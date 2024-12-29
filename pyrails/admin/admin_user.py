from pyrails.models import *


class BaseAdminUser(BaseModel):
    email = StringField(required=True, unique=True)
    password_hash = HashedField(required=True)
    is_admin = BooleanField(default=True)

    def __str__(self) -> str:
        return f"AdminUser<{self.email}>"
