import os
import importlib.util
import sys
import traceback
from dotenv import load_dotenv
from pyrails.logger import logger


class Config:
    def __init__(self, env=None):
        # Initialize with basic ENV setting
        self.ENV = os.getenv("PYRAILS_ENV", "development")

        # Load configurations in order of precedence
        self._load_default_config()
        self._load_base_env()
        self._load_environment_env()
        self.load_environment_config()  # Python config files last

    def _load_default_config(self):
        """Load default configurations"""
        self.APP_NAME = "MyPyRailsApp"
        self.DB_NAME = f"database_{self.ENV}"
        self.DATABASE_URL = "mongodb://localhost:27017"
        self.DEBUG = False
        self.APP_MODE = "server"

        self.DATABASES = {
            "default": {
                "NAME": self.DB_NAME,
                "URL": self.DATABASE_URL,
                "SSL": False,
            }
        }

        self.ADMIN_PANEL_ENABLED = True
        self.ADMIN_PANEL_ROUTE_PREFIX = "/admin"
        self.ADMIN_AUTH_CLASS = "User"

        self.JWT_SECRET_KEY = "PLEASE_CHANGE_ME"

        self.FILE_STORAGE_BACKEND = "filesystem"
        self.FILE_SYSTEM_STORAGE_LOCATION = "./uploads"
        self.FILE_SYSTEM_BASE_URL = "/uploads/"

        self.S3_BUCKET_NAME = ""
        self.AWS_ACCESS_KEY_ID = ""
        self.AWS_SECRET_ACCESS_KEY = ""
        self.AWS_REGION_NAME = ""

    def _load_base_env(self):
        """Load base .env file and set variables as attributes"""
        # Load the base .env file
        base_env_path = os.path.join(os.getcwd(), ".env")
        if os.path.exists(base_env_path):
            load_dotenv(base_env_path)
            self._set_env_vars_as_attributes()
        else:
            logger.info("No base .env file found")

    def _load_environment_env(self):
        """Load environment-specific .env file and set variables as attributes"""
        env_specific_path = os.path.join(os.getcwd(), f".env.{self.ENV}")
        if os.path.exists(env_specific_path):
            load_dotenv(env_specific_path, override=True)
            self._set_env_vars_as_attributes()

    def _set_env_vars_as_attributes(self):
        """Set environment variables as attributes of the config object"""
        for key, value in os.environ.items():
            if key.isupper():  # Only set uppercase variables as config attributes
                # Convert common string values to appropriate types
                if value.lower() in ("true", "false"):
                    value = value.lower() == "true"
                elif value.isdigit():
                    value = int(value)
                elif value.replace(".", "", 1).isdigit() and value.count(".") < 2:
                    value = float(value)

                setattr(self, key, value)

    def load_from_module(self, module):
        """Load configuration from a given module."""
        for key in dir(module):
            if key.isupper():
                setattr(self, key, getattr(module, key))

    def load_environment_config(self):
        """Dynamically load the environment-specific configuration."""
        try:
            cwd = os.getcwd()
            config_path = os.path.join(cwd, "config", f"{self.ENV}.py")

            if not os.path.exists(config_path):
                logger.warn(
                    f"Configuration file for environment '{self.ENV}' not found at {config_path}."
                )
                return

            spec = importlib.util.spec_from_file_location(
                f"config.{self.ENV}", config_path
            )
            config_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(config_module)

            self.load_from_module(config_module)
        except Exception as e:
            logger.error(f"Error loading configuration: {str(e)}")
            logger.error(traceback.format_exc())
            logger.info("Using default configuration.")

    def add_database(
        self, alias: str, name: str, url: str, ssl: bool = False, **kwargs
    ):
        self.DATABASES[alias] = {"NAME": name, "URL": url, "SSL": ssl, **kwargs}

    def to_dict(self):
        return {
            key: value for key, value in vars(self).items() if not key.startswith("_")
        }


def get_config():
    """Initialize and load the configuration."""
    config = Config()
    return config


# Singleton configuration instance
config = get_config()
