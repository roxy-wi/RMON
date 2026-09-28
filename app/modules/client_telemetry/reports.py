"""Snapshot-consistent, bounded reports over persisted minute distributions."""
import json
import time
from contextlib import contextmanager
from datetime import datetime, timezone

from peewee import Case, MySQLDatabase, PostgresqlDatabase, fn

from app.modules.client_telemetry import service
from app.modules.client_telemetry.contract import MINUTE_US, AGGREGATE_DAYS
from app.modules.client_telemetry.distributions import ALGORITHM, describe_report, empty_report, merge_state
from app.modules.client_telemetry.models import (
    ClientDefinition, ClientDirtyInterval, ClientRollup, ClientSegment, ClientSegmentDimension,
)
from app.modules.client_telemetry.schemas import Definition, Event, STANDARD_CONTEXT
from app.modules.client_telemetry.segments import fingerprint
from app.modules.db.db_model import conn

MAX_ROWS = 20000
MAX_POINTS = 1500
MAX_GROUPS = 256
REPORT_SECONDS = 10


@contextmanager
def snapshot():
    # READ COMMITTED could mix two publications between pages of one report.
    options = {'isolation_level': 'REPEATABLE READ'} if isinstance(conn, (PostgresqlDatabase, MySQLDatabase)) else {}
    with conn.atomic(**options):
        yield


class Budget:
    def __init__(self):
        self.deadline = time.monotonic() + REPORT_SECONDS
        self.rows = 0

    def check(self, count=0):
        self.rows += count
        if self.rows > MAX_ROWS or time.monotonic() > self.deadline:
            raise service.TelemetryError(422, 'report_too_large', 'Narrow the time range or add filters to this report')


def _number(args, name, default, maximum):
    value = args.get(name, str(default))
    if not isinstance(value, str) or len(value) > 10 or not value.isascii() or not value.isdigit() or not 1 <= int(value) <= maximum:
        raise service.TelemetryError(422, 'invalid_query', f'{name} must be an integer between 1 and {maximum}')
    return int(value)


def _minute(args, name, default):
    if name not in args:
        return default
    try:
        value = Event.timestamp(args[name])
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.second or parsed.microsecond:
            raise ValueError()
        return int(parsed.timestamp()) // 60
    except (TypeError, ValueError, OverflowError):
        raise service.TelemetryError(422, 'invalid_time', f'{name} must be an RFC 3339 timestamp aligned to a whole minute') from None


