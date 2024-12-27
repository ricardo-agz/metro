from mongoengine import StringField
import bcrypt


class HashedValue:
    def __init__(self, hashed_value: str):
        self.hashed_value = hashed_value

    def verify(self, plain_text: str) -> bool:
        """Verify the plain text against the hashed value."""
        if self.hashed_value is None:
            return False
        return bcrypt.checkpw(
            plain_text.encode("utf-8"), self.hashed_value.encode("utf-8")
        )


class HashedField(StringField):
    def __init__(self, *args, **kwargs):
        self.rounds = kwargs.pop("rounds", 12)
        self.custom_salt = kwargs.pop("salt", None)
        super().__init__(*args, **kwargs)

    def to_mongo(self, value: str) -> str | None:
        """Hash the value before saving to MongoDB."""
        if value is not None and not value.startswith("$2b$"):
            # Hash the value using bcrypt
            salt = (
                self.custom_salt.encode("utf-8")
                if self.custom_salt
                else bcrypt.gensalt(self.rounds)
            )
            hashed_value = bcrypt.hashpw(value.encode("utf-8"), salt)
            return hashed_value.decode("utf-8")
        return value

    def __get__(self, instance, owner) -> HashedValue:
        """Return a HashedValue instance for verification."""
        stored_hash = instance._data.get(self.name) if instance else None
        return HashedValue(stored_hash)
