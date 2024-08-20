ARG PYTHON_VERSION=3.10

FROM python:${PYTHON_VERSION}-bullseye as build
ARG LOGPREP_VERSION=latest
ARG http_proxy
ARG https_proxy
ARG no_proxy

ADD . /logprep
WORKDIR /logprep
RUN python -m pip install --upgrade pip wheel setuptools>=72.2.0
RUN python -m venv /opt/venv
# Make sure we use the virtualenv:
ENV PATH="/opt/venv/bin:$PATH"

RUN if [ "$LOGPREP_VERSION" = "dev" ]; then pip install .;\
    elif [ "$LOGPREP_VERSION" = "latest" ]; then pip install git+https://github.com/fkie-cad/Logprep.git@latest; \
    else pip install "logprep==$LOGPREP_VERSION"; fi; \
    logprep --version


FROM python:${PYTHON_VERSION}-slim as prod
ARG http_proxy
ARG https_proxy
COPY --from=build /opt/venv /opt/venv
RUN useradd -s /bin/sh -m -c "logprep user" logprep
USER logprep
# Make sure we use the virtualenv:
ENV PATH="/opt/venv/bin:$PATH"
WORKDIR /home/logprep

ENTRYPOINT ["logprep"]
