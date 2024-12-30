import os
from jinja2 import Environment, FileSystemLoader
from fastapi.templating import Jinja2Templates


TEMPLATES_PATH = os.path.join(os.path.dirname(__file__))


env = Environment(
    loader=FileSystemLoader(TEMPLATES_PATH),
)
TEMPLATE_GLOBALS = {
    # Basic built-ins
    "len": len,
    "min": min,
    "max": max,
    "sum": sum,
    "abs": abs,
    "round": round,
    "enumerate": enumerate,
    "range": range,
    "zip": zip,
    # Type conversion
    "int": int,
    "float": float,
    "str": str,
    "bool": bool,
    "list": list,
    "dict": dict,
    "set": set,
    # Other useful builtins
    "all": all,
    "any": any,
    "sorted": sorted,
    "filter": filter,
    "map": map,
}
env.globals.update(TEMPLATE_GLOBALS)

templates = Jinja2Templates(directory=TEMPLATES_PATH)
templates.env = env


__all__ = ["templates"]
