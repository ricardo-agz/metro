import os
import importlib.util
import sys
import traceback
from dotenv import load_dotenv
from pyrails.logger import logger


load_dotenv()


class Config:
    def __init__(self, env=None):
        # Default configurations
        self.ENV = os.getenv("PYRAILS_ENV", "development")
        self.APP_NAME = os.getenv("APP_NAME", "MyPyRailsApp")
        self.DB_NAME = os.getenv("DATABASE_NAME", f"database_{self.ENV}")
        self.DATABASE_URL = os.getenv("DATABASE_URL", "mongodb://localhost:27017")
        self.DEBUG = os.getenv("DEBUG", "False").lower() in ("true", "1", "t")

        self.DATABASES: dict[str, dict[str, any]] = {
            "default": {
                "NAME": self.DB_NAME,
                "URL": self.DATABASE_URL,
                "SSL": False,
            }
        }

        self.FILE_STORAGE_BACKEND = "filesystem"
        self.FILE_SYSTEM_STORAGE_LOCATION = "./uploads"
        self.FILE_SYSTEM_BASE_URL = "/uploads/"

        self.S3_BUCKET_NAME = ""
        self.AWS_ACCESS_KEY_ID = ""
        self.AWS_SECRET_ACCESS_KEY = ""
        self.AWS_REGION_NAME = ""

    def load_from_module(self, module):
        """Load configuration from a given module."""
        for key in dir(module):
            if key.isupper():
                setattr(self, key, getattr(module, key))

    def load_environment_config(self):
        """Dynamically load the environment-specific configuration."""
        env = self.ENV
        try:
            # Get the current working directory (where the script is run from)
            cwd = os.getcwd()

            # Construct the path to the config file
            config_path = os.path.join(cwd, "config", f"{env}.py")

            # Check if the file exists
            if not os.path.exists(config_path):
                logger.debug(
                    f"Configuration file for environment '{env}' not found at {config_path}. Using default configuration."
                )
                return

            # Load the module from the file path
            spec = importlib.util.spec_from_file_location(f"config.{env}", config_path)
            config_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(config_module)

            # Load configurations from the module
            self.load_from_module(config_module)
        except Exception as e:
            logger.error(f"Error loading configuration: {str(e)}")
            logger.error(traceback.format_exc())
            logger.info("Using default configuration.")

    def add_database(
        self, alias: str, name: str, url: str, ssl: bool = False, **kwargs
    ):
        self.DATABASES[alias] = {"NAME": name, "URL": url, "SSL": ssl, **kwargs}


def get_config():
    """Initialize and load the configuration."""
    config = Config()
    config.load_environment_config()
    return config


# Singleton configuration instance
config = get_config()
