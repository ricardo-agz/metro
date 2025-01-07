from mongoengine import connect, register_connection
from pymongo import MongoClient
from pymongo.errors import PyMongoError
import certifi
from metro.logger import logger


class DatabaseManager:
    def __init__(self):
        self.connections = {}
        self.default_alias = None

    def connect_db(
        self,
        alias: str,
        db_name: str,
        db_url: str,
        is_default: bool = False,
        ssl_reqs: bool = False,
        **kwargs,
    ):
        db_host = f"{db_url}/{db_name}?retryWrites=true&w=majority"
        ssl_kwargs = {} if not ssl_reqs else {"ssl": True, "tlsCAFile": certifi.where()}

        logger.info(
            f"Connecting to database '{db_name}' with alias '{alias}' at: {db_host}..."
        )

        try:
            # Create a MongoClient instance
            client = MongoClient(db_host, **ssl_kwargs, **kwargs)

            # Test the connection
            client.admin.command("ismaster")

            # Register the connection
            if is_default or not self.default_alias:
                connect(db=db_name, host=db_host, alias=alias, **ssl_kwargs, **kwargs)
                self.default_alias = alias
            else:
                register_connection(
                    alias=alias, db=db_name, host=db_host, **ssl_kwargs, **kwargs
                )

            # Store the connection
            self.connections[alias] = client

            logger.info(
                f"Connected to database '{db_name}' with alias '{alias}' at: {db_host}"
            )
            if is_default or self.default_alias == alias:
                logger.info(f"Set as default database connection.")
        except PyMongoError as e:
            logger.error(
                f"Failed to connect to MongoDB '{db_name}' with alias '{alias}': {e}"
            )
            raise

    def get_connection(self, alias: str = None) -> MongoClient:
        if alias is None:
            alias = self.default_alias
        return self.connections.get(alias)

    def close_connections(self):
        for client in self.connections.values():
            client.close()
        self.connections.clear()


# Global instance of DatabaseManager
db_manager = DatabaseManager()
