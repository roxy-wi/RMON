"""Read a check and its location measurements from the configured stores."""
from collections import Counter
from bisect import bisect_right
from datetime import datetime, timedelta, timezone
import math

from peewee import Case, fn
import requests

from app.modules.db import sql
from app.modules.db.db_model import MultiCheck, SMON, SmonHistory
from app.modules.tools.common import get_model_for_check
from app.modules.tools.dashboard import CHECK_TYPES, iso, location_state, number


POINT_LIMIT = 2000
TIMINGS = ('response_time', 'name_lookup', 'connect', 'app_connect', 'pre_transfer',
           'redirect', 'start_transfer', 'download')
VM_NAMES = {'name_lookup': 'namelookup', 'app_connect': 'appconnect',
            'pre_transfer': 'pretransfer', 'start_transfer': 'starttransfer'}
PING_FIELDS = {'avg_resp_time': 'name_lookup', 'max_resp_time': 'connect',
               'min_resp_time': 'app_connect', 'packet_loss_percent': 'pre_transfer'}
CONFIG_FIELDS = ('interval', 'ip', 'port', 'url', 'method', 'accepted_status_codes',
                 'resolver', 'record_type', 'packet_size', 'count_packets')


class MetricsUnavailable(Exception):
    pass


def load_check(check_id, type_id, group_id):
    check = MultiCheck.get((MultiCheck.id == check_id) & (MultiCheck.group_id == group_id))
    kind = next((key for key, value in CHECK_TYPES.items() if value == type_id), None)
    locations = list(SMON.select().where((SMON.multi_check_id == check.id) &
                     (SMON.group_id == group_id) & (SMON.check_type == kind)).order_by(SMON.id))
    if not locations:
        raise SMON.DoesNotExist()
    return check, locations


def metric_definitions(kind):
    names = (TIMINGS if kind == 'http' else TIMINGS[:4] if kind == 'smtp' else
             ('response_time', *PING_FIELDS) if kind == 'ping' else ('response_time',))
    return [{'id': key, 'unit': '%' if key == 'packet_loss_percent' else 'ms'} for key in names]


def metric_value(value, unit):
    parsed = number(value)
    scaled = parsed * 1000 if parsed is not None and unit == 'ms' else parsed
    return scaled if scaled is not None and math.isfinite(scaled) else None


def location_info(check, now):
    model = get_model_for_check(check_type=check.check_type)
    fields = [getattr(model, name) for name in CONFIG_FIELDS if name in model._meta.fields]
    config = model.select(*fields).where(model.smon_id == check.id).dicts().first() or {}
    latest = SmonHistory.select().where((SmonHistory.smon_id == check.id) &
             (SmonHistory.date <= now)).order_by(SmonHistory.date.desc()).first()
    agent = check.agent_id
    region = check.region_id or (agent.region_id if agent else None)
    country = check.country_id or (region.country_id if region else None)
    state = location_state({'enabled': check.enabled, 'status': check.status,
                           'interval': max(1, config.get('interval', 120)),
                           'check_timeout': check.check_timeout, 'retries': check.retries,
                           'last_result': latest.date if latest else None}, now)
    response = number(latest.response_time) if latest and state in ('up', 'warning') else None
    return {
        'id': check.id, 'agent': agent.name if agent else None,
        'region': region.name if region else None, 'country': country.name if country else None,
        'state': state, 'status': check.status, 'response_ms': response * 1000 if response is not None else None,
        'last_result': iso(latest.date) if latest else None, 'error': latest.mes if latest else None,
        'certificate_expires': check.ssl_expire_date, 'config': config,
        'timeout': check.check_timeout, 'retries': check.retries,
        'created_at': iso(check.created_at), 'updated_at': iso(check.updated_at),
        'uptime': None, 'mean_ms': None,
    }


