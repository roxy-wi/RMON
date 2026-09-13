from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest


PRIVATE_UI_PATHS = (
    '/overview',
    '/admin',
    '/rmon/dashboard',
    '/rmon/status-page',
    '/rmon/history',
    '/channel',
    '/rmon/agent',
    '/nettools',
)

CORE_UI_PAGES = (
    ('/overview', {'overview-roxy-wi', 'overview-services', 'overview-users', 'overview-groups'}),
    ('/admin', {'tabs', 'admin-tabs', 'users', 'servers', 'settings', 'oidc-provider-form'}),
    ('/rmon/dashboard', {'smon-add-table', 'check_type', 'new-smon-name'}),
    ('/rmon/status-page', {'pages', 'create-status-page-step-1', 'new-status-page-name'}),
    ('/rmon/history', {'alerts_table'}),
    ('/channel', {'checker'}),
    ('/rmon/agent', {'countries', 'add-agent-page', 'add-country-page'}),
    ('/nettools', {'nettools_icmp_form', 'nettools_telnet_form', 'nettools_ipcalc_form'}),
)

SUPPORTED_LANGUAGES = ('en', 'ru', 'fr', 'pt-br')


@pytest.mark.ui
@pytest.mark.parametrize('language', SUPPORTED_LANGUAGES)
def test_admin_settings_remain_available_without_broker_in_every_language(client, auth_headers, language):
    client.set_cookie('lang', language)
    document = _document(client.get('/admin', headers=auth_headers(1, 1)))
    assert {'main-section-head', 'smon-section-head', 'mail-section-head', 'agent-section-head'} <= set(document.ids)
    assert document.find(element_id='rabbitmq-section-head') is None


class HtmlDocument(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.elements = []

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))

    def find(self, *, tag=None, element_id=None):
        for element_tag, attrs in self.elements:
            if tag is not None and element_tag != tag:
                continue
            if element_id is not None and attrs.get('id') != element_id:
                continue
            return attrs
        return None

    def find_all(self, *, tag=None, class_name=None):
        matches = []
        for element_tag, attrs in self.elements:
            if tag is not None and element_tag != tag:
                continue
            classes = (attrs.get('class') or '').split()
            if class_name is not None and class_name not in classes:
                continue
            matches.append(attrs)
        return matches

    @property
    def ids(self):
        return [attrs['id'] for _tag, attrs in self.elements if attrs.get('id')]

    @property
    def local_assets(self):
        assets = set()
        for tag, attrs in self.elements:
            attribute = 'src' if tag == 'script' else 'href' if tag == 'link' else None
            if attribute is None:
                continue
            value = attrs.get(attribute, '')
            path = urlsplit(value).path
            if path.startswith('/static/'):
                assets.add(path)
        return assets


def _document(response):
    assert response.status_code == 200
    assert response.content_type.startswith('text/html')
    document = HtmlDocument()
    document.feed(response.get_data(as_text=True))
    return document


def _assert_unique_ids(document, ids):
    counts = Counter(document.ids)
    duplicates = {element_id: counts[element_id] for element_id in ids if counts[element_id] != 1}
    assert not duplicates, f'Expected one element for every UI id, got {duplicates}'


@pytest.mark.ui
def test_login_page_exposes_complete_local_login_form(client):
    response = client.get('/login')
    document = _document(response)

    form = document.find(tag='form', element_id='auth')
    username = document.find(tag='input', element_id='login')
    password = document.find(tag='input', element_id='pass')
    submit = document.find(tag='button', element_id='enter')

    assert form is not None and form['method'] == 'post'
    assert username is not None and 'required' in username
    assert password is not None and password['type'] == 'password' and 'required' in password
    assert submit is not None and submit['type'] == 'submit'
    assert document.find(element_id='top-link') is None


