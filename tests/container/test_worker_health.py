import runtime_health
from pathlib import Path


def test_process_probe_never_needs_a_database(tmp_path, monkeypatch):
    monkeypatch.setenv('RMON_PROCESS_HEALTH_DIR', str(tmp_path))
    for role in ('operations', 'scheduler'):
        assert not runtime_health.healthy(role)
        runtime_health.pulse(role)
        assert runtime_health.healthy(role)
        runtime_health.pulse(role, ready=False)
        assert not runtime_health.healthy(role)
        assert runtime_health.healthy(role, ready=False)
    monkeypatch.setattr(runtime_health.time, 'time', lambda: 10**12)
    assert not runtime_health.healthy('operations', ready=False)


def test_worker_entrypoints_are_in_the_container_build_context():
    root = Path(__file__).resolve().parents[2]
    included = (root / '.dockerignore').read_text().splitlines()
    dockerfile = (root / 'Dockerfile').read_text()
    for name in ('scheduler_runner.py', 'operations_runner.py', 'runtime_health.py'):
        assert root.joinpath(name).is_file()
        assert '!' + name in included
        assert name in dockerfile
