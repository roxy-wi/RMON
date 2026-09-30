from collections import Counter

import pytest

from tests.functional.test_check_detail import detail_checks
from tests.ui.test_client_checks import Document


@pytest.mark.parametrize('locale', ['en', 'ru', 'fr', 'pt-br'])
def test_detail_has_localized_sections_and_one_chart(app, client, auth_headers, detail_checks, locale):
    multi, _ = detail_checks()
    client.set_cookie('lang', locale)
    response = client.get(f'/rmon/dashboard/{multi.id}/2', headers=auth_headers(1, 1))
    assert response.status_code == 200
    text = response.get_data(as_text=True)
    catalog = app.jinja_env.get_template(f'languages/check_detail_{locale}.html').module.check_detail
    assert catalog['overview'] in text and catalog['diagnostic'] in text
    assert text.count('<canvas') == 1
    assert 'window.onload' not in text and 'EventSource' not in text
    assert 'Store &lt;script&gt;' in text
    assert not [key for key, count in Counter(Document(text).ids).items() if count > 1]
    assert f'data-endpoint="/rmon/dashboard/{multi.id}/2/data"' in text


def test_viewer_gets_read_only_detail(client, auth_headers, detail_checks):
    multi, _ = detail_checks()
    text = client.get(f'/rmon/dashboard/{multi.id}/2', headers=auth_headers(3, 1)).get_data(as_text=True)
    assert 'data-can-edit="false"' in text
    assert 'id="cd-edit"' not in text and 'id="smon-add-table"' not in text


def test_detail_catalogs_have_matching_keys(app):
    catalogs = [app.jinja_env.get_template(f'languages/check_detail_{locale}.html').module.check_detail
                for locale in ('en','ru','fr','pt-br')]
    assert all(set(catalog) == set(catalogs[0]) for catalog in catalogs)
    assert all(value for catalog in catalogs for value in catalog.values())
