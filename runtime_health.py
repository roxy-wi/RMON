"""Local process probes; polling health never adds database traffic."""
import json
import os
from pathlib import Path
import time


def path(role):
    return Path(os.getenv('RMON_PROCESS_HEALTH_DIR', '/tmp')) / f'rmon-{role}-health.json'


def pulse(role, ready=True):
    target = path(role)
    temporary = target.with_suffix(f'.{os.getpid()}.tmp')
    with temporary.open('w', encoding='utf-8') as stream:
        json.dump({'time': time.time(), 'ready': ready}, stream)
    temporary.chmod(0o600)
    os.replace(temporary, target)


def healthy(role, ready=True):
    try:
        state = json.loads(path(role).read_text(encoding='utf-8'))
        return 0 <= time.time() - state['time'] < 90 and (not ready or state['ready'] is True)
    except (OSError, ValueError, KeyError, TypeError):
        return False