@pytest.mark.ui
def test_login_page_renders_enabled_oidc_provider_and_safe_return_path(client, monkeypatch):
    provider = SimpleNamespace(slug='company-sso', label='Company SSO')
    monkeypatch.setattr('app.login.oidc_sql.list_providers', lambda enabled_only: [provider])

    response = client.get('/login', query_string={'next': '/rmon/dashboard'})
    document = _document(response)
    oidc_buttons = document.find_all(tag='a', class_name='oidc-login-button')

    assert len(oidc_buttons) == 1
    assert oidc_buttons[0]['href'] == '/oidc/company-sso/login?next=/rmon/dashboard'
    assert 'Company SSO' in response.get_data(as_text=True)


@pytest.mark.ui
@pytest.mark.parametrize('path', PRIVATE_UI_PATHS)
def test_private_ui_pages_reject_anonymous_requests(client, path):
    response = client.get(path)

    assert response.status_code == 302
    location = urlsplit(response.headers['Location'])
    assert location.path == '/login'
    assert parse_qs(location.query) == {'next': [path]}
    assert 'access_token_cookie=' not in response.headers.get('Set-Cookie', '')


@pytest.mark.ui
@pytest.mark.parametrize(('path', 'expected_ids'), CORE_UI_PAGES)
def test_authenticated_core_ui_pages_render(
    client, auth_headers, monkeypatch, path, expected_ids
):
    monkeypatch.setattr('app.modules.tools.common.is_tool_active', lambda _name: 'active')

    response = client.get(path, headers=auth_headers(1, 1))
    document = _document(response)

    assert expected_ids <= set(document.ids)
    assert document.find(element_id='top-link') is not None
    assert document.find(element_id='disable_alerting') is None
    assert document.find(element_id='user_group_socket') is None
    assert document.find(element_id='user_id_socket') is None
    assert not any('reconnecting-websocket' in asset or 'ion.sound' in asset for asset in document.local_assets)

    for asset in document.local_assets:
        asset_response = client.get(asset)
        assert asset_response.status_code == 200, f'Missing UI asset referenced by {path}: {asset}'


@pytest.mark.ui
def test_navigation_shows_admin_features_only_to_authorized_roles(client, auth_headers):
    superadmin = _document(client.get('/overview', headers=auth_headers(1, 1)))
    guest = _document(client.get('/overview', headers=auth_headers(3, 1)))

    superadmin_links = {attrs.get('href') for attrs in superadmin.find_all(tag='a')}
    superadmin_admin_links = {
        attrs.get('href') for attrs in superadmin.find_all(tag='a', class_name='admin')
    }
    guest_links = {attrs.get('href') for attrs in guest.find_all(tag='a')}
    guest_admin_links = {
        attrs.get('href') for attrs in guest.find_all(tag='a', class_name='admin')
    }

    assert superadmin.find(element_id='admin-area') is not None
    assert '/admin#oidc' in superadmin_links
    assert '/rmon/agent' in superadmin_admin_links

    assert guest.find(element_id='admin-area') is None
    assert '/admin#oidc' not in guest_links
    assert '/rmon/agent' not in guest_admin_links
    assert {'/overview', '/rmon/dashboard', '/rmon/status-page', '/rmon/history', '/channel', '/nettools'} <= guest_links


@pytest.mark.ui
def test_monitoring_dashboard_contains_every_supported_check_editor(client, auth_headers, monkeypatch):
    monkeypatch.setattr('app.modules.tools.common.is_tool_active', lambda _name: 'active')
    response = client.get('/rmon/dashboard', headers=auth_headers(1, 1))
    document = _document(response)

    required_controls = {
        'new-smon-name',
        'new-smon-place',
        'check_type',
        'new-smon-interval',
        'new-smon-ip',
        'new-smon-timeout',
        'new-smon-retries',
        'new-smon-url',
        'new-smon-status-code',
        'new-smon-dns_record_type',
        'new-smon-username',
        'new-smon-password',
        'new-smon-priority',
        'new-smon-runbook',
    }
    option_values = {attrs.get('value') for attrs in document.find_all(tag='option')}

    assert required_controls <= set(document.ids)
    assert {'http', 'tcp', 'dns', 'ping', 'smtp', 'rabbitmq'} <= option_values