def daily_summary(locations, now):
    by_id = {location['id']: location for location in locations}
    ids = list(by_id)
    total, up, response_sum, response_count = 0, 0, 0, 0
    valid = (SmonHistory.status.in_((1, 5, 6, 9))) & (SmonHistory.response_time >= 0)
    for offset in range(0, len(ids), 400):
        rows = (SmonHistory.select(SmonHistory.smon_id, fn.COUNT(SmonHistory.smon_id).alias('total'),
                fn.SUM(Case(None, [(SmonHistory.status == 1, 1)], 0)).alias('up'),
                fn.SUM(Case(None, [(valid, SmonHistory.response_time)], 0)).alias('response_sum'),
                fn.SUM(Case(None, [(valid, 1)], 0)).alias('response_count'))
                .where((SmonHistory.smon_id.in_(ids[offset:offset + 400])) &
                       (SmonHistory.date >= now - timedelta(hours=24)) & (SmonHistory.date <= now))
                .group_by(SmonHistory.smon_id).dicts())
        for row in rows:
            location = by_id[row['smon_id']]
            location['uptime'] = row['up'] * 100 / row['total']
            location['mean_ms'] = row['response_sum'] * 1000 / row['response_count'] if row['response_count'] else None
            total += row['total']
            up += row['up']
            response_sum += row['response_sum']
            response_count += row['response_count']
    return {'uptime': up * 100 / total if total else None,
            'mean_ms': response_sum * 1000 / response_count if response_count else None}


def sql_series(locations, definitions, kind, start, end):
    series, truncated = [], False
    for location in locations:
        rows = list(SmonHistory.select().where((SmonHistory.smon_id == location['id']) &
                    (SmonHistory.date >= start) & (SmonHistory.date <= end))
                    .order_by(SmonHistory.date.desc()).limit(POINT_LIMIT + 1))
        truncated = truncated or len(rows) > POINT_LIMIT
        rows = list(reversed(rows[:POINT_LIMIT]))
        for definition in definitions:
            key, unit = definition['id'], definition['unit']
            field = PING_FIELDS.get(key, key) if kind == 'ping' else key
            points = []
            previous = None
            gap = max(60, location['config'].get('interval', 120) * 3)
            for row in rows:
                # A missing run or a failed measurement is a gap, never a zero latency.
                if previous and (row.date - previous).total_seconds() > gap:
                    points.append({'x': iso(previous + timedelta(seconds=1)), 'y': None})
                value = metric_value(getattr(row, field), unit)
                if row.status not in (1, 5, 6, 9) and unit != '%':
                    value = None
                points.append({'x': iso(row.date), 'y': value})
                previous = row.date
            series.append({'location_id': location['id'], **definition, 'points': points})
    return series, truncated


def vm_series(locations, definitions, start, end):
    """One bounded range request; preserve each metric's own timestamps."""
    ids = {str(location['id']) for location in locations}
    names = {VM_NAMES.get(item['id'], item['id']): item for item in definitions}
    selector = '|'.join(sorted(ids, key=int))
    namespace = sql.get_setting('rmon_name')
    query = f'{namespace}_metrics{{check_id=~"{selector}",metric=~"{"|".join(names)}"}}'
    step = max(1, math.ceil((end - start).total_seconds() / (POINT_LIMIT - 1)))
    try:
        response = requests.get(sql.get_setting('victoria_metrics_select').rstrip('/') + '/query_range',
                                params={'query': query, 'start': iso(start), 'end': iso(end), 'step': f'{step}s'},
                                timeout=(3, 10))
        response.raise_for_status()
        payload = response.json()
        if payload.get('status') != 'success':
            raise ValueError('Metric store rejected the query')
        result = {}
        for item in payload['data']['result']:
            location_id = item['metric'].get('check_id')
            definition = names.get(item['metric'].get('metric'))
            if location_id not in ids or definition is None:
                continue
            values = result.setdefault((int(location_id), definition['id']), {})
            for stamp, value in item['values']:
                date = datetime.fromtimestamp(float(stamp), timezone.utc).replace(tzinfo=None)
                if start <= date <= end:
                    values[date] = metric_value(value, definition['unit'])
        series = []
        for location in locations:
            for definition in definitions:
                values = result.get((location['id'], definition['id']), {})
                points, previous = [], None
                for date, value in sorted(values.items()):
                    gap = max(step * 1.5, location['config'].get('interval', 120) * 3)
                    if previous and (date - previous).total_seconds() > gap:
                        points.append({'x': iso(previous + timedelta(seconds=step)), 'y': None})
                    points.append({'x': iso(date), 'y': value})
                    previous = date
                series.append({'location_id': location['id'], **definition, 'points': points})
        return series, mask_failed_samples(series, locations, start, end)
    except (requests.RequestException, ValueError, KeyError, TypeError, OverflowError) as error:
        # Do not expose the metric store URL, credentials, or response body.
        raise MetricsUnavailable() from error


