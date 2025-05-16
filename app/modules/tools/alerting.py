import json
from typing import Union

import pika
import pdpyras
import telebot
from telebot import apihelper
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import requests
from flask import render_template, abort, g

import app.modules.db.sql as sql
import app.modules.db.smon as smon_sql
import app.modules.db.user as user_sql
import app.modules.db.group as group_sql
import app.modules.db.channel as channel_sql
import app.modules.common.common as common
import app.modules.roxywi.common as roxywi_common


def send_message_to_rabbit(message: str, **kwargs) -> None:
	rabbit_user = sql.get_setting('rabbitmq_user')
	rabbit_password = sql.get_setting('rabbitmq_password')
	rabbit_host = sql.get_setting('rabbitmq_host')
	rabbit_port = sql.get_setting('rabbitmq_port')
	rabbit_vhost = sql.get_setting('rabbitmq_vhost')
	if kwargs.get('rabbit_queue'):
		rabbit_queue = kwargs.get('rabbit_queue')
	else:
		rabbit_queue = sql.get_setting('rabbitmq_queue')

	credentials = pika.PlainCredentials(rabbit_user, rabbit_password)
	parameters = pika.ConnectionParameters(
		rabbit_host,
		rabbit_port,
		rabbit_vhost,
		credentials
	)

	connection = pika.BlockingConnection(parameters)
	channel = connection.channel()
	channel.queue_declare(queue=rabbit_queue)
	channel.basic_publish(exchange='', routing_key=rabbit_queue, body=message)

	connection.close()


def send_email_to_server_group(subject: str, mes: str, level: str, group_id: int) -> None:
	if not sql.get_setting('mail_enabled'):
		return
	try:
		users_email = user_sql.select_users_emails_by_group_id(group_id)

		for user_email in users_email:
			send_email(user_email.email, subject, f'{level}: {mes}')
	except Exception as e:
		roxywi_common.logger(f'Unable to send email: {e}', "error")


def send_email(email_to: str, subject: str, message: str) -> None:
	from smtplib import SMTP

	try:
		from email.MIMEText import MIMEText
	except Exception:
		from email.mime.text import MIMEText

	mail_ssl = sql.get_setting('mail_ssl', group_id=1)
	mail_from = sql.get_setting('mail_from', group_id=1)
	mail_smtp_host = sql.get_setting('mail_smtp_host', group_id=1)
	mail_smtp_port = sql.get_setting('mail_smtp_port', group_id=1)
	mail_smtp_user = sql.get_setting('mail_smtp_user', group_id=1)
	mail_smtp_password = sql.get_setting('mail_smtp_password', group_id=1).replace("'", "")
	rmon_name = sql.get_setting('rmon_name')

	msg = MIMEText(message)
	msg['Subject'] = f'{rmon_name}: {subject}'
	msg['From'] = f'{rmon_name} <{mail_from}>'
	msg['To'] = email_to

	try:
		smtp_obj = SMTP(mail_smtp_host, mail_smtp_port)
		if mail_ssl:
			smtp_obj.starttls()
		smtp_obj.login(mail_smtp_user, mail_smtp_password)
		smtp_obj.send_message(msg)
	except Exception as e:
		roxywi_common.logger(f'unable to send email: {e}', "error")


def telegram_send_mess(mess, o_level, **kwargs):
	token_bot = ''
	channel_name = ''
	runbook = ''
	rmon_name = sql.get_setting('rmon_name')
	if o_level == 'info':
		level = '\U0001F7E2 info'
	elif o_level == 'warning':
		level = '\U0001F7E1 warning'
	else:
		level = f'\U0001F534 {o_level}'
	if kwargs.get('channel_id') == 0:
		return

	if kwargs.get('channel_id'):
		telegrams = channel_sql.get_receiver_by_id('telegram', kwargs.get('channel_id'))
	else:
		telegrams = channel_sql.get_receiver_by_ip('telegram', kwargs.get('ip'))

	proxy = sql.get_setting('proxy')

	for telegram in telegrams:
		token_bot = telegram.token
		channel_name = telegram.chanel_name

	if token_bot == '' or channel_name == '':
		mess = "Can't send message. Add Telegram channel before use alerting at this servers group"
		roxywi_common.logger(mess, "error")

	if proxy is not None and proxy != '' and proxy != 'None':
		apihelper.proxy = {'https': proxy}

	if o_level != 'info':
		try:
			check = smon_sql.get_one_multi_check(kwargs.get('multi_check_id'))
			if check.runbook:
				runbook = f'.\n Runbook: {check.runbook}'
		except Exception as e:
			roxywi_common.logger(f'unable to get check: {e}')

	try:
		bot = telebot.TeleBot(token=token_bot)
		bot.send_message(chat_id=channel_name, text=f'[{rmon_name}] {level}: {mess} {runbook}')
		return 'ok'
	except Exception as e:
		roxywi_common.logger(str(e), "error")
		raise Exception(f'{e}')


