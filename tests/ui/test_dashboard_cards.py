from collections import Counter

import pytest

from tests.ui.test_client_checks import Document


@pytest.mark.parametrize('locale', ['en', 'ru', 'fr', 'pt-br'])
def test_cards_dashboard_is_localized_and_has_unique_controls(app, client, auth_headers, monkeypatch, locale):
    monkeypatch.setattr('app.modules.tools.common.is_tool_active', lambda name: 'active')
    client.set_cookie('lang', locale)
    response = client.get('/rmon/dashboard', headers=auth_headers(1, 1))
    assert response.status_code == 200
    text = response.get_data(as_text=True)
    catalog = app.jinja_env.get_template(f'languages/dashboard_{locale}.html').module.dashboard
    assert catalog['heading'] in text and catalog['auto'] in text
    assert 'data-endpoint="/rmon/dashboard/data"' in text
    assert 'window.onload' not in text
    assert not [key for key, count in Counter(Document(text).ids).items() if count > 1]


def test_dashboard_catalogs_share_keys(app):
    catalogs = [app.jinja_env.get_template(f'languages/dashboard_{locale}.html').module.dashboard for locale in ('en','ru','fr','pt-br')]
    assert all(set(catalog) == set(catalogs[0]) for catalog in catalogs)
    assert all(value for catalog in catalogs for value in catalog.values())


def test_dashboard_viewer_has_no_create_button(client, auth_headers, monkeypatch):
    monkeypatch.setattr('app.modules.tools.common.is_tool_active', lambda name: 'active')
    text = client.get('/rmon/dashboard', headers=auth_headers(3, 1)).get_data(as_text=True)
    assert 'data-can-edit="false"' in text
    assert 'onclick="openSmonDialog(\'http\')"' not in text
