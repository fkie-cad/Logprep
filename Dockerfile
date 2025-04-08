ARG PYTHON_VERSION=3.11

FROM registry-1.docker.io/library/python:${PYTHON_VERSION} AS base
ARG LOGPREP_VERSION=latest

# remove setuptools as installed by the python image
# setuptools is not needed at runtime and is vulnerable by CVE-2024-6345
RUN pip3 uninstall \
    --disable-pip-version-check \
    --no-cache-dir \
    --yes \
    'setuptools' \
    'wheel'

FROM base AS prebuild

# Install the Rust toolchain
RUN curl https://sh.rustup.rs -sSf | bash -s -- -y
FROM prebuild AS build
ADD . /logprep
WORKDIR /logprep

# Use a python virtual environment
RUN python -m venv --upgrade-deps /opt/venv
ENV PATH="/opt/venv/bin:/root/.cargo/bin:${PATH}"


RUN if [ "$LOGPREP_VERSION" = "dev" ]; then pip install --disable-pip-version-check . ;\
    elif [ "$LOGPREP_VERSION" = "latest" ]; then pip install --disable-pip-version-check git+https://github.com/fkie-cad/Logprep.git@latest ; \
    else pip install --disable-pip-version-check "logprep==$LOGPREP_VERSION" ; fi; \
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
