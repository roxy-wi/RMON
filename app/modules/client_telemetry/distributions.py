"""Mergeable, bounded-range sparse histograms. Never merge calculated percentiles."""
from bisect import bisect_left
from decimal import Decimal
from math import ceil

from app.modules.client_telemetry.schemas import SAFE_NUMBER

ALGORITHM = 1
# Fixed across units and compatible definition versions. Positive buckets differ
# by 2**(1/16), giving <=2.22% midpoint error away from zero; absolute resolution
# near zero is 2**-30. Contract validation bounds all input to SAFE_NUMBER.
POSITIVE = [2 ** (power / 16) for power in range(-480, 849) if 2 ** (power / 16) < SAFE_NUMBER]
BOUNDS = [-SAFE_NUMBER, *(-value for value in reversed(POSITIVE)), 0, *POSITIVE, SAFE_NUMBER]


def empty_metric():
    return {'count': 0, 'sum': '0', 'min': None, 'max': None, 'buckets': {}}


def add_value(state, value):
    state['count'] += 1
    state['sum'] = str(Decimal(state['sum']) + Decimal(str(value)))
    state['min'] = value if state['min'] is None else min(state['min'], value)
    state['max'] = value if state['max'] is None else max(state['max'], value)
    bucket = str(bisect_left(BOUNDS, value))
    state['buckets'][bucket] = state['buckets'].get(bucket, 0) + 1


def merge_metric(target, source):
    if not source['count']:
        return
    target['count'] += source['count']
    target['sum'] = str(Decimal(target['sum']) + Decimal(source['sum']))
    target['min'] = source['min'] if target['min'] is None else min(target['min'], source['min'])
    target['max'] = source['max'] if target['max'] is None else max(target['max'], source['max'])
    for bucket, count in source['buckets'].items():
        target['buckets'][bucket] = target['buckets'].get(bucket, 0) + count


def percentile(state, fraction):
    if not state['count']:
        return None
    rank, cumulative = ceil(state['count'] * fraction), 0
    for bucket, count in sorted(state['buckets'].items(), key=lambda item: int(item[0])):
        cumulative += count
        if cumulative < rank:
            continue
        index = int(bucket)
        lower = BOUNDS[index - 1] if index else -SAFE_NUMBER
        upper = BOUNDS[index]
        lower, upper = max(lower, state['min']), min(upper, state['max'])
        return (lower + upper) / 2
    raise ValueError('Histogram counts are inconsistent')


def describe(state):
    return {'count': state['count'], 'sum': float(Decimal(state['sum'])) if state['count'] else None,
            'min': state['min'], 'max': state['max'],
            'mean': float(Decimal(state['sum']) / state['count']) if state['count'] else None,
            'p50': percentile(state, .50), 'p95': percentile(state, .95), 'p99': percentile(state, .99),
            'percentiles_approximate': True, 'algorithm': ALGORITHM}


def empty_state():
    return {'observations': 0, 'ok': 0, 'error': 0, 'sampling_min': None, 'sampling_max': None,
            'metrics': {'all': {}, 'ok': {}, 'error': {}}}


def add_event(state, event):
    state['observations'] += 1
    status = event.get('status')
    if status in ('ok', 'error'):
        state[status] += 1
    probability = event.get('sampling_probability', 1)
    state['sampling_min'] = probability if state['sampling_min'] is None else min(state['sampling_min'], probability)
    state['sampling_max'] = probability if state['sampling_max'] is None else max(state['sampling_max'], probability)
    values = dict(event.get('metrics', {}))
    if 'duration_ms' in event:
        values['duration_ms'] = event['duration_ms']
    for scope in ('all', status) if status in ('ok', 'error') else ('all',):
        for name, value in values.items():
            add_value(state['metrics'][scope].setdefault(name, empty_metric()), value)


def merge_state(target, source, metric, outcome):
    for name in ('observations', 'ok', 'error'):
        target[name] += source[name]
    if source['observations']:
        target['sampling_min'] = source['sampling_min'] if target['sampling_min'] is None else min(target['sampling_min'], source['sampling_min'])
        target['sampling_max'] = source['sampling_max'] if target['sampling_max'] is None else max(target['sampling_max'], source['sampling_max'])
    if metric in source['metrics'][outcome]:
        merge_metric(target['metric'], source['metrics'][outcome][metric])


def empty_report():
    return {'observations': 0, 'ok': 0, 'error': 0, 'sampling_min': None, 'sampling_max': None, 'metric': empty_metric()}


def describe_report(state):
    outcomes = state['ok'] + state['error']
    return {'observations': state['observations'], 'successful': state['ok'], 'errors': state['error'],
            'outcomes': outcomes, 'error_rate': state['error'] / outcomes if outcomes else None,
            'sampling': {'min_probability': state['sampling_min'], 'max_probability': state['sampling_max'],
                         'population_estimated': False}, 'metric': describe(state['metric'])}
