"""Dashboard summaries across every location of a check, using the configured database."""
from collections import Counter
from datetime import datetime, timedelta, timezone
import math

from peewee import Case, JOIN, SQL, fn

from app.modules.db.db_model import MultiCheck, SMON, SmonGroup, SmonHistory
from app.modules.tools.common import get_model_for_check


CHECK_TYPES = {'tcp': 1, 'http': 2, 'smtp': 3, 'ping': 4, 'dns': 5, 'rabbitmq': 6}
STATES = ('up', 'down', 'warning', 'stale', 'disabled')


def iso(value):
    return value.replace(tzinfo=timezone.utc).isoformat() if value else None


def number(value):
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) and result >= 0 else None


def location_state(row, now):
    if not row['enabled']:
        return 'disabled'
    # Allow retries to finish before declaring that results stopped arriving.
    allowance = max(60, row['interval'] * 3,
                    row['interval'] + row['check_timeout'] * (row['retries'] + 1))
    if not row['last_result'] or (now - row['last_result']).total_seconds() > allowance:
        return 'stale'
    if row['status'] == 1:
        return 'up'
    if row['status'] in (5, 6, 9):
        return 'warning'
    if row['status'] in (0, 2, 7, 8):
        return 'down'
    return 'stale'


def history_bins(ids, now):
    """Aggregate in SQL; never transfer all raw observations into the web worker."""
    start = now - timedelta(hours=24)
    bucket = Case(None, [(SmonHistory.date < start + timedelta(hours=i + 1), i)
                         for i in range(23)], 23).alias('bucket')
    query = (SmonHistory.select(SmonHistory.smon_id, bucket, SmonHistory.status,
                                fn.COUNT(SmonHistory.smon_id).alias('count'))
             .where((SmonHistory.smon_id.in_(ids)) & (SmonHistory.date >= start) & (SmonHistory.date <= now))
             .group_by(SmonHistory.smon_id, SQL('bucket'), SmonHistory.status).dicts())
    return query


def snapshot(group_id, *, include_history=True, now=None):
    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    latest = (SmonHistory.select(SmonHistory.date).where(
        (SmonHistory.smon_id == SMON.id) & (SmonHistory.date <= now + timedelta(minutes=5)))
        .order_by(SmonHistory.date.desc()).limit(1))
    rows = list(SMON.select(
        SMON.id, SMON.enabled, SMON.status, SMON.check_type, SMON.response_time,
        SMON.check_timeout, SMON.retries, latest.alias('last_result'),
        MultiCheck.id.alias('multi_id'), MultiCheck.name, MultiCheck.description,
        MultiCheck.check_group_id.alias('check_group'), SmonGroup.name.alias('group_name'),
    ).join(MultiCheck).join(SmonGroup, JOIN.LEFT_OUTER, on=(MultiCheck.check_group_id == SmonGroup.id))
        .where((SMON.group_id == group_id) & (MultiCheck.group_id == group_id))
        .order_by(MultiCheck.id, SMON.id).dicts())
    ids = [row['id'] for row in rows]
    intervals = {}
    # Batch configurations without exceeding SQLite's bound-parameter limit.
    for kind in {row['check_type'] for row in rows}:
        model = get_model_for_check(check_type=kind)
        kind_ids = [row['id'] for row in rows if row['check_type'] == kind]
        for offset in range(0, len(kind_ids), 400):
            intervals.update((row.smon_id_id, row.interval) for row in
                             model.select(model.smon_id, model.interval).where(model.smon_id.in_(kind_ids[offset:offset + 400])))
    cards, by_location = {}, {}
    for row in rows:
        row['interval'] = max(1, intervals.get(row['id'], 120))
        if isinstance(row['last_result'], str):
            row['last_result'] = datetime.fromisoformat(row['last_result'])
        if row['last_result'] and row['last_result'].tzinfo:
            row['last_result'] = row['last_result'].astimezone(timezone.utc).replace(tzinfo=None)
        card = cards.setdefault(row['multi_id'], {
            'id': row['multi_id'], 'name': row['name'] or '', 'description': row['description'] or '',
            'type': row['check_type'], 'type_id': CHECK_TYPES[row['check_type']],
            'group_id': row['check_group'], 'group_name': row['group_name'],
            'locations': Counter(), 'responses': [], 'last_result': None,
            'history': [Counter() for _ in range(24)] if include_history else None,
        })
        state = location_state(row, now)
        card['locations'][state] += 1
        response = number(row['response_time'])
        if state in ('up', 'warning') and response is not None:
            card['responses'].append(response)
        if row['last_result'] and (not card['last_result'] or row['last_result'] > card['last_result']):
            card['last_result'] = row['last_result']
        by_location[row['id']] = card
    if ids and include_history:
        for offset in range(0, len(ids), 400):
            for row in history_bins(ids[offset:offset + 400], now).iterator():
                by_location[row['smon_id']]['history'][int(row['bucket'])][row['status']] += row['count']
    counts = dict.fromkeys(STATES, 0)
    for card in cards.values():
        locations = card['locations']
        card['state'] = next((state for state in ('down', 'warning', 'stale', 'up') if locations[state]), 'disabled')
        counts[card['state']] += 1
        card['total_locations'] = sum(locations.values())
        card['active_locations'] = card['total_locations'] - locations['disabled']
        card['locations'] = {state: locations[state] for state in STATES}
        responses = card.pop('responses')
        # Agent timing fields are stored in seconds, including ICMP RTTs.
        card['response_ms'] = sum(responses) * 1000 / len(responses) if responses else None
        card['last_result'] = iso(card['last_result'])
        card['uptime'] = None
        if include_history:
            samples = sum(sum(bucket.values()) for bucket in card['history'])
            healthy = sum(bucket[1] for bucket in card['history'])
            card['uptime'] = healthy * 100 / samples if samples else None
            card['history'] = [{
                'total': sum(bucket.values()), 'up': bucket[1],
                'state': ('down' if any(bucket[s] for s in (0, 2, 7, 8)) else
                          'warning' if any(bucket[s] for s in (5, 6, 9)) else
                          'stale' if any(bucket[s] for s in bucket if s != 1) or not bucket else 'up'),
            } for bucket in card['history']]
    groups = list(SmonGroup.select(SmonGroup.id, SmonGroup.name).where(SmonGroup.group_id == group_id).dicts())
    return {'items': list(cards.values()), 'groups': groups, 'counts': counts, 'updated_at': iso(now),
            'history_start': iso(now - timedelta(hours=24)), 'history_available': include_history}
