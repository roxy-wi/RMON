from flask.views import MethodView
from flask_jwt_extended import jwt_required
from flask import render_template, jsonify, request, g
from playhouse.shortcuts import model_to_dict

from app.modules.db.db_model import Cred
import app.modules.db.cred as cred_sql
import app.modules.db.group as group_sql
import app.modules.db.server as server_sql
import app.modules.common.common as common
import app.modules.roxywi.group as group_mod
import app.modules.roxywi.common as roxywi_common
import app.modules.server.ssh as ssh_mod
import app.modules.server.server as server_mod
import app.modules.tools.smon as smon_mod
from app.middleware import get_user_params, page_for_admin, check_group
from app.modules.roxywi.exception import RoxywiGroupMismatch, RoxywiResourceNotFound


class ServerView(MethodView):
    methods = ["POST", "PUT", "DELETE"]
    decorators = [jwt_required(), get_user_params(), page_for_admin(level=2), check_group()]

    def __init__(self, is_api=False):
        self.json_data = request.get_json()
        self.is_api = is_api

    def post(self):
        """
        POST method for creating a new server.

        Parameters:
        - None

        Returns:
        - If successful and called as an API, returns a JSON response with status 'Created' and the ID of the newly created server. HTTP status code 201.
        - If successful and called from a web interface, returns a JSON response with status 'Created', the rendered HTML template for adding a new server, and the ID of the newly created server. HTTP status code 201.

        Raises:
        - ValueError: If there is an issue with parsing the input values (e.g. invalid integer format).
        - KeyError: If a required key is missing in the input data.
        - Exception: If there is an unexpected error while processing the server data.

        Example Usage:
        response = post()

        Note:
        - This method is specifically designed for internal use and does not include any authorization checks.
        - The method performs various validations and creates a server based on the provided data.
        - If the 'add_to_smon' flag is set, the method also attempts to create a corresponding SMON entry for monitoring the server.
        - Additionally, the method logs the creation of the server and updates the server information.

        """
        try:
            if g.user_params['role'] == 1:
                group = int(self.json_data['group'])
            else:
                group = int(g.user_params['group_id'])
            hostname = common.checkAjaxInput(self.json_data['name'])
            ip = common.is_ip_or_dns(self.json_data['ip'])
            enable = int(self.json_data['enabled'])
            cred = int(self.json_data['creds_id'])
            port = int(self.json_data['port'])
            desc = common.checkAjaxInput(self.json_data['desc'])
            add_to_smon = int(self.json_data['add_to_smon'])
            lang = roxywi_common.get_user_lang_for_flask()
        except ValueError as e:
            return roxywi_common.handle_json_exceptions(e, f'There is must be a value')
        except KeyError as e:
            return roxywi_common.handle_json_exceptions(e, f'There is must be a key')
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot parse server data')

        try:
            last_id = server_mod.create_server(hostname, ip, group, enable, cred, port, desc)
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot create a server')

        if add_to_smon:
            try:
                user_group = roxywi_common.get_user_group(id=1)
                json_data = {
                    "name": hostname,
                    "ip": ip,
                    "port": "0",
                    "enabled": "1",
                    "url": "",
                    "body": "",
                    "group": hostname,
                    "desc": f"Ping {hostname}",
                    "tg": "0",
                    "slack": "0",
                    "pd": "0",
                    "resolver": "",
                    "record_type": "",
                    "packet_size": "56",
                    "http_method": "",
                    "check_type": "ping",
                    "agent_id": "1",
                    "interval": "120",
                }
                smon_mod.create_smon(json_data, user_group)
            except Exception as e:
                roxywi_common.logging(ip, f'error: Cannot add server {hostname} to SMON: {e}')

        roxywi_common.logging(ip, f'A new server {hostname} has been created', login=1, keep_history=1, service='server')

        try:
            server_mod.update_server_after_creating(hostname, ip)
        except Exception as e:
            roxywi_common.logging(ip, f'error: Cannot get system info from {hostname}: {e}', login=1, keep_history=1, service='server')

        if self.is_api:
            return jsonify({'status': 'Created', 'id': last_id}), 201
        else:
            data = render_template('ajax/new_server.html', groups=group_sql.select_groups(),
                servers=server_sql.select_servers(server=ip), lang=lang, sshs=cred_sql.select_ssh(group=group), adding=1)
            return jsonify({'status': 'Created', 'data': data, 'id': last_id}), 201

    def put(self):
        """
        Updates the server information based on the provided JSON data.

        Parameters:
        self (object): The current object.

        Returns:
        tuple: A tuple containing the JSON response and the HTTP status code.
        """
        try:
            if g.user_params['role'] == 1:
                group = int(self.json_data['group'])
            else:
                group = int(g.user_params['group_id'])
            name = common.checkAjaxInput(self.json_data['name'])
            enable = int(self.json_data['enabled'])
            serv_id = int(self.json_data['id'])
            cred = int(self.json_data['creds_id'])
            port = int(self.json_data['port'])
            desc = common.checkAjaxInput(self.json_data['desc'])
        except ValueError as e:
            return roxywi_common.handle_json_exceptions(e, f'There is must be a value')
        except KeyError as e:
            return roxywi_common.handle_json_exceptions(e, f'There is must be a key')
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot parse server data')

        try:
            server_sql.update_server(name, group, enable, serv_id, cred, port, desc)
            server_ip = server_sql.select_server_ip_by_id(serv_id)
            roxywi_common.logging(server_ip, f'The server {name} has been update', roxywi=1, login=1, keep_history=1, service='server')
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot update server')

        return jsonify({'status': 'Created'}), 201

    def delete(self):
        """
        Method: delete

            This method deletes a server based on the ID provided in the JSON data.

            Parameters:
                self: The instance of the class containing the method.

            Returns:
                If successful, the method returns a JSON response with a status of 'Ok' and a status code of 204.
                If any exceptions occur during the process, the method returns a JSON response with an error message.

            Raises:
                None.
        """
        try:
            server_id = int(self.json_data['id'])
        except ValueError as e:
            return roxywi_common.handle_json_exceptions(e, f'There is must be a value')
        except KeyError as e:
            return roxywi_common.handle_json_exceptions(e, f'There is must be a key')
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot parse server data')
        try:
            server_mod.delete_server(server_id)
            return jsonify({'status': 'Ok'}), 204
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot delete server')


