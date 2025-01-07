import uuid

import aioredis
import asyncio
import json
import time
from typing import Any, Dict, List, Optional

from pydantic import ValidationError

from metro.jobs.backends.base import Backend
from metro.jobs.models import JobTask, JobStatus
from metro.logger import logger


class RedisBackend(Backend):
    """
    Redis implementation of the Backend interface.
    """

    def __init__(
        self,
        redis_url: Optional[str] = None,
        host: Optional[str] = None,
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        ssl: bool = False,
        **kwargs,
    ):
        """
        Initialize the Redis client with flexible connection parameters.
        You can provide a redis_url or host and other parameters.

        :param redis_url: The Redis URL.
        :param host: The Redis host.
        :param port: The Redis port.
        :param db: The Redis database number.
        :param password: The Redis password.
        :param ssl: Whether to use SSL.
        :param kwargs: Additional arguments for Redis.
        """
        self.redis = None
        self.lock_prefix = "lock:"
        if redis_url:
            # Use the provided Redis URL
            self.redis = aioredis.from_url(redis_url, decode_responses=True, **kwargs)
        elif host:
            # Build the Redis connection with provided parameters
            self.redis = aioredis.Redis(
                host=host,
                port=port,
                db=db,
                password=password,
                ssl=ssl,
                decode_responses=True,
                **kwargs,
            )
        else:
            raise ValueError("Either redis_url or host must be provided.")

    async def enqueue_job(self, queue_name: str, job_data: JobTask):
        """
        Enqueue a job into the specified queue.

        :param queue_name: The name of the queue.
        :param job_data: The job data object.
        """
        try:
            job_json = job_data.json(by_alias=True)
            async with self.redis.pipeline() as pipe:
                await pipe.lpush(f"queue:{queue_name}", job_json)
                await pipe.execute()
            logger.debug(f"Enqueued job {job_data['id']} to queue {queue_name}.")
        except Exception as e:
            logger.error(f"Failed to enqueue job: {e}")
            raise

    async def schedule_job(self, delay: float, queue_name: str, job_data: JobTask):
        """
        Schedule a job to be enqueued after a certain delay.

        :param delay: Delay in seconds.
        :param queue_name: The name of the queue.
        :param job_data: The job data dictionary.
        """
        try:
            score = time.time() + delay
            job_json = job_data.json(by_alias=True)
            await self.redis.zadd(f"scheduled_jobs:{queue_name}", {job_json: score})
            logger.debug(
                f"Scheduled job {job_data['id']} to queue {queue_name} after {delay} seconds."
            )
        except Exception as e:
            logger.error(f"Failed to schedule job: {e}")
            raise

    async def remove_scheduled_job(self, job_id: str, queue_name: str):
        """
        Remove a scheduled job from the scheduled_jobs sorted set.

        :param job_id: The unique identifier of the job.
        :param queue_name: The name of the queue.
        """
        try:
            # Fetch the job JSON by matching the job_id
            job_keys = await self.redis.zrange(f"scheduled_jobs:{queue_name}", 0, -1)
            for job_json in job_keys:
                job_data = json.loads(job_json)
                if job_data["id"] == job_id:
                    await self.redis.zrem(f"scheduled_jobs:{queue_name}", job_json)
                    logger.debug(f"Removed scheduled job {job_id}.")
                    break
        except Exception as e:
            logger.error(f"Failed to remove scheduled job {job_id}: {e}")
            raise

    async def get_due_jobs(self, queue_name: str) -> list[JobTask]:
        """
        Get all jobs that are due to be executed.

        :return: A list of job data dictionaries.
        """
        try:
            now = time.time()
            job_json_list = await self.redis.zrangebyscore(
                f"scheduled_jobs:{queue_name}", 0, now
            )
            jobs = [JobTask(**json.loads(job_json)) for job_json in job_json_list]
            logger.debug(f"Retrieved {len(jobs)} due jobs.")
            return jobs
        except Exception as e:
            logger.error(f"Failed to get due jobs: {e}")
            raise

    async def dequeue_job(self, queue_name: str) -> Optional[JobTask]:
        """
        Dequeue a job from the specified queue.

        :param queue_name: The name of the queue.
        :return: The job data dictionary or None if the queue is empty.
        """
        try:
            job_json = await self.redis.rpop(f"queue:{queue_name}")
            if job_json:
                job_data = JobTask.parse_raw(job_json)
                logger.debug(f"Dequeued job {job_data.id} from queue {queue_name}.")
                return job_data
            return None
        except ValidationError as ve:
            logger.error(f"Invalid job data: {ve}")
            return None
        except Exception as e:
            logger.error(f"Failed to dequeue job: {e}")
            return None

    async def add_to_batch(self, batch_name: str, job_data: JobTask):
        """
        Add a job to a batch queue.

        :param batch_name: The name of the batch.
        :param job_data: The job data dictionary.
        """
        try:
            job_json = job_data.json(by_alias=True)
            await self.redis.lpush(f"batch:{batch_name}", job_json)
            logger.debug(f"Added job {job_data.id} to batch {batch_name}.")
        except Exception as e:
            logger.error(f"Failed to add job to batch: {e}")
            raise

    async def get_batch_size(self, batch_name: str) -> int:
        """
        Get the size of a batch queue.

        :param batch_name: The name of the batch.
        :return: The number of jobs in the batch.
        """
        try:
            size = await self.redis.llen(f"batch:{batch_name}")
            logger.debug(f"Batch {batch_name} size: {size}.")
            return size
        except Exception as e:
            logger.error(f"Failed to get batch size: {e}")
            return 0

    async def get_batch(self, batch_name: str) -> list[JobTask]:
        """
        Retrieve all jobs in a batch queue.

        :param batch_name: The name of the batch.
        :return: A list of job data dictionaries.
        """
        try:
            job_json_list = await self.redis.lrange(f"batch:{batch_name}", 0, -1)
            jobs = [JobTask.parse_raw(job_json) for job_json in job_json_list]
            logger.debug(f"Retrieved {len(jobs)} jobs from batch {batch_name}.")
            return jobs
        except ValidationError as ve:
            logger.error(f"Invalid job data: {ve}")
            return []
        except Exception as e:
            logger.error(f"Failed to get batch: {e}")
            return []

    async def clear_batch(self, batch_name: str):
        """
        Clear all jobs in a batch queue.

        :param batch_name: The name of the batch.
        """
        try:
            async with self.redis.pipeline() as pipe:
                await pipe.delete(f"batch:{batch_name}")
                await pipe.hdel("batch_start_times", batch_name)
                await pipe.execute()
            logger.debug(f"Cleared batch {batch_name}.")
        except Exception as e:
            logger.error(f"Failed to clear batch: {e}")
            raise

    async def set_batch_start_time(self, batch_name: str, start_time: float):
        """
        Set the start time of a batch.

        :param batch_name: The name of the batch.
        :param start_time: The start time as a Unix timestamp.
        """
        try:
            await self.redis.hset("batch_start_times", batch_name, start_time)
            logger.debug(f"Set batch {batch_name} start time to {start_time}.")
        except Exception as e:
            logger.error(f"Failed to set batch start time: {e}")
            raise

    async def get_batch_start_time(self, batch_name: str) -> Optional[float]:
        """
        Get the start time of a batch.

        :param batch_name: The name of the batch.
        :return: The start time as a Unix timestamp or None if not set.
        """
        try:
            start_time = await self.redis.hget("batch_start_times", batch_name)
            if start_time:
                return float(start_time)
            return None
        except Exception as e:
            logger.error(f"Failed to get batch start time: {e}")
            return None

    async def acquire_lock(self, lock_name: str, timeout: int = 10) -> str | None:
        """
        Acquire a distributed lock.

        :param lock_name: The name of the lock.
        :param timeout: The maximum time to wait for the lock in seconds.
        :return: A unique identifier if the lock is acquired, otherwise None.
        """
        lock_key = f"{self.lock_prefix}{lock_name}"
        identifier = str(uuid.uuid4())
        end_time = time.time() + timeout
        while time.time() < end_time:
            try:
                result = await self.redis.set(lock_key, identifier, nx=True, ex=timeout)
                if result:
                    logger.debug(f"Acquired lock: {lock_key}")
                    return identifier
                await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(f"Error acquiring lock {lock_key}: {e}")
                await asyncio.sleep(0.1)
        logger.warning(f"Failed to acquire lock: {lock_key}")
        return None

    async def release_lock(self, lock_name: str, identifier: str):
        """
        Release a distributed lock.

        :param lock_name: The name of the lock.
        :param identifier: The unique identifier used to acquire the lock.
        """
        lock_key = f"{self.lock_prefix}{lock_name}"
        # Use a Lua script to ensure that the lock is only released if it's owned
        lua_script = """
                if redis.call("get", KEYS[1]) == ARGV[1] then
                    return redis.call("del", KEYS[1])
                else
                    return 0
                end
                """
        result = await self.redis.eval(lua_script, 1, lock_key, identifier)
        if result:
            logger.debug(f"Released lock: {lock_key}")
        else:
            logger.warning(f"Failed to release lock (not owner): {lock_key}")

    async def set_job_status(
        self, job_id: str, status: str, error_message: Optional[JobStatus] = None
    ):
        """
        Set the status of a job.

        :param job_id: The unique identifier of the job.
        :param status: The status to set (e.g., 'queued', 'running', 'completed', 'failed').
        :param error_message: Optional error message if the job failed.
        """
        key = f"job_status:{job_id}"
        try:
            job_status = JobStatus(id=job_id, status=status, error=error_message)
            mapping = job_status.dict(by_alias=True)
            await self.redis.hset(key, mapping=mapping)
            logger.debug(f"Set status of job {job_id} to {status}.")
        except Exception as e:
            logger.error(f"Failed to set job status: {e}")
            raise

    async def get_job_status(self, job_id: str) -> Optional[JobStatus]:
        """
        Get the status of a job by job ID.

        :param job_id: The unique identifier of the job.
        :return: A JobStatus object containing the job's status and error message if any.
        """
        key = f"job_status:{job_id}"
        try:
            status_data_raw = await self.redis.hgetall(key)
            status_data = JobStatus(**status_data_raw)
            logger.debug(f"Retrieved status for job {job_id}: {status_data_raw}")
            return status_data
        except Exception as e:
            logger.error(f"Failed to get job status: {e}")
            return None

    async def close(self):
        """
        Close the Redis connection.
        """
        if self.redis:
            await self.redis.close()
            logger.debug("Closed Redis connection.")
        else:
            logger.warning("Redis connection is not open.")
