controller_template = """from metro.controllers import Controller, Request, get, post, put, delete


class {pascal_case_name}Controller(Controller):
{methods_code}
"""
