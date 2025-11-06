FROM python:3.13-alpine

RUN addgroup --system --gid 1001 backend
RUN adduser --system --uid 1001 backend

WORKDIR /app
COPY pyproject.toml .
COPY uv.lock .

RUN apk update --no-cache
RUN apk upgrade --no-cache
RUN apk add --no-cache openjdk17-jdk uv build-base
RUN uv venv
RUN uv pip install .

RUN apk del build-base

COPY ./app /app

EXPOSE 8000

USER backend

ENTRYPOINT [ ".venv/bin/fastapi", "run" ]
