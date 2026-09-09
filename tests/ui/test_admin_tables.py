from html.parser import HTMLParser
from types import SimpleNamespace

import pytest
from flask import g, render_template


class Rows(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.rows = []
        self.cell = None
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'tr':
            self.rows.append([])
        if tag in ('th', 'td'):
            self.cell = {'attrs': attrs, 'actions': [], 'text': ''}
            self.rows[-1].append(self.cell)
        if self.cell is not None and (tag == 'button' or attrs.get('onclick') or tag == 'a'):
            self.cell['actions'].append((tag, attrs))

    def handle_endtag(self, tag):
        if tag in ('th', 'td'):
            self.cell = None

    def handle_data(self, data):
        if self.cell is not None:
            self.cell['text'] += data


def render(app, template, *, role=1, language='en', **context):
    with app.test_request_context('/admin'):
        g.user_params = {'role': role, 'group_id': 1}
        lang = language if template.startswith('ajax/load_') else app.jinja_env.get_template(
            f'languages/{language}.html').module
        return render_template(template, lang=lang, **context)


def assert_actions(rows, columns):
    assert rows
    for row in rows:
        assert len(row) == columns
        assert 'actions-column' in row[-1]['attrs'].get('class', '')
        # Editable fields are data; non-data buttons and links belong to Actions.
        assert not any(cell['actions'] for cell in row[:-1])


@pytest.mark.ui
@pytest.mark.parametrize('role,columns', [(1, 5), (2, 6)])
@pytest.mark.parametrize('language', ['en', 'ru', 'fr', 'pt-br'])
def test_users_have_one_actions_column_and_keep_field_ids(app, role, columns, language):
    users = [SimpleNamespace(user_id=9, username='alice', email='alice@example.test', enabled=1, ldap_user=0)]
    html = render(app, 'include/admin_users.html', role=role, language=language, users=users,
                  users_roles=[], user_roles=[], roles=[])
    rows = Rows(html).rows
    assert_actions(rows, columns)
    assert rows[0][-1]['text'].strip() == 'Actions'
    for field in ['login-9', 'enabled-9', 'email-9']:
        assert f'id="{field}"' in html
    assert 'openChangeUserPasswordDialog' in html
    assert ('confirmChangeGroupsAndRoles' in html) == (role == 1)
    fragment = render(app, 'include/admin_users.html', role=role, language=language, adding=True,
                      users=users, users_roles=[], user_roles=[], roles=[])
    assert_actions(Rows(fragment).rows, columns)


@pytest.mark.ui
def test_ldap_and_protected_superadmin_do_not_get_password_actions(app):
    user = SimpleNamespace(user_id=9, username='alice', email='alice@example.test', enabled=1, ldap_user=1)
    html = render(app, 'include/admin_users.html', users=[user], users_roles=[], user_roles=[], roles=[])
    assert 'openChangeUserPasswordDialog' not in html
    user.ldap_user = 0
    html = render(app, 'include/admin_users.html', role=2, users=[user],
                  users_roles=[SimpleNamespace(user_role_id=1, user_id=9)], user_roles=[], roles=[])
    assert 'openChangeUserPasswordDialog' not in html
    assert 'confirmChangeGroupsAndRoles' not in html


@pytest.mark.ui
@pytest.mark.parametrize('role,columns', [(1, 9), (2, 8)])
def test_server_actions_share_a_column_in_full_page_and_ajax_fragment(app, role, columns):
    context = {'servers': [(9, 'test-host', '192.0.2.9', '1', 1, 1, None, 22, 'Test')],
               'groups': [], 'sshs': []}
    for adding in [False, True]:
        html = render(app, 'include/admin_servers.html', role=role, adding=adding, **context)
        rows = Rows(html).rows
        assert all(len(row) == columns for row in rows)
        action_cell = rows[-1][-1]
        assert 'actions-column' in action_cell['attrs']['class']
        assert len(action_cell['actions']) == 6
        for handler in ['checkSshConnect', 'viewFirewallRules', 'showServerInfo', 'cloneServer', 'confirmDeleteServer']:
            assert any(handler in attrs.get('onclick', '') for _, attrs in action_cell['actions'])
        for field in ['hostname-9', 'ip-9', 'port-9', 'server_enabled-9', 'credentials-9', 'desc-9',
                      'server_info_link-9', 'clone-9']:
            assert f'id="{field}"' in html


@pytest.mark.ui
@pytest.mark.parametrize('shared,group,action_count', [(0, 1, 1), (1, 1, 1), (1, 2, 0)])
def test_ssh_delete_menu_respects_shared_credential_ownership(app, shared, group, action_count):
    ssh = SimpleNamespace(id=9, name='test-ssh', key_enabled=1, group_id=group, shared=shared, username='ubuntu')
    html = render(app, 'ajax/new_ssh.html', sshs=[ssh], groups=[])
    rows = Rows(html).rows
    assert_actions(rows, 6)
    assert len(rows[0][-1]['actions']) == action_count


@pytest.mark.ui
def test_services_have_one_actions_column_and_native_disabled_controls(app):
    services = [('rmon-server', 'active', {'current_version': '6.33'}),
                ('rmon-socket', 'inactive', {'current_version': '1.0'}),
                ('rabbitmq-server', 'missing', {'current_version': '* is not installed'})]
    html = render(app, 'ajax/load_services.html', services=services)
    rows = Rows(html).rows
    assert_actions(rows, 4)
    assert 'disabled' in rows[0][-1]['actions'][0][1]
    assert 'disabled' in rows[1][-1]['actions'][2][1]
    assert len(rows[2][-1]['actions']) == 1
    assert 'id="restart-rmon-server"' in html


@pytest.mark.ui
def test_update_rows_have_matching_columns_with_and_without_available_updates(app):
    for need_update in [False, True]:
        html = render(app, 'ajax/load_updateroxywi.html',
                      versions={'need_update': need_update, 'current_ver': '1.4.0', 'new_ver': '1.4.1'},
                      services=[('rmon-server', 'active', {'current_version': '6.33', 'new_version': '6.34', 'update_available': True})])
        rows = Rows(html).rows
        assert all(len(row) == 5 for row in rows)
        assert len(rows[0][-1]['actions']) == int(need_update)
        assert len(rows[1][-1]['actions']) == 1
        assert all('actions-column' in row[-1]['attrs']['class'] for row in rows)


@pytest.mark.ui
@pytest.mark.parametrize('language,missing,unknown', [
    ('en', 'Not installed', 'Version unavailable'),
    ('ru', 'Не установлен', 'Версия недоступна'),
    ('fr', 'Non installé', 'Version indisponible'),
    ('pt-br', 'Não instalado', 'Versão indisponível'),
])
@pytest.mark.parametrize('template', ['ajax/load_updateroxywi.html', 'ajax/load_services.html'])
def test_service_versions_distinguish_source_install_missing_and_unknown(app, language, missing, unknown, template):
    def details(version, installed, update=False):
        return {'current_version': version, 'new_version': '6.34', 'installed': installed,
                'version_known': version != '0', 'update_available': update}
    kwargs = {'versions': {'current_ver': '1.4.0', 'new_ver': '1.3.0', 'need_update': False}}
    html = render(app, template, language=language, services=[
        ('rmon-server', 'active', details('6.33', True, True)),
        ('rmon-socket', 'inactive', details('0', False)),
    ], **kwargs)
    assert '6.33' in html
    assert missing in html
    assert "updateService('rmon-server', 'install')" not in html
    assert "updateService('rmon-socket', 'install')" in html
    html = render(app, template, language=language,
                  services=[('rmon-server', 'active', details('0', True))], **kwargs)
    assert unknown in html
    assert "updateService('rmon-server', 'install')" not in html


@pytest.mark.ui
def test_admin_page_buttons_have_their_own_inset_toolbar(client, auth_headers):
    html = client.get('/admin', headers=auth_headers(1, 1)).get_data(as_text=True)
    assert html.count('class="admin-page-actions"') == 2


@pytest.mark.ui
def test_container_update_links_to_docker_instead_of_installing_packages(app):
    html = render(app, 'ajax/load_updateroxywi.html',
                  versions={'need_update': False, 'current_ver': '1.4.0', 'new_ver': '1.4.0'},
                  services=[('rmon-server', 'active', {'current_version': '6.33', 'new_version': '6.34',
                            'update_available': True, 'managed_by': 'docker', 'installed': True})])
    assert 'https://rmon.io/installation#standalone-server' in html
    assert "updateService('rmon-server'" not in html