def slack_send_mess(mess, level, **kwargs):
	slack_token = ''
	channel_name = ''
	runbook = ''
	rmon_name = sql.get_setting('rmon_name')

	if kwargs.get('channel_id') == 0:
		return

	if kwargs.get('channel_id'):
		slacks = channel_sql.get_receiver_by_id('slack', kwargs.get('channel_id'))
	else:
		slacks = channel_sql.get_receiver_by_ip('slack', kwargs.get('ip'))

	proxy = sql.get_setting('proxy')

	for slack in slacks:
		slack_token = slack.token
		channel_name = slack.chanel_name

	if proxy is not None and proxy != '' and proxy != 'None':
		proxies = dict(https=proxy, http=proxy)
		client = WebClient(token=slack_token, proxies=proxies)
	else:
		client = WebClient(token=slack_token)

	if level != 'info':
		try:
			check = smon_sql.get_one_multi_check(kwargs.get('multi_check_id'))
			if check.runbook:
				runbook = f'.\n Runbook: {check.runbook}'
		except Exception as e:
			roxywi_common.logger(f'unable to get check: {e}')

	try:
		client.chat_postMessage(channel=f'#{channel_name}', text=f'[{rmon_name}] {level}: {mess} {runbook}')
		return 'ok'
	except SlackApiError as e:
		roxywi_common.logger(str(e), "error")
		raise Exception(f'{e}')


def pd_send_mess(mess, level, **kwargs):
	token = ''
	runbook = ''
	rmon_name = sql.get_setting('rmon_name')

	if kwargs.get('channel_id') == 0:
		return

	if kwargs.get('channel_id'):
		try:
			pds = channel_sql.get_receiver_by_id('pd', kwargs.get('channel_id'))
		except Exception as e:
			roxywi_common.logger(str(e), "error")
	else:
		try:
			pds = channel_sql.get_receiver_by_ip('pd', kwargs.get('ip'))
		except Exception as e:
			roxywi_common.logger(str(e), "error")

	for pd in pds:
		token = pd.token

	try:
		proxy = sql.get_setting('proxy')
		session = pdpyras.EventsAPISession(token)
		dedup_key = f'{kwargs.get("multi_check_id")} {kwargs.get("agent_name")}'
	except Exception as e:
		roxywi_common.logger(str(e), "error")
		raise Exception(f'{e}')

	if proxy is not None and proxy != '' and proxy != 'None':
		proxies = dict(https=proxy, http=proxy)
		session.proxies.update(proxies)

	if level != 'info':
		try:
			check = smon_sql.get_one_multi_check(kwargs.get('multi_check_id'))
			if check.runbook:
				runbook = check.runbook
		except Exception as e:
			roxywi_common.logger(f'unable to get check: {e}')

	try:
		if level == 'info':
			session.resolve(dedup_key)
		else:
			custom_details = {
				'alert': f'[{rmon_name}] {mess}',
				'runbook': runbook
			}
			session.trigger(mess, 'RMON', dedup_key=dedup_key, severity=level, custom_details=custom_details)
		return 'ok'
	except Exception as e:
		roxywi_common.logger(str(e), "error")
		raise Exception(f'{e}')


def mm_send_mess(mess, level, **kwargs):
	token = ''
	runbook = ''
	rmon_name = sql.get_setting('rmon_name')

	if kwargs.get('channel_id') == 0:
		return

	if kwargs.get('channel_id'):
		try:
			mms = channel_sql.get_receiver_by_id('mm', kwargs.get('channel_id'))
		except Exception as e:
			print(e)
	else:
		try:
			mms = channel_sql.get_receiver_by_ip('mm', kwargs.get('ip'))
		except Exception as e:
			print(e)

	for pd in mms:
		token = pd.token
		channel = pd.chanel_name.lower()

	if level != 'info':
		try:
			check = smon_sql.get_one_multi_check(kwargs.get('multi_check_id'))
			if check.runbook:
				runbook = check.runbook
		except Exception as e:
			roxywi_common.logger(f'unable to get check: {e}')

	if level == "info":
		color = "51A347"
	elif level == "warning":
		color = "FFB300"
	else:
		color = "c20707"
	attach = {
		"fallback": f"{level}",
		"color": f"#{color}",
		"text": f"{mess}",
		"author_name": f"{rmon_name}",
		"title": f"{level} alert",
		"fields": [
			{
				"short": "true",
				"title": "Level",
				"value": level,
			},
			{
				"short": "true",
				"title": "Runbook",
				"value": runbook,
			}
		]
	}
	attach = str(json.dumps(attach))
	headers = {'Content-Type': 'application/json'}
	values = f'{{"channel": "{channel}", "username": "{rmon_name}", "attachments": [{attach}]}}'
	proxy_dict = common.return_proxy_dict()
	try:
		response = requests.post(token, headers=headers, data=str(values), timeout=15, proxies=proxy_dict)
		if response.status_code != 200:
			res = json.loads(response.text)
			roxywi_common.logger(res["message"].encode('utf-8'))
			raise Exception(res["message"].encode('utf-8'))
		return 'ok'
	except Exception as e:
		roxywi_common.logger(str(e))
		raise Exception(f'{e}')


