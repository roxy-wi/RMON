from app.modules.db.db_model import mysql_enable, connect, Server, SystemInfo
from app.modules.db.common import out_error


def add_server(hostname, ip, group, shared, enable, master, cred, port, desc, haproxy, nginx, apache, firewall):
	try:
		server_id = Server.insert(
			hostname=hostname, ip=ip, groups=group, shared=shared, enable=enable, master=master, cred=cred,
			port=port, desc=desc, haproxy=haproxy, nginx=nginx, apache=apache, firewall_enable=firewall
		).execute()
		return server_id
	except Exception as e:
		out_error(e)
		return False


def delete_server(server_id):
	try:
		server_for_delete = Server.delete().where(Server.server_id == server_id)
		server_for_delete.execute()
	except Exception as e:
		out_error(e)
	else:
		return True


def update_server(hostname, group, enable, server_id, cred, port, desc):
	try:
		server_update = Server.update(
			hostname=hostname, groups=group, enable=enable, cred=cred, port=port, desc=desc
		).where(Server.server_id == server_id)
		server_update.execute()
	except Exception as e:
		out_error(e)


def get_hostname_by_server_ip(server_ip):
	try:
		hostname = Server.get(Server.ip == server_ip)
	except Exception as e:
		return out_error(e)
	else:
		return hostname.hostname


def select_server_by_name(name):
	try:
		ip = Server.get(Server.hostname == name)
	except Exception as e:
		return out_error(e)
	else:
		return ip.ip


def insert_system_info(
	server_id: int, os_info: str, sys_info: dict, cpu: dict, ram: dict, network: dict, disks: dict
):
	try:
		SystemInfo.insert(
			server_id=server_id, os_info=os_info, sys_info=sys_info, cpu=cpu, ram=ram, network=network, disks=disks
		).on_conflict('replace').execute()
	except Exception as e:
		out_error(e)


def delete_system_info(server_id: int):
	try:
		SystemInfo.delete().where(SystemInfo.server_id == server_id).execute()
	except Exception as e:
		out_error(e)


def select_one_system_info(server_id: int):
	try:
		return SystemInfo.select().where(SystemInfo.server_id == server_id).execute()
	except Exception as e:
		out_error(e)


def is_system_info(server_id):
	try:
		query_res = SystemInfo.get(SystemInfo.server_id == server_id).server_id
	except Exception:
		return True
	else:
		if query_res:
			return True
		else:
			return False


def select_os_info(server_id):
	try:
		query_res = SystemInfo.get(SystemInfo.server_id == server_id).os_info
	except Exception as e:
		out_error(e)
		return
	else:
		return query_res


def update_firewall(serv):
	query = Server.update(firewall_enable=1).where(Server.ip == serv)
	try:
		query.execute()
		return True
	except Exception as e:
		out_error(e)
		return False


def return_firewall(serv):
	try:
		query_res = Server.get(Server.ip == serv).firewall_enable
	except Exception:
		return False
	else:
		return True if query_res == 1 else False


def update_server_pos(pos, server_id) -> str:
	query = Server.update(pos=pos).where(Server.server_id == server_id)
	try:
		query.execute()
		return 'ok'
	except Exception as e:
		out_error(e)


def is_serv_protected(serv):
	try:
		query_res = Server.get(Server.ip == serv)
	except Exception:
		return ""
	else:
		return True if query_res.protected else False


def select_server_ip_by_id(server_id: int) -> str:
	try:
		server_ip = Server.get(Server.server_id == server_id).ip
	except Exception as e:
		return out_error(e)
	else:
		return server_ip


def select_server_id_by_ip(server_ip):
	try:
		server_id = Server.get(Server.ip == server_ip).server_id
	except Exception:
		return None
	else:
		return server_id


def select_servers(**kwargs):
	conn = connect()
	cursor = conn.cursor()

	if mysql_enable == '1':
		sql = """select * from `servers` where `enable` = 1 ORDER BY servers.groups """

		if kwargs.get("server") is not None:
			sql = """select * from `servers` where `ip` = '{}' """.format(kwargs.get("server"))
		if kwargs.get("full") is not None:
			sql = """select * from `servers` ORDER BY hostname """
		if kwargs.get("id"):
			sql = """select * from `servers` where `id` = '{}' """.format(kwargs.get("id"))
	else:
		sql = """select * from servers where enable = '1' ORDER BY servers.groups """

		if kwargs.get("server") is not None:
			sql = """select * from servers where ip = '{}' """.format(kwargs.get("server"))
		if kwargs.get("full") is not None:
			sql = """select * from servers ORDER BY hostname """
		if kwargs.get("id"):
			sql = """select * from servers where id = '{}' """.format(kwargs.get("id"))

	try:
		cursor.execute(sql)
	except Exception as e:
		out_error(e)
	else:
		return cursor.fetchall()


def get_dick_permit(group_id, **kwargs):
	only_group = kwargs.get('only_group')
	disable = 'enable = 1'
	ip = ''
	conn = connect()
	cursor = conn.cursor()

	if kwargs.get('shared'):
		shared = ""
	else:
		shared = "and shared = 0"
	if kwargs.get('disable') == 0:
		disable = '(enable = 1 or enable = 0)'
	if kwargs.get('ip'):
		ip = "and ip = '%s'" % kwargs.get('ip')

	try:
		if mysql_enable == '1':
			if group_id == 1 and not only_group:
				sql = f" select * from `servers` where {disable} {shared} {ip} order by `pos` asc"
			else:
				sql = f" select * from `servers` where `groups` = {group_id} and ({disable}) {shared} {ip} order by `pos` asc"
		else:
			if group_id == 1 and not only_group:
				sql = f" select * from servers where {disable} {shared} {ip} order by pos"
			else:
				sql = f" select * from servers where groups = '{group_id}' and ({disable}) {shared} {ip} order by pos"

	except Exception as e:
		raise Exception(f'error: {e}')

	try:
		cursor.execute(sql)
	except Exception as e:
		out_error(e)
	else:
		return cursor.fetchall()


def is_master(ip, **kwargs):
	conn = connect()
	cursor = conn.cursor()
	if kwargs.get('master_slave'):
		sql = """ select master.hostname, master.ip, slave.hostname, slave.ip
		from servers as master
		left join servers as slave on master.id = slave.master
		where slave.master > 0 """
	else:
		sql = """ select slave.ip, slave.hostname from servers as master
		left join servers as slave on master.id = slave.master
		where master.ip = '%s' """ % ip
	try:
		cursor.execute(sql)
	except Exception as e:
		out_error(e)
	else:
		return cursor.fetchall()
