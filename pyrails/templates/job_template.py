job_template = """from pyrails.jobs.jobs import Job
from pyrails.logger import logger


class {job_class_name}(Job):
    \"\"\"
    Job: {job_class_name}
    \"\"\"

    queue = "{queue_name}"
{batchable_config}
    
{perform_method}
"""
