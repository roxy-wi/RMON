import uuid

import pytest
from cryptography.fernet import Fernet

from app.modules.db.db_model import Cred
from app.modules.server.ssh import _get_fernet_key
from rotate_credential_secret import _fernet_from_environment, rotate_credentials


LEGACY_KEY = '_B8avTpFFL19M8P9VyTiX42NyeyUaneV26kyftB2E_4='


@pytest.mark.security
def test_legacy_fernet_key_is_accepted(monkeypatch):
    monkeypatch.setenv('RMON_SECRET_PHRASE', LEGACY_KEY)

    assert _get_fernet_key() == LEGACY_KEY.encode('ascii')
    assert isinstance(_fernet_from_environment('RMON_SECRET_PHRASE'), Fernet)


@pytest.mark.security
def test_change_me_fernet_key_is_rejected(monkeypatch):
    monkeypatch.setenv('RMON_SECRET_PHRASE', 'CHANGE_ME')

    with pytest.raises(RuntimeError):
        _get_fernet_key()


@pytest.mark.security
def test_credential_rotation_reencrypts_all_secret_fields(monkeypatch):
    old_key = Fernet.generate_key()
    new_key = Fernet.generate_key()
    old_fernet = Fernet(old_key)
    credential = Cred.create(
        name=f'rotation-{uuid.uuid4().hex}', username='root', group_id=1,
        password=old_fernet.encrypt(b'password').decode('ascii'),
        passphrase=old_fernet.encrypt(b'passphrase').decode('ascii'),
        private_key=old_fernet.encrypt(b'private-key').decode('ascii'),
    )
    monkeypatch.setenv('RMON_OLD_SECRET_PHRASE', old_key.decode('ascii'))
    monkeypatch.setenv('RMON_SECRET_PHRASE', new_key.decode('ascii'))

    assert rotate_credentials() == 1

    credential = Cred.get_by_id(credential.id)
    new_fernet = Fernet(new_key)
    assert new_fernet.decrypt(credential.password.encode('ascii')) == b'password'
    assert new_fernet.decrypt(credential.passphrase.encode('ascii')) == b'passphrase'
    assert new_fernet.decrypt(credential.private_key.encode('ascii')) == b'private-key'
