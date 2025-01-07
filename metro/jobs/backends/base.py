from abc import ABC, abstractmethod
from metro.jobs.models import JobTask, JobStatus


class Backend(ABC):
    """
    Abstract base class for backend implementations.
    """

    @abstractmethod
    async def enqueue_job(self, queue_name: str, job_data: JobTask):
        pass

    @abstractmethod
    async def schedule_job(self, delay: float, queue_name: str, job_data: JobTask):
        pass

    @abstractmethod
    async def remove_scheduled_job(self, job_id: str, queue_name: str):
        pass

    @abstractmethod
    async def get_due_jobs(self, queue_name: str) -> list[JobTask]:
        """
        Get all jobs within a queue that are due to run.
        :param queue_name: The name of the queue.
        :return: A list of job tasks.
        """
        pass

    @abstractmethod
    async def dequeue_job(self, queue_name: str) -> JobTask | None:
        pass

    @abstractmethod
    async def add_to_batch(self, batch_name: str, job_data: JobTask):
        pass

    @abstractmethod
    async def get_batch_size(self, batch_name: str) -> int:
        pass

    @abstractmethod
    async def get_batch(self, batch_name: str) -> list[JobTask]:
        pass

    @abstractmethod
    async def clear_batch(self, batch_name: str):
        pass

    @abstractmethod
    async def set_batch_start_time(self, batch_name: str, start_time: float):
        pass

    @abstractmethod
    async def get_batch_start_time(self, batch_name: str) -> float | None:
        pass

    @abstractmethod
    async def acquire_lock(self, lock_name: str, timeout: int = 10) -> str | None:
        pass

    @abstractmethod
    async def release_lock(self, lock_name: str, identifier: str):
        pass

    @abstractmethod
    async def set_job_status(
        self, job_id: str, status: str, error_message: str | None = None
    ):
        """
        Set the status of a job.

        :param job_id: The unique identifier of the job.
        :param status: The status to set (e.g., 'queued', 'running', 'completed', 'failed').
        :param error_message: Optional error message if the job failed.
        """
        pass

    @abstractmethod
    async def get_job_status(self, job_id: str) -> JobStatus:
        """
        Get the status of a job by job ID.

        :param job_id: The unique identifier of the job.
        :return: A dictionary containing the job's status and error message if any.
        """
        pass

    @abstractmethod
    def close(self):
        pass
