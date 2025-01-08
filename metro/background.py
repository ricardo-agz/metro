from fastapi import BackgroundTasks as FastAPIBgTasks


class BackgroundTasks(FastAPIBgTasks):
    def add_task(self, func, *args, **kwargs):
        super().add_task(func, *args, **kwargs)
