import app.modules.server.server as server_mod
import app.modules.roxy_wi_tools as roxy_wi_tools
import app.modules.roxywi.common as roxywi_common

get_config_var = roxy_wi_tools.GetConfigVar()


def roxy_wi_log() -> list:
	log_path = get_config_var.get_config_var('main', 'log_path')
	user_group_id = roxywi_common.get_user_group(id=1)

	if user_group_id != 1:
		user_group = roxywi_common.get_user_group()
		group_grep = f'|grep "group: {user_group}"'
	else:
		group_grep = ''
	cmd = f"find {log_path}/rmon.log -type f -exec stat --format '%Y :%y %n' '{{}}' \; | sort -nr | cut -d: -f2- " \
			f"| head -1 |awk '{{print $4}}' |xargs tail {group_grep}|sort -r"
	try:
		output, stderr = server_mod.subprocess_execute(cmd)
		return output
	except Exception:
		return ['']
