from setuptools import setup, find_packages

setup(
    name="metro",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        "fastapi",
        "mongoengine",
        "uvicorn",
        "click",
        "inflect",
        "python-dotenv",
        "cryptography",
        "websockets",
        "bcrypt",
        "jinja2",
        "pyjwt~=2.10.1",
    ],
    entry_points="""
        [console_scripts]
        metro=metro.cli:cli
    """,
)
