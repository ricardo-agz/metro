from typing import Optional, Callable


def job_config(
    queue: str = "default",
    batch_size: Optional[int] = None,
    batch_interval: Optional[int] = None,
):
    """
    Decorator to add configuration to a job class.

    :param queue: The queue name for the job.
    :param batch_size: The number of jobs to batch before processing.
    :param batch_interval: The time interval in seconds to batch jobs.
    """

    def decorator(cls):
        if batch_size is not None and batch_size <= 0:
            raise ValueError("batch_size must be greater than 0.")
        if batch_interval is not None and batch_interval <= 0:
            raise ValueError("batch_interval must be greater than 0.")
        cls.queue = queue
        cls.batch_size = batch_size
        cls.batch_interval = batch_interval
        return cls

    return decorator


def before_perform(func: Callable):
    """
    Decorator to add a before_perform hook to a job class.
    """
    func._is_before_perform_hook = True
    return func


def after_perform(func: Callable):
    """
    Decorator to add an after_perform hook to a job class.
    """
    func._is_after_perform_hook = True
    return func


def before_perform_batch(func: Callable):
    """
    Decorator to add a before_perform_batch hook to a batchable job class.
    """
    func._is_before_perform_batch_hook = True
    return func


def after_perform_batch(func: Callable):
    """
    Decorator to add an after_perform_batch hook to a batchable job class.
    """
    func._is_after_perform_batch_hook = True
    return func
