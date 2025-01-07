job_template = """from metro.jobs.jobs import Job
from metro.logger import logger


class {job_class_name}(Job):
    \"\"\"
    Job: {job_class_name}
    \"\"\"

    queue = "{queue_name}"
{batchable_config}
    
{perform_method}
"""