def check_rabbit_alert() -> Union[str, dict]:
	claims = roxywi_common.get_jwt_token_claims()
	try:
		user_group_id = claims['group']
	except Exception as e:
		return roxywi_common.handle_json_exceptions(e, 'Cannot get group')

	try:
		json_for_sending = {"user_group": user_group_id, "message": 'info: Test message'}
		send_message_to_rabbit(json.dumps(json_for_sending))
	except Exception as e:
		return roxywi_common.handle_json_exceptions(e, 'Cannot get group')
	else:
		return 'ok'


def email_send_mess(mess, o_level, **kwargs):
	runbook = ''
	rmon_name = sql.get_setting('rmon_name')

	if o_level == 'info':
		level = '\U0001F7E2 info'
	elif o_level == 'warning':
		level = '\U0001F7E1 warning'
	else:
		level = f'\U0001F534 {o_level}'
	if kwargs.get('channel_id') == 0:
		return

	if kwargs.get('channel_id'):
		emails = channel_sql.get_receiver_by_id('email', kwargs.get('channel_id'))
	else:
		emails = channel_sql.get_receiver_by_ip('email', kwargs.get('ip'))

	for e in emails:
		emails_raw = e.token
		emails = [email.strip() for email in emails_raw.replace(',', ' ').split()]
		for email in emails:
			email = email.replace("'", "")
			if o_level != 'info':
				try:
					check = smon_sql.get_one_multi_check(kwargs.get('multi_check_id'))
					if check.runbook:
						runbook = f'.\n Runbook: {check.runbook}'
				except Exception as e:
					roxywi_common.logger(f'unable to get check: {e}')
			send_email(email, f'{rmon_name}: {level}: {mess} {runbook}', f'{level}: {mess}')


def check_email_alert() -> str:
	rmon_name = sql.get_setting('rmon_name')
	subject = 'test message'
	message = f'Test message from {rmon_name}'

	try:
		user = user_sql.get_user_id(g.user_params['user_id'])
	except Exception as e:
		return f'Cannot get a user email: {e}'

	try:
		send_email(user.email, subject, message)
	except Exception as e:
		return f'Cannot send a message {e}'

	return 'ok'


def add_receiver(receiver: str, token: str, channel: str, group: str, is_api=False) -> Union[str, int]:
	last_id = channel_sql.insert_new_receiver(receiver, token, channel, group)

	if is_api:
		return last_id
	else:
		lang = roxywi_common.get_user_lang_for_flask()
		new_channel = channel_sql.select_receiver(receiver, last_id)
		groups = group_sql.select_groups()
		return render_template('ajax/new_receiver.html', groups=groups, lang=lang, channel=new_channel, receiver=receiver)


def delete_receiver_channel(channel_id: int, receiver_name: str) -> None:
	try:
		channel_sql.delete_receiver(receiver_name, channel_id)
	except Exception as e:
		raise e


def update_receiver_channel(receiver_name: str, token: str, channel: str, group: id, channel_id: int) -> None:
	try:
		channel_sql.update_receiver(receiver_name, token, channel, group, channel_id)
	except Exception as e:
		raise e


def check_receiver(channel_id: int, receiver_name: str, multi_check_id: int = None) -> str:
	functions = {
		"telegram": telegram_send_mess,
		"slack": slack_send_mess,
		"pd": pd_send_mess,
		"mm": mm_send_mess,
		"email": email_send_mess
	}
	rmon_name = sql.get_setting('rmon_name')
	mess = f'Test message from {rmon_name}'

	if receiver_name == 'pd':
		level = 'warning'
	else:
		level = 'info'

	kwargs = {
		'multi_check_id': multi_check_id,
		'channel_id': channel_id
	}

	try:
		return functions[receiver_name](mess, level, **kwargs)
	except Exception as e:
		raise e


def load_channels():
	try:
		user_subscription = roxywi_common.return_user_status()
	except Exception as e:
		user_subscription = roxywi_common.return_unsubscribed_user_status()
		roxywi_common.logger(f'Cannot get a user plan: {e}', "error")

	try:
		user_params = roxywi_common.get_users_params()
	except Exception:
		abort(403)

	kwargs = {
		'user_subscription': user_subscription,
		'user_params': user_params,
		'lang': user_params['lang']
	}

	if user_subscription['user_status']:
		user_group = roxywi_common.get_user_group(id=1)
		kwargs.setdefault('telegrams', channel_sql.get_user_receiver_by_group('telegram', user_group))
		kwargs.setdefault('pds', channel_sql.get_user_receiver_by_group('pd', user_group))
		kwargs.setdefault('mms', channel_sql.get_user_receiver_by_group('mm', user_group))
		kwargs.setdefault('groups', group_sql.select_groups())
		kwargs.setdefault('slacks', channel_sql.get_user_receiver_by_group('slack', user_group))
		kwargs.setdefault('emails', channel_sql.get_user_receiver_by_group('email', user_group))
		kwargs.setdefault('user_subscription', user_subscription)
		kwargs.setdefault('user_params', user_params)
		kwargs.setdefault('lang', user_params['lang'])

	return render_template('ajax/channels.html', **kwargs)
