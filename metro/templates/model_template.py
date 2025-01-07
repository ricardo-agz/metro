model_template = """from metro.models import *


class {resource_name_pascal}(BaseModel):
{fields}
    meta = {{
        "collection": "{resource_name_snake}"
    }}
"""
