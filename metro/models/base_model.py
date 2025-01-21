from datetime import datetime
from mongoengine import Document
from .base_logic import BaseModelLogic, DynamicFinderMetaclass
from .specialty_fields.file_field import FileHandlingMixin


class BaseModel(BaseModelLogic, FileHandlingMixin, Document):
    """
    Abstract base class for MongoEngine Documents, inheriting from both
    Document and BaseModelMixin.
    """

    meta = {
        "abstract": True,
        "db_alias": "default",
    }

    def save(self, *args, **kwargs) -> "BaseModel":
        try:
            self.validate(clean=True)
            self.pre_save()  # Run pre-save hooks
            self.updated_at = datetime.utcnow()
            result = super().save(*args, **kwargs)
            self.post_save()  # Run post-save hooks
            return result
        except Exception as e:
            self.handle_save_error(e)
            raise