def mask_failed_samples(series, locations, start, end):
    """VM has timing fields; the SQL history remains the source of check statuses."""
    truncated = False
    for location in locations:
        rows = list(SmonHistory.select(SmonHistory.date, SmonHistory.status)
                    .where((SmonHistory.smon_id == location['id']) &
                           (SmonHistory.date >= start) & (SmonHistory.date <= end))
                    .order_by(SmonHistory.date.desc()).limit(POINT_LIMIT + 1))
        limited = len(rows) > POINT_LIMIT
        truncated = truncated or limited
        rows = list(reversed(rows[:POINT_LIMIT]))
        before = (SmonHistory.select(SmonHistory.date, SmonHistory.status)
                  .where((SmonHistory.smon_id == location['id']) & (SmonHistory.date < start))
                  .order_by(SmonHistory.date.desc()).first()) if not limited else None
        if before:
            rows.insert(0, before)
        dates = [row.date for row in rows]
        for item in series:
            if item['location_id'] != location['id'] or item['unit'] == '%':
                continue
            for point in item['points']:
                when = datetime.fromisoformat(point['x']).replace(tzinfo=None)
                index = bisect_right(dates, when) - 1
                if (index >= 0 and rows[index].status not in (1, 5, 6, 9)) or (limited and index < 0):
                    point['y'] = None
    return truncated


def snapshot(check_id, type_id, group_id, *, hours=1, location_id=None, now=None):
    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    check, checks = load_check(check_id, type_id, group_id)
    if location_id is not None and location_id not in {item.id for item in checks}:
        raise SMON.DoesNotExist()
    kind = checks[0].check_type
    locations = [location_info(item, now) for item in checks]
    summary = daily_summary(locations, now)
    states = Counter(location['state'] for location in locations)
    responses = [item['response_ms'] for item in locations if item['response_ms'] is not None]
    summary.update(state=next((s for s in ('down', 'warning', 'stale', 'up') if states[s]), 'disabled'),
                   response_ms=sum(responses) / len(responses) if responses else None,
                   locations=dict(states), total_locations=len(locations))
    selected = [item for item in locations if location_id is None or item['id'] == location_id]
    definitions = metric_definitions(kind) if location_id else [{'id': 'response_time', 'unit': 'ms'}]
    start = now - timedelta(hours=hours)
    if sql.get_setting('use_victoria_metrics'):
        series, truncated = vm_series(selected, definitions, start, now)
    else:
        series, truncated = sql_series(selected, definitions, kind, start, now)
    # Latest results are deliberately separate from the latency lines.
    events = []
    for item in selected:
        rows = (SmonHistory.select(SmonHistory.date, SmonHistory.status, SmonHistory.mes)
                .where((SmonHistory.smon_id == item['id']) & (SmonHistory.date >= start) & (SmonHistory.date <= now))
                .order_by(SmonHistory.date.desc()).limit(20))
        events.extend({'location_id': item['id'], 'date': iso(row.date), 'status': row.status, 'message': row.mes}
                      for row in rows)
    events.sort(key=lambda row: row['date'], reverse=True)
    return {'id': check.id, 'name': check.name or '', 'description': check.description or '',
            'type': kind, 'type_id': type_id, 'summary': summary, 'locations': locations,
            'series': series, 'events': events[:20], 'selected_location': location_id,
            'start': iso(start), 'end': iso(now), 'updated_at': iso(now),
            'truncated': truncated, 'point_limit': POINT_LIMIT}