class GroupView(MethodView):
    methods = ["POST", "PUT", "DELETE"]
    decorators = [jwt_required(), get_user_params(), page_for_admin()]

    def __init__(self, is_api=False):
        self.json_data = request.get_json()
        self.is_api = is_api

    def post(self):
        """
        This method is used to create a new group with the given name and description. It handles input validation and error handling.

        Parameters:
        - self.json_data: A dictionary containing the name and description of the group.

        Returns:
        - If the group creation is successful:
            - If the method is called as an API endpoint, it returns a JSON response with the status "Created" and the newly created group ID. HTTP status code 201.
            - If the method is called from a non-API context, it returns a JSON response with the status "Created", the rendered HTML template for the new group, and the newly created group ID. HTTP status code 201.
        - If there is a validation error or an exception occurs during the group creation process, it returns a JSON response with the appropriate error message and details."""
        try:
            group = common.checkAjaxInput(self.json_data['name'])
            desc = common.checkAjaxInput(self.json_data['desc'])
        except ValueError as e:
            return roxywi_common.handle_json_exceptions(e, f'There is must be a value')
        except KeyError as e:
            return roxywi_common.handle_json_exceptions(e, f'There is must be a key')
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot parse group data')
        try:
            last_id = group_sql.add_group(group, desc)
            roxywi_common.logging('RMON server', f'A new group {group} has been created', roxywi=1, login=1)
            if self.is_api:
                return jsonify({'status': 'Created', 'id': last_id}), 201
            else:
                data = render_template('ajax/new_group.html', groups=group_sql.select_groups(group=group))
                return jsonify({'status': 'Created', 'data': data, 'id': last_id}), 201
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot create group')

    def put(self):
        """
        This method is used to update a group record with the provided data.

        Parameters:
        - self: The current instance of the class.
        - json_data: A JSON object containing the following fields:
            - name (str): The new name of the group.
            - desc (str): The new description of the group.
            - group_id (int): The ID of the group to be updated.

        Returns:
        - If the parameters are successfully parsed and the group is updated, a JSON response will be returned with
            the status 'Created' and a status code of 201 (Created).
        - If any errors occur during the parameter parsing or group update, an exception will be raised and handled by
            the `handle_json_exceptions()` method, returning a JSON response with an error message.
        """
        try:
            name = common.checkAjaxInput(self.json_data['name'])
            desc = common.checkAjaxInput(self.json_data['desc'])
            group_id = int(self.json_data['group_id'])
        except ValueError as e:
            return roxywi_common.handle_json_exceptions(e, f'There is must be a value')
        except KeyError as e:
            return roxywi_common.handle_json_exceptions(e, f'There is must be a key')
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot parse group data')

        try:
            group_mod.update_group(group_id, name, desc)
            return jsonify({'status': 'Created'}), 201
        except Exception as e:
            roxywi_common.handle_json_exceptions(e, 'Cannot update group')

    def delete(self):
        """
        Method to delete a group.

        Deletes a group based on the provided group_id. Returns a JSON response with the status 'Ok' and a status code of 204 if the deletion is successful.

        Parameters:
            - self: The current instance of the class.

        Returns:
            - tuple: A tuple containing the JSON response and the status code.

        Exceptions:
            - ValueError: If the group_id is not an integer.
            - KeyError: If the group_id is not found in the json_data.
            - Exception: If there is an error parsing the group data or deleting the group.
        """
        try:
            group_id = int(self.json_data['group_id'])
        except ValueError as e:
            return roxywi_common.handle_json_exceptions(e, f'There is must be a value')
        except KeyError as e:
            return roxywi_common.handle_json_exceptions(e, f'There is must be a key')
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot parse group data')
        try:
            group_mod.delete_group(group_id)
            return jsonify({'status': 'Ok'}), 204
        except Exception as e:
            roxywi_common.handle_json_exceptions(e, 'Cannot delete group')


