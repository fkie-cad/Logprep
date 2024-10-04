ARG PYTHON_VERSION=3.11

FROM bitnami/python:${PYTHON_VERSION} as build
ARG LOGPREP_VERSION=latest
ARG http_proxy
ARG https_proxy
ARG no_proxy

ADD . /logprep
WORKDIR /logprep
RUN curl https://sh.rustup.rs -sSf | bash -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"
RUN python -m venv /opt/venv
# Make sure we use the virtualenv:
ENV PATH="/opt/venv/bin:$PATH"
RUN python -m pip install --upgrade pip 'setuptools>=72.2.0'

RUN if [ "$LOGPREP_VERSION" = "dev" ]; then pip install .;\
    elif [ "$LOGPREP_VERSION" = "latest" ]; then pip install git+https://github.com/fkie-cad/Logprep.git@latest; \
    else pip install "logprep==$LOGPREP_VERSION"; fi; \
    logprep --version


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
