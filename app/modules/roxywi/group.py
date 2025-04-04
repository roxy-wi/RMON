import app.modules.db.group as group_sql


def update_group(group_id: int, group_name: str, desc: str) -> None:
    try:
        group_sql.update_group(group_name, desc, group_id)
    except Exception as e:
        raise Exception(e)


def delete_group(group_id: int) -> None:
    group_sql.delete_group(group_id)
