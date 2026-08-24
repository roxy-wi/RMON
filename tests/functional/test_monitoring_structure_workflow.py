import uuid

import pytest

from app.modules.db.db_model import Country, Region, SmonGroup


@pytest.mark.functional
def test_country_and_region_crud_workflow(client, auth_headers):
    suffix = uuid.uuid4().hex
    country_response = client.post(
        '/api/v1.0/rmon/country',
        json={
            'name': f'country-{suffix}', 'description': 'functional country',
            'enabled': True, 'shared': False, 'regions': [], 'group_id': 1,
        },
        headers=auth_headers(2, 1),
    )
    assert country_response.status_code == 201
    country_id = country_response.get_json()['id']

    region_response = client.post(
        '/api/v1.0/rmon/region',
        json={
            'name': f'region-{suffix}', 'description': 'functional region',
            'enabled': True, 'shared': False, 'agents': [],
            'country_id': country_id, 'group_id': 1,
        },
        headers=auth_headers(2, 1),
    )
    assert region_response.status_code == 201
    region_id = region_response.get_json()['id']

    region_get_response = client.get(
        f'/api/v1.0/rmon/region/{region_id}', headers=auth_headers(2, 1)
    )
    assert region_get_response.status_code == 200
    assert region_get_response.get_json()['country_id'] == country_id

    countries_response = client.get(
        '/api/v1.0/rmon/countries', headers=auth_headers(2, 1)
    )
    regions_response = client.get(
        '/api/v1.0/rmon/regions', headers=auth_headers(2, 1)
    )
    assert country_id in {country['id'] for country in countries_response.get_json()}
    assert region_id in {region['id'] for region in regions_response.get_json()}

    assert client.delete(
        f'/api/v1.0/rmon/region/{region_id}', headers=auth_headers(2, 1)
    ).status_code == 204
    assert client.delete(
        f'/api/v1.0/rmon/country/{country_id}', headers=auth_headers(2, 1)
    ).status_code == 204
    assert not Region.select().where(Region.id == region_id).exists()
    assert not Country.select().where(Country.id == country_id).exists()


@pytest.mark.functional
def test_check_group_crud_workflow(client, auth_headers):
    suffix = uuid.uuid4().hex
    create_response = client.post(
        '/api/v1.0/rmon/check-group',
        json={'name': f'check-group-{suffix}', 'group_id': 1},
        headers=auth_headers(2, 1),
    )
    assert create_response.status_code == 201
    check_group_id = create_response.get_json()['id']

    get_response = client.get(
        f'/api/v1.0/rmon/check-group/{check_group_id}', headers=auth_headers(2, 1)
    )
    assert get_response.status_code == 200
    assert get_response.get_json()['name'] == f'check-group-{suffix}'

    update_response = client.put(
        f'/api/v1.0/rmon/check-group/{check_group_id}',
        json={'name': f'updated-check-group-{suffix}', 'group_id': 1},
        headers=auth_headers(2, 1),
    )
    assert update_response.status_code == 201
    assert SmonGroup.get_by_id(check_group_id).name == f'updated-check-group-{suffix}'

    list_response = client.get(
        '/api/v1.0/rmon/check-groups', headers=auth_headers(2, 1)
    )
    assert check_group_id in {group['id'] for group in list_response.get_json()}

    delete_response = client.delete(
        f'/api/v1.0/rmon/check-group/{check_group_id}', headers=auth_headers(2, 1)
    )
    assert delete_response.status_code == 204
    assert not SmonGroup.select().where(SmonGroup.id == check_group_id).exists()
