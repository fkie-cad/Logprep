ARG PYTHON_VERSION=3.11
ARG MINIMUM_UV_SUPPORTED_LOGPREP_VERSION=18.1.0
ARG LOGPREP_VERSION=dev

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

# Re-declare build arguments in this stage so they are available
ARG LOGPREP_VERSION
ARG MINIMUM_UV_SUPPORTED_LOGPREP_VERSION

ADD . /logprep
WORKDIR /logprep

# Use a python virtual environment
RUN python -m venv --upgrade-deps /opt/venv
ENV PATH="/opt/venv/bin:/root/.cargo/bin:${PATH}"

# Install uv into the venv
RUN pip install --disable-pip-version-check --no-cache-dir uv

# Use uv.lock + pyproject.toml to install logprep and its runtime deps, non-editable \
RUN if [ "$LOGPREP_VERSION" = "dev" ]; then \
        echo "Building dev from local checkout using uv.lock"; \
        # Local checkout (/logprep) must contain a valid uv.lock
        UV_PROJECT_ENVIRONMENT=/opt/venv uv sync --no-editable --frozen && \
        /opt/venv/bin/logprep --version; \
    else \
        echo "Building specific version: ${LOGPREP_VERSION}"; \
        # Decide based on MINIMUM_UV_SUPPORTED_LOGPREP_VERSION whether we rely on uv.lock
        if [ "$(printf '%s\n' "$MINIMUM_UV_SUPPORTED_LOGPREP_VERSION" "$LOGPREP_VERSION" | sort -V | head -n1)" = "$MINIMUM_UV_SUPPORTED_LOGPREP_VERSION" ]; then \
            echo "Requested version ${LOGPREP_VERSION} >= minimum (${MINIMUM_UV_SUPPORTED_LOGPREP_VERSION}) → expecting uv.lock in the repo"; \
            git clone https://github.com/fkie-cad/Logprep.git /tmp/logprep && \
            cd /tmp/logprep && \
            git checkout "$LOGPREP_VERSION" && \
            # uv.lock must exist and match pyproject.toml; --frozen enforces this
            UV_PROJECT_ENVIRONMENT=/opt/venv uv sync --no-editable --frozen && \
            /opt/venv/bin/logprep --version; \
        else \
            echo "Requested version ${LOGPREP_VERSION} < minimum (${MINIMUM_UV_SUPPORTED_LOGPREP_VERSION}) → falling back to PyPI (no uv.lock expected)"; \
            # Older releases are installed directly from PyPI without uv.lock
            UV_PROJECT_ENVIRONMENT=/opt/venv uv pip install "logprep==${LOGPREP_VERSION}" && \
            /opt/venv/bin/logprep --version; \
        fi; \
    fi

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
