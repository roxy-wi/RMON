from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

import pytest
from flask import render_template


class Document(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.ids = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if 'id' in values:
            self.ids.append(values['id'])


@pytest.mark.ui
@pytest.mark.parametrize('language', ['en', 'ru', 'fr', 'pt-br'])
def test_client_workspace_renders_localized_controls_and_navigation(client, auth_headers, app, language):
    client.set_cookie('lang', language)
    response = client.get('/client-checks', headers=auth_headers(2, 1))
    assert response.status_code == 200
    assert response.headers['Cache-Control'] == 'no-store'
    text = response.get_data(as_text=True)
    strings = app.jinja_env.get_template(f'languages/{language}.html').module.client_checks
    assert strings['title'] in text
    assert all(count == 1 for count in Counter(Document(text).ids).values())
    assert {'cc-project-form', 'cc-definition-form', 'cc-key-form', 'cc-report-form', 'cc-chart'} <= set(Document(text).ids)
    assert 'href="/client-checks"' in text
    assert 'data-api="/api/v1.0/client/projects"' in text
    assert 'data-can-edit="true"' in text
    assert 'cc-preset-labels' in text
    assert strings['preset_page_load_name']
    assert strings['preset_http_reachability_metric_duration_ms']


@pytest.mark.ui
def test_client_workspace_viewer_has_reports_without_write_controls(client, auth_headers):
    response = client.get('/client-checks', headers=auth_headers(3, 1))
    assert response.status_code == 200
    text = response.get_data(as_text=True)
    ids = set(Document(text).ids)
    assert 'cc-report-form' in ids and 'cc-project-form' not in ids and 'cc-new-key' not in ids
    assert 'data-can-edit="false"' in text


@pytest.mark.ui
def test_client_workspace_requires_login_and_handles_unknown_locale(client, auth_headers):
    assert client.get('/client-checks').status_code == 302
    client.set_cookie('lang', '../../anything')
    response = client.get('/client-checks', headers=auth_headers(2, 1))
    assert response.status_code == 200
    assert 'Client checks' in response.get_data(as_text=True)


@pytest.mark.ui
def test_client_catalogs_have_identical_keys_and_browser_fixture_matches_template(app):
    with app.test_request_context():
        catalogs = [app.jinja_env.get_template(f'languages/{language}.html').module.client_checks for language in ('en', 'ru', 'fr', 'pt-br')]
        assert all(set(catalog) == set(catalogs[0]) for catalog in catalogs)
        assert all(isinstance(value, str) and value for catalog in catalogs for value in catalog.values())
        rendered = '\n'.join(line.rstrip() for line in render_template('client/workspace.html', c=catalogs[0], can_edit=True).splitlines()) + '\n'
    path = Path(__file__).parents[1] / 'frontend/fixtures/client-checks.html'
    assert path.read_text(encoding='utf-8') == rendered
