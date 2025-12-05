FROM python:3.12-slim-trixie
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Create user and group for the application
ARG UID=1000
ARG GID=1000
RUN groupadd -g $GID app \
 && useradd -u $UID -g app -m -s /bin/bash app
USER app


# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1
# Copy from the cache instead of linking since it's a mounted volume
ENV UV_LINK_MODE=copy
WORKDIR /home/app
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --group dev
# Add the virtual environment to PATH
ENV PATH="/home/app/.venv/bin:$PATH"

# Disable bytecode compilation
ENV PYTHONDONTWRITEBYTECODE=1
# Unbuffer stdout and stderr
ENV PYTHONUNBUFFERED=1
WORKDIR /home/app/src