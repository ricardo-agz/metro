# Installation

Create and activate a virtual environment and then install Metro.

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

<details>
<summary>Virtual Environment Setup</summary>

<Tabs>
  <TabItem value="unix" label="macOS/Linux">

```bash
# Create a virtual environment
python -m venv venv

# Activate the virtual environment
source venv/bin/activate

# Verify activation
which python
```

  </TabItem>
  <TabItem value="windows" label="Windows">

```bash
# Create a virtual environment
python -m venv venv

# Activate the virtual environment
venv\Scripts\activate

# Verify activation
where python
```

  </TabItem>
</Tabs>

</details>

## Requirements

Metro is built on top of:

* [FastAPI](https://fastapi.tiangolo.com) / [Starlette](https://www.starlette.io/) for the web parts
* [MongoEngine](http://mongoengine.org/) for the database

## Installing Metro

<Tabs>
  <TabItem value="pip" label="Using pip" default>

```bash
pip install metro
```

  </TabItem>
  <TabItem value="source" label="From source">

```bash
git clone https://github.com/ricardo-agz/pyrails.git
cd metro
pip install -e .
```

  </TabItem>
</Tabs>

## Creating a New Project

```bash
metro new my_project
cd my_project
```

## Running Your Project

```bash
# Start MongoDB (if not running)
metro db up

# Start the development server
metro run
```

:::note Verify Installation
After installation, you can verify Metro is correctly installed:
```bash
metro --version
```
:::