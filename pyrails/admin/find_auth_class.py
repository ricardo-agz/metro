import inspect
import os
import importlib
import traceback
import sys
from typing import Type, Optional

from pyrails.auth import UserBase
from pyrails.config import config
from pyrails.models import BaseModel
from pyrails.logger import logger


def find_auth_class(verbose: bool = True) -> Optional[Type[UserBase]]:
    """Recursively search for auth class in models directory and subdirectories"""
    sys.path.append(os.getcwd())
    models_dir = os.path.join(os.getcwd(), "app", "models")
    admin_auth_class = None

    for root, _, files in os.walk(models_dir):
        # Convert file path to module path
        module_path = os.path.relpath(root, os.getcwd()).replace(os.sep, ".")

        # Look through all Python files in this directory
        for file in files:
            if file.endswith(".py") and not file.startswith("__"):
                module_name = file[:-3]  # Remove .py extension
                full_module_path = f"{module_path}.{module_name}"

                try:
                    module = importlib.import_module(full_module_path)

                    # Inspect each class in the module
                    for name, obj in inspect.getmembers(module):
                        if (
                            inspect.isclass(obj)
                            and issubclass(obj, BaseModel)
                            and obj != BaseModel
                            and name.lower() == config.ADMIN_AUTH_CLASS.lower()
                        ):
                            if not issubclass(obj, UserBase) and verbose:
                                logger.warn(
                                    f"Admin auth class {config.ADMIN_AUTH_CLASS} does not inherit UserBase. Make sure {config.ADMIN_AUTH_CLASS} implements the necessary fields and methods or set it to inherit from UserBase."
                                )
                            return obj

                except ImportError as e:
                    logger.warn(f"Warning: Could not import {full_module_path}: {e}")
                    continue

    if not admin_auth_class and verbose:
        logger.error(
            f"Admin panel is enabled but could not find admin auth class {config.ADMIN_AUTH_CLASS} in app/models. Admin panel will not work."
        )
        logger.warn(
            "If a user model class exists and it is not named 'User', make sure to set ADMIN_AUTH_CLASS='MyUserClass' in your config file."
        )
