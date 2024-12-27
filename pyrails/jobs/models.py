from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, ValidationError


class JobTask(BaseModel):
    """
    Pydantic model for job tasks.
    """

    id: str
    class_name: str = Field(..., alias="class")
    args: list
    kwargs: dict
    enqueue_time: datetime
    status: str
    queue: str
    run_at: Optional[datetime] = None


class JobStatus(BaseModel):
    """
    Pydantic model for job status.
    """

    id: str
    status: str
    error: Optional[str] = None
