dockerignore_template = """# Git
.git
.gitignore

# Python
__pycache__
*.pyc
*.pyo
*.pyd
.Python
env
pip-log.txt
pip-delete-this-directory.txt
.tox
.coverage
.coverage.*
.cache
nosetests.xml
coverage.xml
*.cover
*.log
.mypy_cache
.pytest_cache
.hypothesis

# Virtual environment
venv
.env

# PyCharm
.idea

# VS Code
.vscode

# Jupyter Notebook
.ipynb_checkpoints

# Metro specific
*.sqlite3

# OS generated files
.DS_Store
.DS_Store?
._*
.Spotlight-V100
.Trashes
ehthumbs.db
Thumbs.db

# Docker
docker-compose.override.yml

# MongoDB
data/db/

# Temporary files
*.swp
*.swo
*~
"""
