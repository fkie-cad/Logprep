ARG PYTHON_VERSION=3.11

FROM bitnami/python:${PYTHON_VERSION} as build
ARG LOGPREP_VERSION=latest
ARG http_proxy
ARG https_proxy
ARG no_proxy

ADD . /logprep
WORKDIR /logprep

# Install the Rust toolchain
RUN curl https://sh.rustup.rs -sSf | bash -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

# Use a python virtual environment
RUN python -m venv --upgrade-deps /opt/venv
ENV PATH="/opt/venv/bin:$PATH"


RUN if [ "$LOGPREP_VERSION" = "dev" ]; then pip install .;\
    elif [ "$LOGPREP_VERSION" = "latest" ]; then pip install git+https://github.com/fkie-cad/Logprep.git@latest; \
    else pip install "logprep==$LOGPREP_VERSION"; fi; \
    /opt/venv/bin/logprep --version

# geoip2 4.8.0 lists a vulnerable setuptools version as a dependency. setuptools is unneeded at runtime, so it is uninstalled.
# More recent (currently unreleased) versions of geoip2 removed setuptools from dependencies.
RUN pip uninstall -y setuptools


FROM bitnami/python:${PYTHON_VERSION} as prod
ARG http_proxy
ARG https_proxy
COPY --from=build /opt/venv /opt/venv
RUN useradd -s /bin/sh -m -c "logprep user" logprep
USER logprep
# Make sure we use the virtualenv:
ENV PATH="/opt/venv/bin:$PATH"
WORKDIR /home/logprep

ENTRYPOINT ["logprep"]
