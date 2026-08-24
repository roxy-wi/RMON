import importlib.util
import os
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

from pydantic import TypeAdapter, ValidationError


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def load_source(module_name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(module_name, REPOSITORY_ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ConfigurationSecurityTests(unittest.TestCase):
    def test_scheduler_api_is_disabled_and_test_keys_can_come_from_environment(self):
        environment = {
            'RMON_SECRET_KEY': 'session-secret-' * 4,
            'RMON_JWT_ALGORITHM': 'HS256',
            'RMON_JWT_SECRET_KEY': 'jwt-secret-' * 4,
        }
        with patch.dict(os.environ, environment, clear=False):
            config = load_source('rmon_test_config', 'app/config.py')

        self.assertFalse(config.Configuration.SCHEDULER_API_ENABLED)
        self.assertEqual(config.Configuration.JWT_ALGORITHM, 'HS256')
        self.assertEqual(config.Configuration.SECRET_KEY, environment['RMON_SECRET_KEY'])

    def test_short_flask_secret_is_rejected(self):
        environment = {
            'RMON_SECRET_KEY': 'too-short',
            'RMON_JWT_ALGORITHM': 'HS256',
            'RMON_JWT_SECRET_KEY': 'jwt-secret-' * 4,
        }
        with patch.dict(os.environ, environment, clear=False):
            with self.assertRaisesRegex(RuntimeError, 'at least 32'):
                load_source('rmon_test_short_config', 'app/config.py')


class InputValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.models = load_source('rmon_test_class_models', 'app/modules/roxywi/class_models.py')
        cls.adapter = TypeAdapter(cls.models.EscapedString)

    def test_safe_value_is_not_shell_quoted_or_modified(self):
        self.assertEqual(self.adapter.validate_python('value with spaces'), 'value with spaces')

    def test_shell_metacharacters_are_rejected(self):
        for value in ('value; id', 'value|id', 'value\nnext', '$(id)', '`id`'):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                self.adapter.validate_python(value)

    def test_path_traversal_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.adapter.validate_python('../credential')

    def test_non_string_is_rejected_instead_of_becoming_empty(self):
        with self.assertRaises(TypeError):
            self.adapter.validate_python(123)


class TenantAccessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        package_names = ('app', 'app.modules', 'app.modules.roxywi')
        cls.saved_modules = {name: sys.modules.get(name) for name in package_names}
        for name in package_names:
            package = types.ModuleType(name)
            package.__path__ = []
            sys.modules[name] = package
        exception = load_source('app.modules.roxywi.exception', 'app/modules/roxywi/exception.py')
        sys.modules['app.modules.roxywi.exception'] = exception
        cls.access = load_source('rmon_test_access', 'app/modules/roxywi/access.py')

    @classmethod
    def tearDownClass(cls):
        sys.modules.pop('app.modules.roxywi.exception', None)
        for name, module in cls.saved_modules.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module

    def test_group_admin_cannot_manage_another_group(self):
        with self.assertRaises(Exception):
            self.access.ensure_group_management(2, 10, 11)

    def test_group_admin_cannot_assign_superadmin(self):
        with self.assertRaises(Exception):
            self.access.ensure_role_assignment(2, 1)

    def test_superadmin_can_manage_other_groups_and_roles(self):
        self.access.ensure_group_management(1, 10, 11)
        self.access.ensure_role_assignment(1, 1)


class SourceBoundaryTests(unittest.TestCase):
    def test_login_guard_does_not_use_url_substring_bypass(self):
        login_source = (REPOSITORY_ROOT / 'app/login.py').read_text(encoding='utf-8')
        self.assertNotIn("'api' not in request.url", login_source)
        self.assertIn('request.endpoint not in allowed_endpoints', login_source)

    def test_agent_http_target_is_loaded_from_database(self):
        agent_source = (REPOSITORY_ROOT / 'app/modules/tools/smon_agent.py').read_text(encoding='utf-8')
        self.assertGreaterEqual(agent_source.count('server_ip = smon_sql.get_agent_ip_by_id(agent_id)'), 4)

    def test_passwords_use_adaptive_hashes_with_legacy_migration(self):
        tools_source = (REPOSITORY_ROOT / 'app/modules/roxy_wi_tools.py').read_text(encoding='utf-8')
        auth_source = (REPOSITORY_ROOT / 'app/modules/roxywi/auth.py').read_text(encoding='utf-8')
        self.assertIn('generate_password_hash', tools_source)
        self.assertIn('needs_rehash', auth_source)
        self.assertIn('update_user_password', auth_source)

    def test_legacy_credential_secret_is_not_blocklisted(self):
        ssh_source = (REPOSITORY_ROOT / 'app/modules/server/ssh.py').read_text(encoding='utf-8')
        self.assertNotIn('KNOWN_INSECURE_SECRET_SHA256', ssh_source)


if __name__ == '__main__':
    unittest.main()
