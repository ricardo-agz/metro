worker_template = """from metro.worker import MetroWorker
from metro.jobs.backends.redis_backend import RedisBackend
from contextlib import asynccontextmanager
from {job_modules_import} import *

@asynccontextmanager
async def lifespan(worker: MetroWorker):
    worker.connect_db()
    yield

backend = RedisBackend(host="{backend_host}", port={backend_port}, db={backend_db})

worker = MetroWorker(
    backend=backend,
    auto_load=True,
    job_directories={job_directories},
    lifespan=lifespan
)

if __name__ == "__main__":
    worker.run()
"""
