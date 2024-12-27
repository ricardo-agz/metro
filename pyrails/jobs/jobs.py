import inspect
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, Type, Callable
from pyrails.jobs.backends.base import Backend
from pyrails.logger import logger
from .models import JobTask, JobStatus


class Job(ABC):
    """
    Abstract base class for all jobs.
    """

    queue: str = "default"
    backend: "Backend" = None
    batch_size: Optional[int] = None
    batch_interval: Optional[int] = None

    # Hook lists
    _before_perform_hooks: list[Callable] = []
    _after_perform_hooks: list[Callable] = []
    _before_perform_batch_hooks: list[Callable] = []
    _after_perform_batch_hooks: list[Callable] = []

    @classmethod
    def set_backend(cls, backend: "Backend"):
        cls.backend = backend

    @classmethod
    def check_backend(cls):
        if cls.backend is None:
            raise ValueError("Backend not set for Job class.")

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # Initialize hook lists
        cls._before_perform_hooks = []
        cls._after_perform_hooks = []
        cls._before_perform_batch_hooks = []
        cls._after_perform_batch_hooks = []

        # Register hooks based on decorators
        for attr_name, attr in inspect.getmembers(cls, predicate=inspect.isfunction):
            if callable(attr):
                if getattr(attr, "_is_before_perform_hook", False):
                    cls._before_perform_hooks.append(attr)
                if getattr(attr, "_is_after_perform_hook", False):
                    cls._after_perform_hooks.append(attr)
                if getattr(attr, "_is_before_perform_batch_hook", False):
                    cls._before_perform_batch_hooks.append(attr)
                if getattr(attr, "_is_after_perform_batch_hook", False):
                    cls._after_perform_batch_hooks.append(attr)

        if (cls.batch_size is not None) or (cls.batch_interval is not None):
            if not hasattr(cls, "perform_batch") or not callable(
                getattr(cls, "perform_batch")
            ):
                raise NotImplementedError(
                    "Batchable jobs must implement `perform_batch` method."
                )
        else:
            if hasattr(cls, "perform_batch"):
                raise AttributeError(
                    "Non-batchable jobs should not implement `perform_batch` method."
                )

    @classmethod
    async def enqueue(cls, *args, **kwargs) -> str:
        """
        Enqueue a job for immediate execution.
        Returns a job ID.
        """
        cls.check_backend()

        job_id = str(uuid.uuid4())
        job_data = JobTask(
            id=job_id,
            class_name=cls.__name__,
            args=args,
            kwargs=kwargs,
            enqueue_time=datetime.utcnow(),
            status="queued",
            queue=cls.queue,
        )

        await cls.backend.enqueue_job(cls.queue, job_data)
        await cls.backend.set_job_status(job_id, "queued")
        return job_id

    @classmethod
    async def schedule(cls, run_at: datetime, *args, **kwargs) -> str:
        """
        Schedule a job to be executed at a specific time.
        Returns a job ID.
        """
        cls.check_backend()

        delay = (run_at - datetime.utcnow()).total_seconds()
        if delay <= 0:
            return await cls.enqueue(*args, **kwargs)
        job_id = str(uuid.uuid4())
        job_data = JobTask(
            id=job_id,
            class_name=cls.__name__,
            args=args,
            kwargs=kwargs,
            enqueue_time=datetime.utcnow(),
            status="scheduled",
            queue=cls.queue,
            run_at=run_at,
        )

        await cls.backend.schedule_job(delay, cls.queue, job_data.dict(by_alias=True))
        await cls.backend.set_job_status(job_id, "scheduled")
        return job_id

    @classmethod
    async def enqueue_batch(cls, *args, **kwargs) -> str:
        """
        Enqueue a job for batch processing.
        Returns a job ID.
        """
        cls.check_backend()
        if cls.batch_size is None or cls.batch_interval is None:
            raise ValueError("Batch size and interval must be set for batchable jobs.")

        job_id = str(uuid.uuid4())
        job_data = JobTask(
            id=job_id,
            class_name=cls.__name__,
            args=args,
            kwargs=kwargs,
            enqueue_time=datetime.utcnow(),
            status="batch_queued",
            queue=cls.queue,
        )

        await cls.backend.add_to_batch(cls.__name__, job_data)
        await cls.backend.set_job_status(job_id, "batch_queued")
        return job_id

    @classmethod
    async def get_status(cls, job_id: str) -> JobStatus:
        """
        Get the status of a job.
        """
        cls.check_backend()

        return await cls.backend.get_job_status(job_id)

    @abstractmethod
    async def perform(self, *args, **kwargs):
        """
        The method containing the job logic.
        Must be implemented by subclasses.
        """
        pass

    @abstractmethod
    async def perform_batch(self, jobs: list[JobTask]):
        """
        The method containing the batch job logic.
        Must be implemented by subclasses.
        """
        pass

    # Hook execution methods
    async def run_before_hooks(self, *args, **kwargs):
        for hook in self._before_perform_hooks:
            await hook(self, *args, **kwargs)

    async def run_after_hooks(self, *args, **kwargs):
        for hook in self._after_perform_hooks:
            await hook(self, *args, **kwargs)

    async def run_before_batch_hooks(self, jobs: list[JobTask]):
        for hook in self._before_perform_batch_hooks:
            await hook(self, jobs)

    async def run_after_batch_hooks(self, jobs: list[JobTask]):
        for hook in self._after_perform_batch_hooks:
            await hook(self, jobs)

    # Execution methods
    async def execute(self, *args, **kwargs):
        """
        Execute an individual job, running before and after hooks.

        :param args: Positional arguments for the job.
        :param kwargs: Keyword arguments for the job.
        """
        await self.run_before_hooks(*args, **kwargs)
        await self.perform(*args, **kwargs)
        await self.run_after_hooks(*args, **kwargs)

    async def execute_batch(self, jobs: list[JobTask]):
        """
        Execute a batch of jobs, running before and after batch hooks.

        :param jobs: A list of job data dictionaries.
        """
        await self.run_before_batch_hooks(jobs)
        await self.perform_batch(jobs)
        await self.run_after_batch_hooks(jobs)


class JobRegistry:
    """
    A simple job registry to keep track of all job classes.
    """

    _registry: dict[str, Type[Job]] = {}

    @classmethod
    def register(cls, job_class: Type[Job]):
        """
        Register a job class.

        :param job_class: The job class to register.
        """
        cls._registry[job_class.__name__] = job_class

    @classmethod
    def get(cls, job_class_name: str) -> Optional[Type[Job]]:
        """
        Retrieve a job class by its name.

        :param job_class_name: The name of the job class.
        :return: The job class or None if not found.
        """
        return cls._registry.get(job_class_name)

    @classmethod
    def all_jobs(cls) -> list[Type[Job]]:
        """
        Get all registered job classes.

        :return: A list of all registered job classes.
        """
        return list(cls._registry.values())

    @classmethod
    def clear(cls):
        """
        Clear the job registry.

        :return: None
        """
        cls._registry.clear()
