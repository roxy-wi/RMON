from typing import Union

from app.modules.db.db_model import Region, SmonAgent
from app.modules.db.common import out_error
from app.modules.roxywi.class_models import RegionRequest
from app.modules.roxywi.exception import RoxywiResourceNotFound


def select_regions_by_group(group_id: int) -> Region:
    try:
        return Region.select().where(
            (Region.group_id == group_id) |
            (Region.shared == True)
        ).execute()
    except Exception as e:
        out_error(e)


def get_region_with_group(region_id: int, group_id: int) -> Region:
    try:
        return Region.get(Region.id == region_id, ((Region.group_id == group_id) | (Region.shared == True)))
    except Region.DoesNotExist:
        raise RoxywiResourceNotFound
    except Exception as e:
        out_error(e)


def create_region(body: RegionRequest) -> int:
    try:
        last_id = Region.insert(**body.model_dump(mode='json', exclude={'agents'})).execute()
        return last_id
    except Exception as e:
        out_error(e)


def update_region(body: RegionRequest, region_id: int) -> None:
    try:
        Region.update(**body.model_dump(mode='json', exclude={'agents'}, exclude_none=True)).where(Region.id == region_id).execute()
    except Region.DoesNotExist:
        raise RoxywiResourceNotFound
    except Exception as e:
        out_error(e)


def add_region_to_country(region_id: int, country_id: Union[int, None]) -> None:
    try:
        Region.update(country_id=country_id).where(Region.id == region_id).execute()
    except Region.DoesNotExist:
        raise RoxywiResourceNotFound
    except Exception as e:
        out_error(e)


def delete_region(region_id: int) -> None:
    try:
        Region.delete().where(Region.id == region_id).execute()
    except Region.DoesNotExist:
        raise RoxywiResourceNotFound
    except Exception as e:
        out_error(e)


def get_regions_by_country(country_id: int) -> Region:
    try:
        return Region.select().where(Region.country_id == country_id).execute()
    except Region.DoesNotExist:
        raise RoxywiResourceNotFound
    except Exception as e:
        out_error(e)


def get_enabled_regions_by_country_with_group(country_id: int, group_id: int) -> Region:
    try:
        return Region.select().join(SmonAgent).where(
            (Region.country_id == country_id) & (Region.enabled == True) & ((Region.group_id == group_id) | (Region.shared == True))
        ).group_by(Region.id).execute()
    except Region.DoesNotExist:
        raise RoxywiResourceNotFound
    except Exception as e:
        out_error(e)
