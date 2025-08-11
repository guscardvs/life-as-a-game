# syntax=docker/dockerfile:1
FROM ghcr.io/astral-sh/uv:python3.13-alpine



# Copy the project into the image
ADD . /app

# Sync the project into a new environment, asserting the lockfile is up to date
WORKDIR /app
RUN uv sync --locked

EXPOSE 18000
ENV CONFIG_ENV=prd

CMD ["uv", "run", "python", "-m", "app.cli"]
