from app.modules.roxywi.exception import RoxywiPermissionError


def ensure_group_management(actor_role, active_group, target_group):
    actor_role = int(actor_role)
    if actor_role == 1:
        return
    if actor_role > 2 or int(active_group) != int(target_group):
        raise RoxywiPermissionError('You do not have permission to manage this group')


def ensure_role_assignment(actor_role, target_role):
    actor_role = int(actor_role)
    target_role = int(target_role)
    if actor_role == 1:
        return
    if actor_role > 2 or target_role == 1 or target_role < actor_role:
        raise RoxywiPermissionError('You do not have permission to assign this role')


def ensure_target_role(actor_role, target_role):
    actor_role = int(actor_role)
    target_role = int(target_role)
    if actor_role != 1 and target_role < actor_role:
        raise RoxywiPermissionError('You do not have permission to manage this user')
