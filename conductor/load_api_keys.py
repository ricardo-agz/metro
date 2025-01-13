import os
from conductor.constants import PROVIDERS
from conductor.key_storage import key_storage


def load_api_keys():
    """Load API keys from key storage"""
    for provider in PROVIDERS:
        key = key_storage.get_key(provider)
        if key:
            os.environ[f"{provider.upper()}_API_KEY"] = key