def window(args, now):
    end = _minute(args, 'to', now // MINUTE_US)
    start = _minute(args, 'from', end - 60)
    if start >= end or start < now // MINUTE_US - AGGREGATE_DAYS * 1440 or end > now // MINUTE_US + 1:
        raise service.TelemetryError(422, 'invalid_range', 'Select an increasing period within the last 90 days')
    span = end - start
    default_step = next(step for step in (1, 5, 15, 60, 360, 1440) if (span + step - 1) // step <= 500)
    step = _number(args, 'interval_minutes', default_step, 1440)
    if step not in (1, 5, 15, 60, 360, 1440) or (span + step - 1) // step > MAX_POINTS:
        raise service.TelemetryError(422, 'too_many_points', 'Use a larger interval: 1, 5, 15, 60, 360 or 1440 minutes')
    return start, end, step


def _filters(args, allowed):
    try:
        raw = args.get('filters', '{}')
        if len(raw) > 4096:
            raise ValueError()
        values = json.loads(raw)
        if not isinstance(values, dict) or len(values) > 8:
            raise ValueError()
        for name, value in values.items():
            if name not in allowed or value is not None and type(value) is not allowed[name]:
                raise ValueError()
            if isinstance(value, str) and (not 1 <= len(value) <= (2048 if name == '_page_url' else 128) or '\x00' in value):
                raise ValueError()
            if isinstance(value, str):
                value.encode('utf-8')
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise service.TelemetryError(422, 'invalid_filters', 'Filter only declared fields using their defined type; use null for missing values') from None
    return values


def quality(definitions, start, end, now):
    pending = ClientDirtyInterval.generation > ClientDirtyInterval.processed_generation
    row = (ClientDirtyInterval.select(
        fn.SUM(Case(None, [(pending, 1)], 0)).alias('pending'),
        fn.SUM(Case(None, [(pending & ClientDirtyInterval.last_error.is_null(False), 1)], 0)).alias('failed'),
        fn.MIN(Case(None, [(pending, ClientDirtyInterval.minute)], None)).alias('oldest'),
        fn.MAX(ClientDirtyInterval.last_received_us).alias('last_received'),
        fn.MAX(ClientDirtyInterval.updated_us).alias('last_processed'))
        .where((ClientDirtyInterval.definition.in_(definitions)) & (ClientDirtyInterval.minute >= start)
               & (ClientDirtyInterval.minute < end)).dicts().get())
    oldest = row['oldest']
    return {'pending_intervals': row['pending'] or 0, 'failed_intervals': row['failed'] or 0,
            'oldest_pending_at': iso_minute(oldest) if oldest is not None else None,
            'lag_seconds': max(0, now // 1000000 - (oldest + 1) * 60) if oldest is not None else 0,
            'last_received_us': row['last_received'] or None, 'last_processed_us': row['last_processed'] or None,
            'complete': not row['pending']}


def iso_minute(minute):
    return datetime.fromtimestamp(minute * 60, timezone.utc).isoformat().replace('+00:00', 'Z')


def build(check, args, *, include_series=True, budget=None):
    """Caller opens snapshot() around the entire response, including overviews."""
    budget = budget or Budget()
    budget.check()
    now = service.database_us()
    start, end, step = window(args, now)
    definitions = list(ClientDefinition.select().where(ClientDefinition.check == check.id).order_by(ClientDefinition.version))
    if not definitions:
        raise service.TelemetryError(409, 'definition_missing', 'Create a definition for this check')
    allowed = {name: str for name in STANDARD_CONTEXT}
    allowed['_page_url'] = str
    metrics = {}
    for row in definitions:
        definition = Definition.model_validate(row.definition)
        for name, field in definition.context.items():
            if field.filterable:
                allowed[name] = bool if field.type == 'boolean' else str
        measurements = dict(definition.metrics)
        if definition.duration:
            measurements['duration_ms'] = definition.duration
        for name, value in measurements.items():
            if name in metrics and (metrics[name].unit, metrics[name].type) != (value.unit, value.type):
                raise service.TelemetryError(409, 'incompatible_definitions', 'Report definitions use incompatible measurement units or types')
            metrics[name] = value
    latest = Definition.model_validate(definitions[-1].definition)
    default_metric = latest.primary_metric or ('duration_ms' if latest.duration else next(iter(latest.metrics), None))
    metric = args.get('metric', default_metric)
    if metric is not None and metric not in metrics:
        raise service.TelemetryError(422, 'unknown_metric', 'Select a measurement defined for this check')
    outcome = args.get('outcome', 'ok' if metric == 'duration_ms' and latest.has_outcome else 'all')
    if outcome not in ('all', 'ok', 'error') or not latest.has_outcome and outcome != 'all':
        raise service.TelemetryError(422, 'invalid_outcome', 'Select an outcome supported by this check')
    group_by = args.get('group_by')
    if group_by is not None and group_by not in allowed:
        raise service.TelemetryError(422, 'invalid_group', 'Group only by standard or declared filterable context')
    filters, limit = _filters(args, allowed), _number(args, 'limit', 20, 50)
    definition_ids = [row.id for row in definitions]
    condition = ((ClientSegment.definition.in_(definition_ids)) & (ClientSegment.minute >= start) & (ClientSegment.minute < end))
    for name, value in filters.items():
        matches = ClientSegmentDimension.select(ClientSegmentDimension.segment).where(ClientSegmentDimension.name == name)
        if value is None:
            # Older definitions may not have declared this filter yet.
            condition &= ClientSegment.id.not_in(matches.where(ClientSegmentDimension.value_hash != fingerprint(None)))
        else:
            condition &= ClientSegment.id.in_(matches.where(ClientSegmentDimension.value_hash == fingerprint(value)))
    totals, points, groups = empty_report(), {}, {}
    cursor_minute, cursor_id = start, 0
    while True:
        budget.check()
        rows = list(ClientRollup.select(ClientRollup, ClientSegment).join(ClientSegment).where(
            condition & ((ClientSegment.minute > cursor_minute)
                         | ((ClientSegment.minute == cursor_minute) & (ClientSegment.id > cursor_id))))
            .order_by(ClientSegment.minute, ClientSegment.id).limit(100))
        if not rows:
            break
        budget.check(len(rows))
        for row in rows:
            budget.check()
            if row.algorithm != ALGORITHM:
                raise service.TelemetryError(409, 'unsupported_aggregate', 'Update RMON to read this aggregate format')
            merge_state(totals, row.state, metric, outcome)
            if include_series:
                bucket = start + ((row.segment.minute - start) // step) * step
                merge_state(points.setdefault(bucket, empty_report()), row.state, metric, outcome)
            if group_by:
                value = row.segment.dimensions.get(group_by)
                identity = fingerprint(value)
                if identity not in groups:
                    if len(groups) >= MAX_GROUPS:
                        raise service.TelemetryError(422, 'too_many_groups', 'Narrow the period or filters to compare fewer groups')
                    groups[identity] = (value, empty_report())
                merge_state(groups[identity][1], row.state, metric, outcome)
        cursor_minute, cursor_id = rows[-1].segment.minute, rows[-1].segment_id
    aggregation = quality(definition_ids, start, end, now)
    budget.check()
    ranked = sorted(groups.values(), key=lambda item: (-item[1]['observations'], fingerprint(item[0])))
    omitted = ranked[limit:]
    return {'check_id': check.id, 'check': check.code, 'from': iso_minute(start), 'to': iso_minute(end),
            'interval_minutes': step, 'metric': metric, 'metric_label': metrics[metric].label if metric else None,
            'unit': metrics[metric].unit if metric else None,
            'metric_outcome': outcome, 'filters': filters, 'group_by': group_by,
            'state': 'processing' if not aggregation['complete'] else ('ready' if totals['observations'] else 'no_data'),
            'aggregation': aggregation, 'summary': describe_report(totals),
            'series': [{'at': iso_minute(minute), **describe_report(points.get(minute, empty_report()))}
                       for minute in range(start, end, step)] if include_series else [],
            'groups': [{'value': value, **describe_report(state)} for value, state in ranked[:limit]],
            'groups_truncated': bool(omitted), 'omitted_group_observations': sum(state['observations'] for _, state in omitted)}
