import keyring
from keyring import errors as keyring_errors
import json
import os


SERVICE_NAME = "metro_conductor"
CONFIG_DIR = os.path.expanduser("~/.metro")
CONFIG_FILE = os.path.join(CONFIG_DIR, "conductor_config.json")


def set_secure_permissions():
    """Set secure file permissions on config file"""
    if os.name != "nt":
        os.chmod(CONFIG_DIR, 0o700)
        os.chmod(CONFIG_FILE, 0o600)


class KeyStorage:
    def __init__(self):
        self.keyring_available = self._check_keyring_available()

    @staticmethod
    def _check_keyring_available():
        try:
            keyring.get_keyring()
            return True
        except Exception:
            return False

    @staticmethod
    def _store_in_keyring(key_name: str, value: str):
        keyring.set_password(SERVICE_NAME, key_name, value)

    @staticmethod
    def _get_from_keyring(key_name: str):
        return keyring.get_password(SERVICE_NAME, key_name)

    def _store_in_file(self, config):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f)
        set_secure_permissions()

    @staticmethod
    def _load_from_file():
        if not os.path.exists(CONFIG_FILE):
            return {}
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)

    def set_key(self, provider: str, api_key: str):
        key_name = f"{provider}_api_key"
        if self.keyring_available:
            self._store_in_keyring(key_name, api_key)
            # Store metadata in config file
            config = self._load_from_file()
            config[key_name] = {"stored_in": "keyring"}
            self._store_in_file(config)
        else:
            config = self._load_from_file()
            config[key_name] = api_key
            self._store_in_file(config)

    def get_key(self, provider: str):
        key_name = f"{provider}_api_key"
        config = self._load_from_file()

        if key_name not in config:
            return None

        if self.keyring_available and isinstance(config[key_name], dict):
            return self._get_from_keyring(key_name)
        else:
            return config[key_name]

    def remove_key(self, provider: str):
        key_name = f"{provider}_api_key"

        if self.keyring_available:
            try:
                keyring.delete_password(SERVICE_NAME, key_name)
            except keyring_errors.PasswordDeleteError:
                pass

        config = self._load_from_file()
        if key_name in config:
            del config[key_name]
            self._store_in_file(config)


key_storage = KeyStorage()
