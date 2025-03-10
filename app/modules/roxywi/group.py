import app.modules.db.group as group_sql
import app.modules.roxywi.common as roxywi_common


def update_group(group_id: int, group_name: str, desc: str) -> None:
    try:
        group_sql.update_group(group_name, desc, group_id)
        roxywi_common.logger(f'The {group_name} has been updated', roxywi=1, login=1)
    except Exception as e:
        raise Exception(e)


def delete_group(group_id: int) -> None:
    group_name = group_sql.get_group(group_id).name

    group_sql.delete_group(group_id)
    roxywi_common.logger(f'The {group_name} has been deleted', roxywi=1, login=1)
