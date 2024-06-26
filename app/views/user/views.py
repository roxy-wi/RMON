from flask.views import MethodView
from flask_jwt_extended import jwt_required
from flask import render_template, jsonify, request, g

import app.modules.db.sql as sql
import app.modules.db.user as user_sql
import app.modules.db.group as group_sql
import app.modules.common.common as common
import app.modules.roxywi.user as roxywi_user
import app.modules.roxywi.common as roxywi_common
from app.middleware import get_user_params, page_for_admin, check_group


class UserView(MethodView):
    methods = ["GET", "POST", "PUT", "DELETE"]
    decorators = [jwt_required(), get_user_params(), page_for_admin(level=2), check_group()]

    def __init__(self, is_api=False):
        self.json_data = request.get_json()
        self.is_api = is_api

    def get(self):
        """
        Gets the user information based on the provided user ID.

        Parameters:
            None.

        Returns:
            A JSON response containing the user's information.

        Raises:
            ValueError: If the user ID is not provided or is not an integer.
            Exception: If there is an error retrieving the user or checking user access.
        """
        try:
            user_id = int(self.json_data["user_id"])
        except ValueError as e:
            return roxywi_common.handle_json_exceptions(e, f'There is must be a value')
        except KeyError as e:
            return roxywi_common.handle_json_exceptions(e, f'Missing key in JSON data')
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot get user id')
        try:
            user = user_sql.get_user_id(user_id)
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot get user')

        try:
            roxywi_common.is_user_has_access_to_group(user_id)
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot find user'), 404

        json_data = {
            "id": user_id,
            "name": user.username,
            "email": user.email,
            "group": g.user_params['group_id'],
            "enabled": user.activeuser,
            "ldap": user.ldap_user,
            "last_login_date": user.last_login_date,
            "last_login_ip": user.last_login_ip
        }

        return jsonify(json_data)

    def post(self):
        """
        This method is used to create a new user.

        Parameters:
        - email (str): The email of the user.
        - password (str): The password of the user.
        - role (int): The role of the user. Valid roles are:
           - 1: Superadmin
           - 2: Admin
           - 3: User
           - 4: Guest
        - new_user (str): The username of the user.
        - enabled (int): Determines if the user is enabled or disabled. 1 for enabled, 0 for disabled.
        - group_id (int): The ID of the user's group.

        Returns:
        - If successful, returns a JSON response with the following keys:
           - 'status': The status of the user creation ('Created').
           - 'id': The ID of the created user.
           - 'data': The rendered HTML template of the newly created user.
        - If unsuccessful, returns a JSON response with the following keys:
           - 'status': The status of the error.
           - 'message': The error message.
        """
        try:
            email = common.checkAjaxInput(self.json_data['email'])
            password = common.checkAjaxInput(self.json_data['password'])
            role = int(self.json_data['role'])
            new_user = common.checkAjaxInput(self.json_data['username'])
            enabled = int(self.json_data['enabled'])
            group_id = int(self.json_data['user_group'])
        except ValueError as e:
            return roxywi_common.handle_json_exceptions(e, f'There is must be a value')
        except KeyError as e:
            return roxywi_common.handle_json_exceptions(e, f'Missing key in JSON data')
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot create user')
        lang = roxywi_common.get_user_lang_for_flask()

        if g.user_params['role'] > role:
            return roxywi_common.handle_json_exceptions('Wrong role', 'Cannot create user')
        try:
            user_id = roxywi_user.create_user(new_user, email, password, role, enabled, group_id)
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot create a new user')
        else:
            if self.is_api:
                return jsonify({'status': 'Created', 'id': user_id}), 201
            else:
                return jsonify({'status': 'created', 'id': user_id, 'data': render_template(
                    'ajax/new_user.html', users=user_sql.select_users(user=new_user), groups=group_sql.select_groups(),
                    roles=sql.select_roles(), adding=1, lang=lang
                )})

    def put(self):
        """
        Update user information.

        This method takes in user information as parameters and updates the user's details in the database.

        Parameters:
        - None

        Returns:
        - None

        Raises:
        - None

        Note:
        - This method requires the following parameters in the 'json_data' dictionary:
            - 'user_id' (int): The ID of the user to update.
            - 'username' (str): The updated username.
            - 'email' (str): The updated email address.
            - 'enabled' (int): Whether the user is enabled or disabled (0 being disabled and 1 being enabled).

        - If any of the required parameters are missing or if there are any exceptions during the process, an appropriate exception response is returned.

        - The user's details are logged using the 'logging' method from the 'roxywi_common' module.

        - Finally, a JSON response with a status of "Ok" is returned.
        """
        try:
            user_id = int(self.json_data['user_id'])
            user_name = common.checkAjaxInput(self.json_data['username'])
            email = common.checkAjaxInput(self.json_data['email'])
            enabled = int(self.json_data['enabled'])
        except ValueError as e:
            return roxywi_common.handle_json_exceptions(e, f'There is must be a value')
        except KeyError as e:
            return roxywi_common.handle_json_exceptions(e, f'Missing key in JSON data')
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot update user')
        try:
            user_sql.update_user_from_admin_area(user_name, email, user_id, enabled)
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot update user')
        roxywi_common.logging(user_name, ' has been updated user ', roxywi=1, login=1)
        return jsonify({'status': 'Ok'}), 201

    def delete(self):
        try:
            user_id = int(self.json_data['user_id'])
        except ValueError as e:
            return roxywi_common.handle_json_exceptions(e, f'There is must be a value')
        except KeyError as e:
            return roxywi_common.handle_json_exceptions(e, f'Missing key in JSON data')
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot delete user')

        try:
            roxywi_common.is_user_has_access_to_group(user_id)
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot find user'), 404
        try:
            user = user_sql.get_user_id(user_id)
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot get user'), 404

        if g.user_params['role'] > user.role:
            return roxywi_common.handle_json_exceptions('Wrong role', 'Cannot delete user'), 404

        try:
            roxywi_user.delete_user(user_id)
            return jsonify({'status': 'Ok'}), 204
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, f'Cannot delete the user')


