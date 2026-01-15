# syntax=docker/dockerfile:1.7

ARG PYTHON_VERSION=3.11

FROM registry-1.docker.io/library/python:${PYTHON_VERSION} AS build

# remove setuptools as installed by the python image
# setuptools is not needed at runtime and is vulnerable by CVE-2024-6345
RUN pip3 uninstall \
    --disable-pip-version-check \
    --no-cache-dir \
    --yes \
    'setuptools' \
    'wheel'

# Install git (needed for cloning Logprep in some build paths)
RUN apt-get update && \
    apt-get install -y git && \
    rm -rf /var/lib/apt/lists/*

# Use a python virtual environment
RUN python -m venv --upgrade-deps /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

# Install uv into the venv
RUN pip install --disable-pip-version-check --no-cache-dir uv

WORKDIR /logprep

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1

# Copy from the cache instead of linking since it's a mounted volume
ENV UV_LINK_MODE=copy

# Omit development dependencies
ENV UV_NO_DEV=1

# Ensure installed tools can be executed out of the box
ENV UV_TOOL_BIN_DIR=/usr/local/bin

# Install deps using only the lockfile + pyproject first (best layer caching)
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=/logprep/uv.lock,readonly \
    --mount=type=bind,source=pyproject.toml,target=/logprep/pyproject.toml,readonly \
    UV_PROJECT_ENVIRONMENT=/opt/venv uv sync --no-install-project --no-editable --frozen

# Then copy the rest of the project
COPY . /logprep

# Use uv.lock + pyproject.toml to install logprep and its runtime deps, non-editable \
RUN --mount=type=cache,target=/root/.cache/uv \
    UV_PROJECT_ENVIRONMENT=/opt/venv uv sync --no-editable --frozen && \
    /opt/venv/bin/logprep --version

# geoip2 4.8.0 lists a vulnerable setuptools version as a dependency. setuptools is unneeded at runtime, so it is uninstalled.
# More recent (currently unreleased) versions of geoip2 removed setuptools from dependencies.
RUN pip uninstall -y setuptools


FROM registry-1.docker.io/library/python:${PYTHON_VERSION}-slim AS prod
ARG http_proxy
ARG https_proxy

# remove setuptools as installed by the python image
# setuptools is not needed at runtime and is vulnerable by CVE-2024-6345
RUN pip3 uninstall \
    --disable-pip-version-check \
    --no-cache-dir \
    --yes \
    'setuptools' \
    'wheel'

RUN apt-get update && apt-get -y upgrade && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY --from=build /opt/venv /opt/venv
RUN useradd -s /bin/sh -m -c "logprep user" logprep
USER logprep

# Make sure we use the virtualenv:
ENV PATH="/opt/venv/bin:${PATH}"
WORKDIR /home/logprep

ENTRYPOINT ["logprep"]
