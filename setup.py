from setuptools import setup, find_packages

setup(
    name="metro",
    version="0.1",
    packages=find_packages(exclude=["docs*", "conductor*"]),
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
    extras_require={
        "conductor": [
            "openai~=1.59.5",
            "anthropic~=0.42.0",
            "keyring>=24.0.0",
            "inquirer>=3.1.3",
        ]
    },
    entry_points={
        "console_scripts": [
            "metro=metro.cli:cli",
        ],
        "metro.plugins": [
            "conductor=conductor.cli:register_commands",
        ],
    },
)