class UserGroupView(MethodView):
    methods = ["GET", "POST", "PUT", "DELETE"]
    decorators = [jwt_required(), get_user_params(), page_for_admin(), check_group()]

    def __init__(self, is_api=False):
        self.json_data = request.get_json()

    def get(self):
        """
        Retrieve information for a group.

        Parameters:
            None

        Returns:
            A JSON object containing the following information for each user in the group:
                - id: The user's ID
                - username: The user's username
                - email: The user's email address
                - group: The group's ID
                - enabled: Whether the user is active or not
                - ldap: Whether the user is an LDAP user or not
                - last_login_date: The date of the user's last login
                - last_login_ip: The IP address of the user's last login
                - role: The ID of the user's role in the group

        Raises:
            Exception: If there is an error retrieving the group ID or the group information
        """
        try:
            group_id = int(self.json_data["group_id"])
        except ValueError as e:
            return roxywi_common.handle_json_exceptions(e, f'There is must be a value')
        except KeyError as e:
            return roxywi_common.handle_json_exceptions(e, f'Missing key in JSON data')
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot get group id')
        try:
            users = user_sql.get_users_in_group(group_id)
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot get group')

        json_data = []
        for user in users:
            user_role = user_sql.get_role_id(user.user_id, group_id)
            json_data.append({
                "id": user.user_id,
                "username": user.username,
                "email": user.email,
                "group": group_id,
                "enabled": user.activeuser,
                "ldap": user.ldap_user,
                "last_login_date": user.last_login_date,
                "last_login_ip": user.last_login_ip,
                "role": user_role
            })

        return jsonify(json_data)

    def post(self):
        """
        Post Method

        This method adds or updates a user into a group with a specific role.

        Parameters:
        - group_id (int): The ID of the group to add the user to.
        - user_id (int): The ID of the user to be added to the group.
        - role_id (int): The ID of the role for the user in the group.

        Returns:
        - JSON response: A JSON response with the status 'added' indicating that the user has been successfully added to the group.

        Exceptions:
        - JSON Exception: If there is an error parsing the input JSON data.
        - JSON Exception: If there is an error updating the user role in the group.
        """
        try:
            group_id = int(self.json_data['group_id'])
            user_id = int(self.json_data['user_id'])
            role_id = int(self.json_data['role_id'])
        except ValueError as e:
            return roxywi_common.handle_json_exceptions(e, f'There is must be a value')
        except KeyError as e:
            return roxywi_common.handle_json_exceptions(e, f'Missing key in JSON data')
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot get user data')
        try:
            user_sql.update_user_role(user_id, group_id, role_id)
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot add user to group')
        else:
            return jsonify({'status': 'Created'}), 201

    def delete(self):
        """
        Delete method deletes a user from a group.

        Parameters:
            - None

        Return:
            - If the user is successfully deleted from the group, it returns a JSON response with a status code 204 (No Content).
            - If there is an error, it returns a JSON response with an error message and a status code 500 (Internal Server Error).

        Raises:
            - ValueError: If the 'group_id' or 'user_id' parameters are not integers.
            - KeyError: If the 'group_id' or 'user_id' parameters are missing from the JSON data.
            - Exception: If there is an error getting user data or deleting the user from the group.
        """
        try:
            group_id = int(self.json_data['group_id'])
            user_id = int(self.json_data['user_id'])
        except ValueError as e:
            return roxywi_common.handle_json_exceptions(e, f'There is must be a value')
        except KeyError as e:
            return roxywi_common.handle_json_exceptions(e, f'Missing key in JSON data')
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot get user data')

        try:
            user_sql.delete_user_from_group(group_id, user_id)
            return jsonify({'status': 'Ok'}), 204
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot delete user')
