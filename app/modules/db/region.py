from app.modules.db.db_model import Region
from app.modules.db.common import out_error
from app.modules.roxywi.class_models import RegionRequest
from app.modules.roxywi.exception import RoxywiResourceNotFound


def select_regions() -> Region:
    try:
        return Region.select().execute()
    except Exception as e:
        out_error(e)


def select_regions_by_group(group_id: int) -> Region:
    try:
        return Region.select().where(Region.group_id == group_id).execute()
    except Exception as e:
        out_error(e)


def get_region(region_id: int) -> Region:
    try:
        return Region.get(Region.id == region_id)
    except Region.DoesNotExist:
        raise RoxywiResourceNotFound
    except Exception as e:
        out_error(e)


def get_region_with_group(region_id: int, group_id: int) -> Region:
    try:
        return Region.get(Region.id == region_id, Region.group_id == group_id)
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
        Region.update(**body.model_dump(mode='json', exclude={'agents'})).where(Region.id == region_id).execute()
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