class CredsView(MethodView):
    methods = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']
    decorators = [jwt_required(), get_user_params(), page_for_admin(level=2), check_group()]

    def __init__(self, is_api=False):
        self.json_data = request.get_json()
        self.is_api = is_api

    @staticmethod
    def get():
        """
            Get method retrieves credentials based on the group ID stored in the user parameters.

            Returns:
                A JSON response containing the credentials and a status code of 200 if successful.
                If an exception occurs, it returns a JSON response generated by the `handle_json_exceptions` method from the `roxywi_common` module.
        """
        group_id = int(g.user_params['group_id'])
        try:
            creds = cred_sql.select_ssh(group=group_id)
            json_data = []
            for cred in creds:
                json_data.append(model_to_dict(cred, exclude=[Cred.password, Cred.passphrase]))
            return jsonify(json_data), 200
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot get credentials')

    def post(self):
        """
        This method is used to create a new credential entry. It takes several parameters and returns a JSON response.

        Parameters:
        - None

        Returns:
        - A JSON response with status and id fields. The status field indicates the result of the operation (e.g., 'Created'),
        and the id field contains the ID of the newly created credential entry.

        Note: This method assumes the existence of the following variables/constants: g.user_params, self.json_data, common, roxywi_common, cred_sql, jsonify.
        """
        try:
            if g.user_params['role'] == 1:
                group = int(self.json_data['group'])
            else:
                group = int(g.user_params['group_id'])
            name = common.checkAjaxInput(self.json_data['name'])
            username = common.checkAjaxInput(self.json_data['username'])
            enabled = int(self.json_data['key_enabled'])
            try:
                password = common.checkAjaxInput(self.json_data['password'])
            except KeyError:
                password = ''
        except ValueError as e:
            return roxywi_common.handle_json_exceptions(e, f'There is must be a value')
        except KeyError as e:
            return roxywi_common.handle_json_exceptions(e, f'There is must be a key')
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot parse cred data')

        try:
            return ssh_mod.create_ssh_cred(name, password, group, username, enabled, self.is_api)
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot create new cred')

    def put(self):
        """
        Updates the SSH credentials with the given parameters.

        Parameters:
            self: The object of the class.

        Returns:
            If the group is incorrect, returns the JSON response with a 404 status code.
            If there is a ValueError or KeyError, returns the JSON response with an appropriate error message.
            If there is an exception while parsing the credential data, returns the JSON response with a general error message.
            If the SSH key update is successful, returns the JSON response with a 201 status code and the status 'Ok'.
            If there is an exception while updating the SSH key, returns the JSON response with an appropriate error message.
        """
        try:
            self._check_is_correct_group()
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, ''), 404

        try:
            if g.user_params['role'] == 1:
                group = int(self.json_data['group'])
            else:
                group = int(g.user_params['group_id'])
            name = common.checkAjaxInput(self.json_data['name'])
            username = common.checkAjaxInput(self.json_data['username'])
            key_enabled = int(self.json_data['key_enabled'])
            ssh_id = int(self.json_data['id'])
            try:
                password = common.checkAjaxInput(self.json_data['password'])
            except KeyError:
                password = ''
        except ValueError as e:
            return roxywi_common.handle_json_exceptions(e, f'There is must be a value')
        except KeyError as e:
            return roxywi_common.handle_json_exceptions(e, f'There is must be a key')
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot parse cred data')

        try:
            ssh_mod.update_ssh_key(ssh_id, name, password, key_enabled, username, group)
            return jsonify({'status': 'Ok'}), 201
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot update SSH key')

    def delete(self):
        """
        The delete method is used to delete an SSH credentials from the system.

        Parameters:
          - None

        Return type:
          - Tuple: (JSON response, HTTP status code)

        Exceptions:
          - If the group is incorrect, a JSON exception is raised and a relevant error message is returned with a 404 status code.
          - If the value of the 'id' key in the JSON data cannot be converted to an integer, a JSON exception is raised and a relevant error message is returned.
          - If the 'id' key is missing in the JSON data, a JSON exception is raised and a relevant error message is returned.
          - If there is any other exception during parsing the data, a JSON exception is raised and a generic error message is returned.
        """
        try:
            self._check_is_correct_group()
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, ''), 404

        try:
            ssh_id = int(self.json_data['id'])
        except ValueError as e:
            return roxywi_common.handle_json_exceptions(e, f'There is must be a value')
        except KeyError as e:
            return roxywi_common.handle_json_exceptions(e, f'There is must be a key')
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot parse cred data')

        try:
            ssh_mod.delete_ssh_key(ssh_id)
            return jsonify({'status': 'Ok'}), 204
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot delete SSH key')

    def patch(self):
        """
        This method is used to upload an SSH private key.

        Returns:
            - If the check for correct group fails, it returns a 404 error.
            - If the user's role is 1, it expects the following parameters in JSON data:
                - 'group': An integer representing the group.
            - If the user's role is not 1, it expects the 'group_id' parameter from the user's parameters.
            - It also expects the following parameters in JSON data:
                - 'private_key': A string representing the private key.
                - 'name': A string representing the name.
                - 'passphrase' (optional): A string representing the passphrase. If not provided, it defaults to an empty string.

        Raises:
            - If there is a value error, it returns a 400 error with a message.
            - If there is a key error, it returns a 400 error with a message.
            - If there are any other exceptions, it returns a 500 error with a message.

        Note:
            - This method uses the roxywi_common.handle_json_exceptions() and common.checkAjaxInput() methods from other modules.
            - The ssh_mod.upload_ssh_key() method is used to upload the SSH key.
            - The returned JSON data includes a 'status' field with the value 'Ok' if the patch was successful.
        """
        try:
            self._check_is_correct_group()
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, ''), 404

        try:
            key = common.checkAjaxInput(self.json_data['private_key'])
            ssh_id = common.checkAjaxInput(self.json_data['id'])
            try:
                passphrase = common.checkAjaxInput(self.json_data['passphrase'])
            except KeyError:
                passphrase = ''
        except ValueError as e:
            return roxywi_common.handle_json_exceptions(e, f'There is must be a value')
        except KeyError as e:
            return roxywi_common.handle_json_exceptions(e, f'There is must be a key')
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot parse cred data')

        try:
            ssh_mod.upload_ssh_key(ssh_id, key, passphrase)
            return jsonify({'status': 'Ok'}), 201
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot upload SSH key')

    def _check_is_correct_group(self):
        if g.user_params['role'] == 1:
            return True
        try:
            ssh = cred_sql.get_ssh(self.json_data['id'])
        except RoxywiResourceNotFound:
            raise RoxywiResourceNotFound
        if ssh.group_id != g.user_params['group_id']:
            raise RoxywiGroupMismatch
