from setuptools import setup, find_packages

setup(
    name="pyrails",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        "fastapi",
        "mongoengine",
        "uvicorn",
        "click",
        "inflect",
        "python-dotenv",
        "hashlib",
        "pydantic",
        "cryptography",
        "websockets",
        "bcrypt",
        "jinja2",
        "requests",
        "httpx",
    ],
    entry_points="""
        [console_scripts]
        pyrails=pyrails.cli:cli
    """,
)