@pytest.mark.ui
def test_status_page_editor_contains_both_steps_and_required_fields(client, auth_headers, monkeypatch):
    monkeypatch.setattr('app.modules.tools.common.is_tool_active', lambda _name: 'active')
    response = client.get('/rmon/status-page', headers=auth_headers(1, 1))
    document = _document(response)

    expected_ids = {
        'create-status-page-step-1',
        'create-status-page-step-1-overview',
        'new-status-page-name',
        'new-status-page-slug',
        'create-status-page-step-2',
        'create-status-page-step-2-overview',
        'new-status-page-desc',
        'new-status-page-style',
        'all-checks',
    }
    assert expected_ids <= set(document.ids)


@pytest.mark.ui
def test_nettools_forms_submit_to_the_expected_endpoints(client, auth_headers):
    document = _document(client.get('/nettools', headers=auth_headers(1, 1)))

    expected_actions = {
        'nettools_icmp_form': '/nettools/icmp',
        'nettools_telnet_form': '/nettools/tcp',
        'nettools_nslookup_form': '/nettools/dns',
        'nettools_portscanner_form': '/nettools/portscan',
        'nettools_whois_form': '/nettools/whois',
        'nettools_ipcalc_form': '/nettools/ipcalc',
    }
    for form_id, action in expected_actions.items():
        form = document.find(tag='form', element_id=form_id)
        assert form is not None
        assert form['method'] == 'post'
        assert form['action'] == action

    _assert_unique_ids(document, set(expected_actions) | {'nettools_ipcalc_submit'})


@pytest.mark.ui
def test_agent_and_channel_editors_use_their_frontend_contract_ids(client, auth_headers, monkeypatch):
    monkeypatch.setattr('app.modules.tools.common.is_tool_active', lambda _name: 'active')

    agents = _document(client.get('/rmon/agent', headers=auth_headers(1, 1)))
    _assert_unique_ids(
        agents,
        {
            'add-agent-page-overview',
            'add-region-page-overview',
            'add-country-page-overview',
        },
    )

    channels = _document(client.get('/channel/load', headers=auth_headers(1, 1)))
    expected_channel_controls = {
        'add-telegram-button',
        'add-slack-button',
        'add-pd-button',
        'add-mm-button',
        'add-incidentrelay-button',
        'add-email-button',
    }
    assert expected_channel_controls <= set(channels.ids)
    _assert_unique_ids(channels, expected_channel_controls)


@pytest.mark.ui
def test_ui_templates_and_language_catalogs_compile(app):
    templates = (
        'login.html',
        'ovw.html',
        'admin.html',
        'channel.html',
        'nettools.html',
        'smon/dashboard.html',
        'smon/agents.html',
        'smon/history.html',
        'smon/manage_status_page.html',
    )

    with app.app_context():
        for template in templates:
            assert app.jinja_env.get_template(template)
        for language in SUPPORTED_LANGUAGES:
            assert app.jinja_env.get_template(f'languages/{language}.html')


@pytest.mark.ui
@pytest.mark.parametrize('path', ('/login',) + PRIVATE_UI_PATHS)
def test_pages_support_mobile_viewport_and_load_shared_interactions(client, auth_headers, monkeypatch, path):
    monkeypatch.setattr('app.modules.tools.common.is_tool_active', lambda _name: 'active')
    document = _document(client.get(path, headers=auth_headers(1, 1)))
    viewport = [a for a in document.find_all(tag='meta') if a.get('name') == 'viewport']
    assert len(viewport) == 1
    assert 'width=device-width' in viewport[0]['content']
    assert 'user-scalable=no' not in viewport[0]['content']
    assert {'/static/css/ux.css', '/static/js/ux.js'} <= document.local_assets


@pytest.mark.ui
def test_login_controls_have_labels_password_manager_hints_and_live_errors(client):
    document = _document(client.get('/login'))
    assert {'login', 'pass'} <= {a.get('for') for a in document.find_all(tag='label')}
    assert document.find(element_id='login')['autocomplete'] == 'username'
    assert document.find(element_id='pass')['autocomplete'] == 'current-password'
    toggle, = document.find_all(tag='button', class_name='password-toggle')
    assert toggle['type'] == 'button'
    assert toggle['aria-controls'] == 'pass'
    assert toggle['aria-pressed'] == 'false'
    assert toggle['aria-label']
    assert document.find(element_id='wrong-login')['role'] == 'alert'


