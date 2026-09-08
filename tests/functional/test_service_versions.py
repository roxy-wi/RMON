import copy
from types import SimpleNamespace

import pytest

from app.modules.tools import common


@pytest.fixture
def version_probes(monkeypatch):
    monkeypatch.setattr(common.distro, 'id', lambda: 'ubuntu')
    monkeypatch.setattr(common.distro, 'like', lambda: '')
    writes = []
    monkeypatch.setattr(common.roxy_sql, 'update_tool_cur_version', lambda *args: writes.append(args))
    return writes


@pytest.mark.parametrize('distro_name,package,expected', [
    ('ubuntu', 'install ok installed\t6.33-1', '6.33.1'),
    ('debian', 'install ok installed\t1:6.33-2', '6.33.2'),
    ('ubuntu', 'install ok installed\t1.0.2-3ubuntu1.1', '1.0.2'),
    ('rocky', '1.0.2-14.el9', '1.0.2'),
    ('rocky', '6.33-1', '6.33.1'),
])
def test_exact_package_versions_for_deb_and_rpm(monkeypatch, version_probes, distro_name, package, expected):
    monkeypatch.setattr(common.distro, 'id', lambda: distro_name)
    calls = []
    def query(args):
        calls.append(args)
        return package
    monkeypatch.setattr(common, '_version_command', query)
    result = common.update_cur_tool_version('rmon-server')
    assert result == {'current_version': expected, 'version_known': True, 'installed': True}
    assert calls[0][-1] == 'rmon-server'
    assert calls[0][0] == ('dpkg-query' if distro_name in ('ubuntu', 'debian') else 'rpm')
    assert len(calls) == 1
    assert version_probes == [('rmon-server', expected)]


def test_source_install_reads_unit_working_directory_without_executing_code(monkeypatch, tmp_path, version_probes):
    source = tmp_path / 'custom deployment' / 'modules' / 'common'
    source.mkdir(parents=True)
    (source / 'version.py').write_text('raise RuntimeError("Must never execute")\nSERVICE_VERSION = "6.33"\n')
    monkeypatch.setattr(common, '_version_command', lambda args:
                        None if args[0] == 'dpkg-query' else f'LoadState=loaded\nWorkingDirectory={source.parents[1]}')
    assert common.update_cur_tool_version('rmon-server') == {
        'current_version': '6.33', 'version_known': True, 'installed': True}
    assert version_probes == [('rmon-server', '6.33')]


@pytest.mark.parametrize('content', [
    'SERVICE_VERSION = read_secret()',
    'SERVICE_VERSION = "<html>error</html>"',
    'SERVICE_VERSION = ',
    'SERVICE_VERSION = 6.33',
    '#' * 65537,
], ids=['expression', 'html', 'syntax', 'number', 'oversized'])
def test_invalid_source_metadata_is_not_a_version(tmp_path, content):
    source = tmp_path / 'modules' / 'common'
    source.mkdir(parents=True)
    (source / 'version.py').write_text(content)
    assert common._source_version(str(tmp_path)) is None


@pytest.mark.parametrize('properties,installed', [
    ('LoadState=not-found\nWorkingDirectory=', False),
    ('LoadState=loaded\nWorkingDirectory=/nonexistent-rmon-test-path', True),
    (None, None),
])
def test_missing_package_is_not_confused_with_missing_or_stopped_source_service(monkeypatch, version_probes, properties, installed):
    monkeypatch.setattr(common, '_version_command', lambda args:
                        'deinstall ok config-files\t6.33' if args[0] == 'dpkg-query' else properties)
    assert common.update_cur_tool_version('rmon-socket') == {
        'current_version': '0', 'version_known': False, 'installed': installed}


def test_command_uses_argument_list_timeout_and_exit_status(monkeypatch):
    calls = []
    def run(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(returncode=0, stdout=' 6.33\n')
    monkeypatch.setattr(common.subprocess, 'run', run)
    assert common._version_command(['rpm', '-q', 'rmon-server']) == '6.33'
    assert calls[0][1]['timeout'] == 3
    assert not calls[0][1].get('shell')
    monkeypatch.setattr(common.subprocess, 'run', lambda *args, **kwargs: SimpleNamespace(returncode=1, stdout='6.33'))
    assert common._version_command(['rpm']) is None


@pytest.mark.parametrize('error', [FileNotFoundError(), common.subprocess.TimeoutExpired('rpm', 3)])
def test_unavailable_package_manager_is_handled(monkeypatch, error):
    def run(*args, **kwargs):
        raise error
    monkeypatch.setattr(common.subprocess, 'run', run)
    assert common._version_command(['rpm']) is None


def test_service_name_cannot_inject_commands(monkeypatch, version_probes):
    monkeypatch.setattr(common, '_version_command', lambda _: pytest.fail('Command must not run'))
    with pytest.raises(ValueError):
        common.update_cur_tool_version('rmon-server; touch /tmp/unexpected')
    assert not version_probes


@pytest.mark.parametrize('current,latest,expected', [
    ('6.9', '6.33', True), ('6.33', '6.9', False), ('6.33', '6.33', False),
    ('1.9', '1.10', True), ('0', '6.34', False), ('6.33', '', False),
])
def test_refresh_is_visible_on_first_request_and_versions_are_not_compared_as_floats(monkeypatch, current, latest, expected):
    stored = {'rmon-server': {'current_version': '0', 'new_version': latest}}
    monkeypatch.setattr(common.roxy_sql, 'get_all_tools', lambda: copy.deepcopy(stored))
    monkeypatch.setattr(common, 'is_tool_active', lambda _: 'active')
    def refresh(name):
        stored[name]['current_version'] = current
        return {'current_version': current, 'version_known': current != '0', 'installed': True}
    monkeypatch.setattr(common, 'update_cur_tool_version', refresh)
    result = common.get_services_status(update_cur_ver=1)
    assert result[0][2]['current_version'] == current
    assert result[0][2]['update_available'] is expected


def test_update_tab_refreshes_installed_versions(client, auth_headers, monkeypatch):
    calls = []
    monkeypatch.setattr('app.modules.roxywi.roxy.versions',
                        lambda: {'current_ver': '1.4.0', 'new_ver': '1.3.0', 'need_update': False})
    monkeypatch.setattr(common, 'get_services_status', lambda **kwargs: calls.append(kwargs) or [])
    assert client.get('/admin/update', headers=auth_headers(1, 1)).status_code == 200
    assert calls == [{'update_cur_ver': 1}]
