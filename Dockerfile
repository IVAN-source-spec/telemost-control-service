FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=false

WORKDIR /app

RUN python -m pip install --upgrade pip setuptools wheel poetry

COPY pyproject.toml poetry.lock* /app/

RUN poetry install --no-interaction --no-ansi --no-root

COPY api_run.py README.md /app/
COPY control_service /app/control_service

EXPOSE 8010

CMD ["python", "api_run.py"]
