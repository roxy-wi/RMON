import json
from typing import Union

import pika
import requests
from flask import render_template, abort, g
from flask_jwt_extended import get_jwt, verify_jwt_in_request

import app.modules.db.sql as sql
import app.modules.db.user as user_sql
import app.modules.db.group as group_sql
import app.modules.db.channel as channel_sql
import app.modules.common.common as common
import app.modules.roxywi.common as roxywi_common

error_mess = common.error_mess


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
	try:
		users_email = user_sql.select_users_emails_by_group_id(group_id)

		for user_email in users_email:
			send_email(user_email.email, subject, f'{level}: {mes}')
	except Exception as e:
		roxywi_common.logging('RMON server', f'error: unable to send email: {e}', roxywi=1)


def send_email(email_to: str, subject: str, message: str) -> None:
	from smtplib import SMTP

	try:
		from email.MIMEText import MIMEText
	except Exception:
		from email.mime.text import MIMEText

	mail_ssl = sql.get_setting('mail_ssl')
	mail_from = sql.get_setting('mail_from')
	mail_smtp_host = sql.get_setting('mail_smtp_host')
	mail_smtp_port = sql.get_setting('mail_smtp_port')
	mail_smtp_user = sql.get_setting('mail_smtp_user')
	mail_smtp_password = sql.get_setting('mail_smtp_password').replace("'", "")

	msg = MIMEText(message)
	msg['Subject'] = f'RMON: {subject}'
	msg['From'] = f'RMON <{mail_from}>'
	msg['To'] = email_to

	try:
		smtp_obj = SMTP(mail_smtp_host, mail_smtp_port)
		if mail_ssl:
			smtp_obj.starttls()
		smtp_obj.login(mail_smtp_user, mail_smtp_password)
		smtp_obj.send_message(msg)
		roxywi_common.logging('RMON server', f'An email has been sent to {email_to}', roxywi=1)
	except Exception as e:
		roxywi_common.logging('RMON server', f'error: unable to send email: {e}', roxywi=1)


def telegram_send_mess(mess, level, **kwargs):
	import telebot
	from telebot import apihelper
	token_bot = ''
	channel_name = ''

	if kwargs.get('channel_id') == 0:
		return

	if kwargs.get('channel_id'):
		telegrams = channel_sql.get_receiver_by_id('telegram', kwargs.get('channel_id'))
	else:
		telegrams = channel_sql.get_receiver_by_ip('slack', kwargs.get('ip'))

	proxy = sql.get_setting('proxy')

	for telegram in telegrams:
		token_bot = telegram.token
		channel_name = telegram.chanel_name

	if token_bot == '' or channel_name == '':
		mess = " Can't send message. Add Telegram channel before use alerting at this servers group"
		roxywi_common.logging('RMON server', mess, roxywi=1)

	if proxy is not None and proxy != '' and proxy != 'None':
		apihelper.proxy = {'https': proxy}
	try:
		bot = telebot.TeleBot(token=token_bot)
		bot.send_message(chat_id=channel_name, text=f'{level}: {mess}')
		return 'ok'
	except Exception as e:
		roxywi_common.logging('RMON server', str(e), roxywi=1)
		raise Exception(f'error: {e}')


def slack_send_mess(mess, level, **kwargs):
	from slack_sdk import WebClient
	from slack_sdk.errors import SlackApiError
	slack_token = ''
	channel_name = ''

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

	try:
		client.chat_postMessage(channel=f'#{channel_name}', text=f'{level}: {mess}')
		return 'ok'
	except SlackApiError as e:
		roxywi_common.logging('RMON server', str(e), roxywi=1)
		raise Exception(f'error: {e}')


