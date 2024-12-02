from app.modules.db.db_model import Country, Region
from app.modules.db.common import out_error
from app.modules.roxywi.class_models import CountryRequest
from app.modules.roxywi.exception import RoxywiResourceNotFound


def select_countries_by_group(group_id: int) -> Country:
    try:
        return Country.select().where(
            (Country.group_id == group_id) |
            (Country.shared == True)
        ).execute()
    except Exception as e:
        out_error(e)


def select_enabled_countries_by_group(group_id: int) -> Country:
    try:
        return Country.select().join(Region).where(
            (Country.enabled == True) &
            ((Country.group_id == group_id) |
            (Country.shared == True))
        ).group_by(Country.id).execute()
    except Exception as e:
        out_error(e)


def get_country_with_group(country_id: int, group_id: int) -> Country:
    try:
        return Country.get((Country.id == country_id) & ((Country.group_id == group_id) | (Country.shared == True)))
    except Country.DoesNotExist:
        raise RoxywiResourceNotFound
    except Exception as e:
        out_error(e)


def create_country(body: CountryRequest) -> int:
    try:
        last_id = Country.insert(**body.model_dump(mode='json', exclude={'regions'})).execute()
        return last_id
    except Exception as e:
        out_error(e)


def update_country(body: CountryRequest, country_id: int) -> None:
    try:
        Country.update(**body.model_dump(mode='json', exclude={'regions'})).where(Country.id == country_id).execute()
    except Country.DoesNotExist:
        raise RoxywiResourceNotFound
    except Exception as e:
        out_error(e)


def delete_country(country_id: int) -> None:
    try:
        Country.delete().where(Country.id == country_id).execute()
    except Country.DoesNotExist:
        raise RoxywiResourceNotFound
    except Exception as e:
        out_error(e)
