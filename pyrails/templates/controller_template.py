controller_template = """from pyrails.controllers import Controller, get, post, put, delete


class {pascal_case_name}Controller(Controller):
{methods_code}
"""