@pytest.mark.ui
def test_app_shell_exposes_keyboard_navigation_and_correct_overview_links(client, auth_headers):
    document = _document(client.get('/overview', headers=auth_headers(1, 1)))
    toggle = document.find(tag='button', element_id='menu-toggle')
    assert document.find(tag='aside', element_id=toggle['aria-controls'])
    assert document.find(tag='main', element_id='main-content')['tabindex'] == '-1'
    assert document.find_all(tag='a', class_name='skip-link')[0]['href'] == '#main-content'
    links = {a.get('href') for a in document.find_all(tag='a')}
    assert {'/admin#servers', '/admin#users', '/admin#groups', '/admin#tools', '/logs/internal'} <= links
    assert not any(link and link.startswith('/app/') for link in links)
    assert document.find(tag='button', element_id='show-user-settings-button')
    for button in document.find_all(tag='button', class_name='icon-button'):
        assert button.get('aria-label') or button.get('id') == 'show-user-settings-button'


@pytest.mark.ui
def test_status_editor_preview_matches_public_route(client, auth_headers, monkeypatch):
    monkeypatch.setattr('app.modules.tools.common.is_tool_active', lambda _name: 'active')
    document = _document(client.get('/rmon/status-page', headers=auth_headers(1, 1)))
    assert document.find(element_id='status-page-url-preview')['data-prefix'] == '/rmon/status/'
    assert document.find(element_id='status-pages-empty') is not None
    assert {'new-status-page-name', 'new-status-page-slug'} <= {
        a.get('for') for a in document.find_all(tag='label')
    }


@pytest.mark.ui
@pytest.mark.parametrize('language', SUPPORTED_LANGUAGES)
def test_ux_messages_are_translated_consistently(app, language):
    with app.app_context():
        english = app.jinja_env.get_template('languages/en.html').module.ux
        translated = app.jinja_env.get_template(f'languages/{language}.html').module.ux
    assert translated.keys() == english.keys()
    assert all(isinstance(message, str) and message.strip() for message in translated.values())


@pytest.mark.ui
def test_check_editor_fixture_matches_the_real_rendered_template(app):
    """Keep the DOM used by JavaScript workflow tests aligned with the actual form."""
    with app.test_request_context():
        env = app.jinja_env
        macros = env.get_template('include/input_macros.html').module
        rendered = env.get_template('include/smon/add_form.html').render(
            lang=env.get_template('languages/en.html').module, chosen_lang='en',
            input=macros.input, select=macros.select, checkbox=macros.checkbox,
            telegrams=[], slacks=[], pds=[], mms=[], emails=[], incidentrelay=[],
        )
    fixture = Path(__file__).resolve().parents[1] / 'frontend/fixtures/check-editor.html'
    assert rendered.strip() == fixture.read_text(encoding='utf-8').strip()
    document = HtmlDocument()
    document.feed(rendered)
    _assert_unique_ids(document, set(document.ids))
    assert len([a for a in document.find_all(tag='section') if a.get('role') == 'tabpanel']) == 3
    labels = {label.get('for') for label in document.find_all(tag='label')}
    assert {'new-smon-name', 'new-smon-url', 'new-smon-place', 'check_type',
            'new-smon-port', 'new-smon-interval', 'new-smon-timeout'} <= labels
    for tab in document.find_all(tag='button'):
        if tab.get('role') == 'tab':
            panel = document.find(element_id=tab['aria-controls'])
            assert panel['aria-labelledby'] == tab['id']


@pytest.mark.ui
@pytest.mark.parametrize('language', SUPPORTED_LANGUAGES)
def test_check_editor_messages_are_translated_consistently(app, language):
    with app.app_context():
        english = app.jinja_env.get_template('languages/en.html').module.check_editor
        translated = app.jinja_env.get_template(f'languages/{language}.html').module.check_editor
    assert translated.keys() == english.keys()
    assert all(isinstance(message, str) and message.strip() for message in translated.values())
