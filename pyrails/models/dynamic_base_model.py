from mongoengine import DynamicDocument
from .base_logic import BaseModelLogic
from datetime import datetime
from .specialty_fields.file_field import FileHandlingMixin


class DynamicBaseModel(BaseModelLogic, FileHandlingMixin, DynamicDocument):
    """
    Abstract base class for dynamic MongoEngine Documents,
    inheriting from both DynamicDocument and BaseModelLogic.
    """

    meta = {
        "abstract": True,
        "db_alias": "default",
    }

    def save(self, *args, **kwargs) -> "DynamicBaseModel":
        try:
            self.clean()
            self.pre_save()
            self.updated_at = datetime.utcnow()
            result = super().save(*args, **kwargs)
            self.post_save()
            return result
        except Exception as e:
            self.handle_save_error(e)
            raise
