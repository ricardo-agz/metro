from setuptools import setup, find_packages


with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()


setup(
    name="metroapi",
    version="0.0.9",
    author="Ricardo Gonzalez",
    author_email="ricardo@rgon.me",
    description="Metro: A batteries-included web framework for the fastest development experience.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/ricardo-agz/metro",
    packages=find_packages(exclude=["docs*", "conductor*"]),
    keywords=["web", "framework", "api"],
    install_requires=[
        "fastapi>=0.68.0,<1.0.0",
        "mongoengine>=0.24.0",
        "uvicorn>=0.15.0",
        "click>=8.0.0",
        "inflect>=5.3.0",
        "python-dotenv>=0.19.0",
        "cryptography>=35.0.0",
        "websockets>=10.0",
        "bcrypt>=3.2.0",
        "jinja2>=3.0.0",
        "pyjwt~=2.10.1",
        "certifi>=2024.12.14",
        "python-multipart~=0.0.20",
        "black~=24.10.0",
        "isort~=5.13.2",
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
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Internet :: WWW/HTTP :: WSGI :: Application",
        "Topic :: Software Development :: Libraries :: Application Frameworks",
    ],
    python_requires=">=3.9",
)
