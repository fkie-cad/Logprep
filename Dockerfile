ARG PYTHON_VERSION=3.11
FROM registry-1.docker.io/library/python:${PYTHON_VERSION} AS base

# remove setuptools as installed by the python image
# setuptools is not needed at runtime and is vulnerable by CVE-2024-6345
RUN pip3 uninstall \
    --disable-pip-version-check \
    --no-cache-dir \
    --yes \
    'setuptools' \
    'wheel'

FROM base AS prebuild

# Install git (needed for cloning Logprep in some build paths)
RUN apt-get update && \
    apt-get install -y git && \
    rm -rf /var/lib/apt/lists/*

# Install the Rust toolchain
RUN curl https://sh.rustup.rs -sSf | bash -s -- -y
FROM prebuild AS build

ADD . /logprep
WORKDIR /logprep

# Use a python virtual environment
RUN python -m venv --upgrade-deps /opt/venv
ENV PATH="/opt/venv/bin:/root/.cargo/bin:${PATH}"

# Install uv into the venv
RUN pip install --disable-pip-version-check --no-cache-dir uv

# Local checkout (/logprep) must contain a valid uv.lock
RUN echo "Building dev from local checkout using uv.lock"; \
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
