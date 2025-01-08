dockerfile_template = """# Use an official Python runtime as a parent image
FROM python:3.11

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \\
    PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y gcc

# Create non-root user
RUN adduser --disabled-password --gecos '' appuser

# Copy project requirements file
COPY ./requirements.txt /app/requirements.txt

# Install project dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the current directory contents into the container at /app
COPY . /app/

# Change ownership of the app directory to appuser
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Uvicorn will listen on this port
EXPOSE 8000

# Install private dependencies and run uvicorn server
CMD uvicorn main:app --host 0.0.0.0 --port 8000
"""
