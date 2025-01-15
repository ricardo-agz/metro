model_template = """from metro.models import * {additional_imports}


class {resource_name_pascal}({base_classes}):
{fields}
    meta = {{
        "collection": "{resource_name_snake}",{meta_indexes}
    }}
"""
