from pathlib import Path
import os
import subprocess
import sys
from unittest.mock import Mock

import pytest
from flask import render_template

from app.modules.tools import common
from app.modules.roxywi import roxy
from app.modules.service import installation


@pytest.fixture(autouse=True)
def container_mode(monkeypatch):
    monkeypatch.setenv('RMON_CONTAINER', '1')
    monkeypatch.delenv('RMON_SERVER_INTERNAL_URL', raising=False)


def test_migration_cli_works_without_service_metrics_directory(tmp_path):
    metrics_directory = tmp_path / 'missing-service-metrics'
    environment = dict(os.environ, RMON_PROMETHEUS_MULTIPROC_DIR=str(metrics_directory),
                       RMON_SCHEDULER_ENABLED='1', TEMP=str(tmp_path), TMP=str(tmp_path), TMPDIR=str(tmp_path))
    result = subprocess.run([sys.executable, 'app/migrate.py', 'list'],
                            cwd=Path(__file__).resolve().parents[2], env=environment,
                            text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert '20260916000000_add_operation_queue' in result.stdout
    assert not metrics_directory.exists()
    assert not list(tmp_path.glob('rmon-migrate-metrics-*'))


@pytest.mark.parametrize('service', ['rmon', 'rmon-server', 'fail2ban'])
def test_container_never_installs_os_packages(monkeypatch, service):
    monkeypatch.setattr(common.server_mod, 'subprocess_execute', Mock(side_effect=AssertionError('Package command')))
    with pytest.raises(ValueError, match='outside'):
        common.update_roxy_wi(service)


@pytest.mark.parametrize('action', ['start', 'stop', 'restart'])
def test_container_never_controls_local_daemons(monkeypatch, action):
    monkeypatch.setattr(roxy.os, 'system', Mock(side_effect=AssertionError('Local service command')))
    assert roxy.action_service(action, 'rmon-server').startswith('error:')


def test_no_false_versions_or_package_queries_for_external_services(monkeypatch):
    monkeypatch.setattr(common, '_version_command', Mock(side_effect=AssertionError('Package query')))
    monkeypatch.setattr(common.server_mod, 'subprocess_execute', Mock(side_effect=AssertionError('Systemctl')))
    assert common.is_tool_active('fail2ban') == 'external'
    assert common.update_cur_tool_version('fail2ban') == {
        'current_version': '0', 'installed': None, 'version_known': False, 'managed_by': 'external'}
    monkeypatch.setattr(common.roxy_sql, 'get_all_tools', lambda: {'fail2ban': {'current_version': '1.0', 'new_version': '1.5'}})
    service = common.get_services_status()[0]
    assert service[2]['version_known'] is False
    assert service[2]['update_available'] is False
    assert service[2]['installed'] is None


def test_external_server_can_still_report_version(monkeypatch):
    monkeypatch.setenv('RMON_SERVER_INTERNAL_URL', 'https://receiver:5100')
    monkeypatch.setattr(common, '_server_runtime_version', lambda: '7.0')
    monkeypatch.setattr(common.roxy_sql, 'update_tool_cur_version', Mock())
    assert common.update_cur_tool_version('rmon-server')['current_version'] == '7.0'


def test_container_ui_hides_external_actions_and_own_package_update(app):
    services = [['rmon-server', 'external', {'current_version': '0', 'new_version': '7.0',
                                          'installed': None, 'version_known': False, 'managed_by': 'external'}]]
    with app.test_request_context('/'):
        services_html = render_template('ajax/load_services.html', services=services, lang='en')
        update_html = render_template('ajax/load_updateroxywi.html', services=services, lang='en',
                                      versions={'current_ver': '1.4.0', 'new_ver': '2.0', 'need_update': True,
                                                'managed_by': 'docker'})
    assert 'Managed externally' in services_html
    assert 'confirmAjaxServiceAction' not in services_html
    assert 'updateService(' not in update_html
    assert 'Update container image' in update_html


def test_agent_installation_no_longer_needs_source_payload():
    role = Path(__file__).resolve().parents[2] / 'app/scripts/ansible/roles/rmon_agent'
    install = (role / 'tasks/install.yml').read_text()
    assert not (role / 'files/container_agent.py').exists()
    assert '/var/www/rmon/app/tools/rmon-agent' not in install


@pytest.mark.parametrize('available', [True, False])
def test_container_uses_bundled_collections_and_never_downloads_at_runtime(monkeypatch, available):
    monkeypatch.setattr(installation.subprocess, 'run', Mock(side_effect=AssertionError('Runtime download')))
    monkeypatch.setattr(installation.Path, 'is_dir', lambda _: available)
    if available:
        assert installation._ensure_agent_collections().replace('\\', '/') == '/usr/share/ansible/collections'
    else:
        with pytest.raises(RuntimeError, match='Ansible collections are missing'):
            installation._ensure_agent_collections()


def test_container_log_job_does_not_chown_data(monkeypatch):
    from app import jobs
    monkeypatch.setattr(jobs.os, 'system', Mock(side_effect=AssertionError('Recursive chown')))
    jobs.update_owner_on_log()


def test_container_artifact_cleanup_preserves_writable_directory(tmp_path, monkeypatch):
    from app import jobs
    artifact = tmp_path / 'artifacts'
    artifact.mkdir()
    (artifact / 'run').mkdir()
    (artifact / 'run' / 'result').write_text('private artifact')
    import time
    jobs.os.utime(artifact / 'run', (time.time() - 3 * 86400,) * 2)
    (artifact / 'recent').mkdir()
    original_scandir = jobs.os.scandir
    monkeypatch.setattr(jobs.os.path, 'isdir', lambda path: str(path).endswith('/artifacts'))
    monkeypatch.setattr(jobs.os, 'scandir', lambda path: original_scandir(artifact) if str(path).startswith('/var/www/') else original_scandir(path))
    jobs.delete_ansible_artifacts()
    assert artifact.is_dir()
    assert list(artifact.iterdir()) == [artifact / 'recent']