def pd_send_mess(mess, level, server_ip=None, service_id=None, alert_type=None, **kwargs):
	import pdpyras

	token = ''

	if kwargs.get('channel_id') == 0:
		return

	if kwargs.get('channel_id'):
		try:
			pds = channel_sql.get_receiver_by_id('pd', kwargs.get('channel_id'))
		except Exception as e:
			roxywi_common.logging('RMON server', str(e), roxywi=1)
	else:
		try:
			pds = channel_sql.get_receiver_by_ip('pd', kwargs.get('ip'))
		except Exception as e:
			roxywi_common.logging('RMON server', str(e), roxywi=1)

	for pd in pds:
		token = pd.token

	try:
		proxy = sql.get_setting('proxy')
		session = pdpyras.EventsAPISession(token)
		dedup_key = f'{server_ip} {service_id} {alert_type}'
	except Exception as e:
		roxywi_common.logging('RMON server', str(e), roxywi=1)
		raise Exception(f'error: {e}')

	if proxy is not None and proxy != '' and proxy != 'None':
		proxies = dict(https=proxy, http=proxy)
		session.proxies.update(proxies)

	try:
		if level == 'info':
			session.resolve(dedup_key)
		else:
			session.trigger(mess, 'RMON', dedup_key=dedup_key, severity=level, custom_details={'server': server_ip, 'alert': mess})
		return 'ok'
	except Exception as e:
		roxywi_common.logging('RMON server', str(e), roxywi=1)
		raise Exception(f'error: {e}')


def mm_send_mess(mess, level, server_ip=None, service_id=None, alert_type=None, **kwargs):
	token = ''

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
		channel = pd.chanel_name

	headers = {'Content-Type': 'application/json'}
	if level == "info":
		color = "51A347"
	else:
		color = "c20707"
	attach = {
		"fallback": f"{alert_type}",
		"color": f"#{color}",
		"text": f"{mess}",
		"author_name": "RMON",
		"title": f"{level} alert",
		"fields": [
			{
				"short": "true",
				"title": "Level",
				"value": f"{level}",
			}
		]
	}
	attach = str(json.dumps(attach))
	values = f'{{"channel": "{channel}", "username": "RMON", "attachments": [{attach}]}}'
	proxy_dict = common.return_proxy_dict()
	try:
		requests.post(token, headers=headers, data=str(values), timeout=15)
		return 'ok'
	except Exception as e:
		roxywi_common.logging('RMON server', str(e), roxywi=1, proxies=proxy_dict)
		raise Exception(f'error: {e}')


def check_rabbit_alert() -> Union[str, dict]:
	verify_jwt_in_request()
	claims = get_jwt()
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


def check_email_alert() -> str:
	subject = 'test message'
	message = 'Test message from RMON'

	try:
		user = user_sql.get_user_id(g.user_params['user_id'])
	except Exception as e:
		return f'error: Cannot get a user email: {e}'

	try:
		send_email(user.email, subject, message)
	except Exception as e:
		return f'error: Cannot send a message {e}'

	return 'ok'


def add_receiver(receiver: str, token: str, channel: str, group: str, is_api=False) -> str:
	last_id = channel_sql.insert_new_receiver(receiver, token, channel, group)

	if is_api:
		return last_id
	else:
		lang = roxywi_common.get_user_lang_for_flask()
		new_channel = channel_sql.select_receiver(receiver, last_id)
		groups = group_sql.select_groups()
		roxywi_common.logging('Roxy-WI server', f'A new {receiver.title()} channel {channel} has been created ', roxywi=1, login=1)
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


def check_receiver(channel_id: int, receiver_name: str) -> str:
	functions = {
		"telegram": telegram_send_mess,
		"slack": slack_send_mess,
		"pd": pd_send_mess,
		"mm": mm_send_mess,
	}
	mess = 'Test message from RMON'

	if receiver_name == 'pd':
		level = 'warning'
	else:
		level = 'info'

	try:
		return functions[receiver_name](mess, level, channel_id=channel_id)
	except Exception as e:
		return f'error: Cannot send message: {e}'


def load_channels():
	try:
		user_subscription = roxywi_common.return_user_status()
	except Exception as e:
		user_subscription = roxywi_common.return_unsubscribed_user_status()
		roxywi_common.logging('Roxy-WI server', f'Cannot get a user plan: {e}', roxywi=1)

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
		kwargs.setdefault('user_subscription', user_subscription)
		kwargs.setdefault('user_params', user_params)
		kwargs.setdefault('lang', user_params['lang'])

	return render_template('ajax/channels.html', **kwargs)
