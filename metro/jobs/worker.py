import asyncio
import time
from typing import Type
import importlib
import pkgutil
import inspect

from metro.jobs.models import JobTask
from metro.jobs.jobs import Job, JobRegistry
from metro.logger import logger
from metro.jobs.backends.base import Backend


class MetroWorker:
    def __init__(
        self,
        backend: "Backend",
        auto_load_jobs: bool = True,
        job_modules: list[str] = None,
        job_directories: list[str] = None,
    ):
        """
        Initialize the MetroWorker.

        :param backend: An instance of Backend to interact with the job backend.
        :param auto_load: Whether to automatically load jobs from directories.
        :param job_modules: A list of module paths from which to load jobs.
        :param job_directories: A list of directories to load jobs from (used if auto_load is True).

        """
        self.backend = backend
        Job.set_backend(backend)
        self.jobs: list[Type[Job]] = []
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.shutdown_event = asyncio.Event()

        JobRegistry.clear()

        if auto_load_jobs:
            directories = job_directories if job_directories else ["app/jobs"]
            self.load_jobs_from_directories(directories)
        elif job_modules:
            self.load_jobs_from_modules(job_modules)
        else:
            logger.warning("No jobs loaded. Worker will not process any jobs.")

    def load_jobs(self):
        """
        Automatically discover and load job classes from the 'jobs' directory.
        """
        for _, module_name, _ in pkgutil.iter_modules(["jobs"]):
            module = importlib.import_module(f"jobs.{module_name}")
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if issubclass(obj, Job) and obj is not Job:
                    self.jobs.append(obj)
                    JobRegistry.register(obj)

    def load_jobs_from_directories(self, directories: list[str]):
        """
        Automatically discover and load job classes from specified directories.

        :param directories: A list of directory paths to search for job modules.
        """
        for directory in directories:
            try:
                for finder, module_name, is_pkg in pkgutil.iter_modules([directory]):
                    full_module_name = f"{directory.replace('/', '.')}.{module_name}"
                    module = importlib.import_module(full_module_name)
                    for name, obj in inspect.getmembers(module, inspect.isclass):
                        if issubclass(obj, Job) and obj is not Job:
                            self.jobs.append(obj)
                            JobRegistry.register(obj)
                            logger.info(
                                f"Loaded job class: {obj.__name__} from module: {full_module_name}"
                            )
            except Exception as e:
                logger.error(f"Failed to load jobs from directory '{directory}': {e}")

    def load_jobs_from_modules(self, modules: list[str]):
        """
        Load job classes from specified modules.

        :param modules: A list of module paths to load job classes from.
        """
        for module_path in modules:
            try:
                module = importlib.import_module(module_path)
                loaded = False
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    if issubclass(obj, Job) and obj is not Job:
                        self.jobs.append(obj)
                        JobRegistry.register(obj)
                        logger.info(
                            f"Loaded job class: {obj.__name__} from module: {module_path}"
                        )
                        loaded = True
                if not loaded:
                    logger.warning(f"No Job subclasses found in module: {module_path}")
            except ImportError as ie:
                logger.error(f"Module '{module_path}' could not be imported: {ie}")
            except Exception as e:
                logger.error(f"Failed to load jobs from module '{module_path}': {e}")

    async def execute_job(self, job_class, *args, job_id=None, **kwargs):
        """
        Execute an individual job.

        :param job_class: The class of the job to execute.
        :param args: Positional arguments for the job.
        :param job_id: The ID of the job.
        :param kwargs: Keyword arguments for the job.
        """
        if job_id:
            await self.backend.set_job_status(job_id, "running")
        try:
            job_instance = job_class()
            await job_instance.execute(*args, **kwargs)
            if job_id:
                await self.backend.set_job_status(job_id, "completed")
                logger.info(f"Job {job_id} completed successfully.")
        except Exception as e:
            logger.exception(f"Error executing job {job_class.__name__}: {e}")
            if job_id:
                await self.backend.set_job_status(job_id, "failed", str(e))

    async def execute_batch_jobs(self, job_class: Type[Job], jobs: list[JobTask]):
        """
        Execute a batch of jobs for the specified job class.

        :param job_class: The class of the job to execute in batch.
        :param jobs: A list of job data dictionaries.
        """
        try:
            # Update status to 'running' for all jobs in the batch
            for job_data in jobs:
                await self.backend.set_job_status(job_data["id"], "running")

            job_instance = job_class()
            await job_instance.execute_batch(jobs)

            # Update status to 'completed' for all jobs in the batch
            for job_data in jobs:
                await self.backend.set_job_status(job_data["id"], "completed")
            logger.info(f"Batch job {job_class.__name__} completed successfully.")
        except Exception as e:
            logger.exception(f"Error executing batch job {job_class.__name__}: {e}")
            # Update status to 'failed' for all jobs in the batch
            for job_data in jobs:
                await self.backend.set_job_status(job_data["id"], "failed", str(e))

    async def process_queue(self, queue_name: str):
        """
        Process jobs in the given queue.
        Handles both individual and batchable jobs.

        :param queue_name: The name of the queue to process.
        """
        job_classes = self._get_job_classes_for_queue(queue_name)
        batchable_job_classes = self._initialize_batch_info(job_classes)

        while True:
            try:
                job_data = await self.backend.dequeue_job(queue_name)

                if job_data:
                    await self._handle_dequeued_job(job_data, batchable_job_classes)
                else:
                    # Short sleep to prevent tight loop when queue is empty
                    await asyncio.sleep(0.1)

                await self._check_batch_intervals(batchable_job_classes)
            except Exception as e:
                logger.exception(f"Error processing queue {queue_name}: {e}")
                await asyncio.sleep(1)  # Sleep before retrying in case of error

    def _get_job_classes_for_queue(self, queue_name: str) -> list[Type[Job]]:
        """
        Retrieve all job classes assigned to the specified queue.

        :param queue_name: The name of the queue.
        :return: A list of job classes.
        """
        return [job for job in self.jobs if job.queue == queue_name]

    def _get_queues_to_process(self) -> set[str]:
        """
        Retrieve all queues that have jobs assigned to them.

        :return: A set of queue names.
        """
        return set(job.queue for job in self.jobs)

    @staticmethod
    def _initialize_batch_info(
        job_classes: list[Type[Job]],
    ) -> dict[str, dict[str, any]]:
        """
        Initialize batch information for batchable job classes.

        :param job_classes: List of job classes assigned to a queue.
        :return: A dictionary containing batch information per job class.
        """
        batchable = {}
        for job_class in job_classes:
            batch_size = getattr(job_class, "batch_size", None)
            batch_interval = getattr(job_class, "batch_interval", None)
            if batch_size or batch_interval:
                batchable[job_class.__name__] = {
                    "job_class": job_class,
                    "jobs": [],
                    "start_time": None,
                    "batch_size": batch_size,
                    "batch_interval": batch_interval,
                }
        return batchable

    async def _handle_dequeued_job(
        self, job_data: JobTask, batchable_job_classes: dict[str, dict[str, any]]
    ):
        """
        Handle a dequeued job, determining if it's batchable and processing accordingly.

        :param job_data: The job data dictionary.
        :param batchable_job_classes: Dictionary containing batch info per job class.
        """
        job_class_name = job_data["class"]
        if job_class_name in batchable_job_classes:
            await self._handle_batchable_job(
                job_data, batchable_job_classes[job_class_name]
            )
        else:
            await self._handle_non_batchable_job(job_data)

    async def _handle_batchable_job(
        self, job_data: JobTask, batch_info: dict[str, any]
    ):
        """
        Handle a batchable job by adding it to the batch and checking batch conditions.

        :param job_data: The job data dictionary.
        :param batch_info: The batch information dictionary for the job class.
        """
        batch_info["jobs"].append(job_data)
        if batch_info["start_time"] is None:
            batch_info["start_time"] = time.time()
            await self.backend.set_batch_start_time(
                batch_info["job_class"].__name__, batch_info["start_time"]
            )

        await self.backend.set_job_status(job_data["id"], "queued")
        logger.debug(
            f"Queued batchable job {job_data['id']} for batch {batch_info['job_class'].__name__}"
        )

        # Check if batch_size condition is met
        if (
            batch_info["batch_size"]
            and len(batch_info["jobs"]) >= batch_info["batch_size"]
        ):
            await self._process_batch(batch_info)

    async def _handle_non_batchable_job(self, job_data: JobTask):
        """
        Handle a non-batchable job by executing it immediately.

        :param job_data: The job data dictionary.
        """
        job_class = JobRegistry.get(job_data["class"])
        if job_class:
            await self.execute_job(
                job_class,
                *job_data.get("args", []),
                job_id=job_data.get("id"),
                **job_data.get("kwargs", {}),
            )
        else:
            logger.error(f"Unknown job class: {job_data['class']}")

    async def _process_batch(self, batch_info: dict[str, any]):
        """
        Process a batch of jobs if batch conditions are met.

        :param batch_info: The batch information dictionary for the job class.
        """
        job_class_name = batch_info["job_class"].__name__
        lock_name = f"lock:batch:{job_class_name}"
        identifier = await self.backend.acquire_lock(lock_name)

        if not identifier:
            logger.warning(
                f"Could not acquire lock for batch {job_class_name}. Batch will remain for later processing."
            )
            return

        try:
            batch_start_time = await self.backend.get_batch_start_time(job_class_name)
            jobs = await self.backend.get_batch(job_class_name)
            time_elapsed = time.time() - batch_start_time if batch_start_time else 0

            if (batch_info["batch_size"] and len(jobs) >= batch_info["batch_size"]) or (
                batch_info["batch_interval"]
                and time_elapsed >= batch_info["batch_interval"]
            ):
                await self.execute_batch_jobs(batch_info["job_class"], jobs)
                await self.backend.clear_batch(job_class_name)
        finally:
            await self.backend.release_lock(lock_name, identifier)

    async def _check_batch_intervals(
        self, batchable_job_classes: dict[str, dict[str, any]]
    ):
        """
        Check if any batch intervals have been met and process the batch if necessary.

        :param batchable_job_classes: Dictionary containing batch info per job class.
        """
        for batch_name, batch_info in batchable_job_classes.items():
            if batch_info["batch_interval"] and batch_info["jobs"]:
                time_elapsed = time.time() - batch_info["start_time"]
                if time_elapsed >= batch_info["batch_interval"]:
                    await self._process_batch(batch_info)

    async def process_scheduled_jobs(self):
        while not self.shutdown_event.is_set():
            try:
                due_jobs = await self.backend.get_due_jobs()
                for job in due_jobs:
                    await self.backend.enqueue_job(job.queue, job)
                    await self.backend.remove_scheduled_job(job.id, job.queue)
                    await self.backend.set_job_status(job.id, "queued")
                await asyncio.sleep(1)  # Adjust the sleep interval as needed
            except Exception as e:
                logger.exception(f"Error processing scheduled jobs: {e}")
                await asyncio.sleep(5)  # Backoff on error

    async def start(self):
        # Start processing queues
        tasks = []
        # queue_names = set(job.queue for job in self.jobs)
        queue_names = self._get_queues_to_process()
        for queue_name in queue_names:
            tasks.append(asyncio.create_task(self.process_queue(queue_name)))
            logger.info(f"Started processing queue: {queue_name}")

        # Start scheduler
        tasks.append(asyncio.create_task(self.process_scheduled_jobs()))
        logger.info("Started scheduled jobs processor.")
        await asyncio.gather(*tasks, return_exceptions=True)
        await self.shutdown_event.wait()

    def run(self):
        try:
            self.loop.create_task(self.start())
            self.loop.run_forever()
        except KeyboardInterrupt:
            logger.info("Worker shutting down...")
            self.loop.run_until_complete(self.shutdown())
        finally:
            self.loop.close()

    async def shutdown(self):
        # Implement graceful shutdown logic
        self.shutdown_event.set()
        await self.backend.close()
        logger.info("Worker shutdown complete.")
