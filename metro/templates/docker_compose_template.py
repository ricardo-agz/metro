docker_compose_template = """version: '3.8'

services:
  web:
    build: .
    ports:
      - "8000:8000"
    environment:
      - METRO_ENV=development
      - METRO_DOCKER_MODE=true
      - DATABASE_URL=mongodb://mongo:27017
    depends_on:
      - mongo
    volumes:
      - .:/app
    command: python -m uvicorn {project_name}.main:app --host 0.0.0.0 --port 8000 --reload

  mongo:
    image: mongo:latest
    ports:
      - "27017:27017"
    volumes:
      - mongodb_data:/data/db

volumes:
  mongodb_data:
"""
