ARG PYTHON_VERSION=3.9

FROM python:${PYTHON_VERSION}-slim as build
ARG LOGPREP_VERSION=latest
ARG http_proxy
ARG https_proxy
ARG no_proxy

ADD . /logprep
WORKDIR /logprep
RUN apt-get update && apt-get -y install git
RUN python -m venv /opt/venv
# Make sure we use the virtualenv:
ENV PATH="/opt/venv/bin:$PATH"
RUN python -m pip install --upgrade pip wheel

RUN if [ "$LOGPREP_VERSION" = "dev" ]; then python setup.py sdist bdist_wheel && pip install ./dist/logprep-*.whl;\
    elif [ "$LOGPREP_VERSION" = "latest" ]; then pip install git+https://github.com/fkie-cad/Logprep.git@latest; \
    else pip install "logprep==$LOGPREP_VERSION"; fi

FROM python:${PYTHON_VERSION}-slim as prod
ARG http_proxy
ARG https_proxy
RUN apt-get update && apt-get -y install --no-install-recommends libhyperscan5 librdkafka1
RUN useradd -s /bin/sh -m -c "logprep user" logprep
COPY --from=build /opt/venv /opt/venv
USER logprep
# Make sure we use the virtualenv:
ENV PATH="/opt/venv/bin:$PATH"
ENV PROMETHEUS_MULTIPROC_DIR=/tmp/logprep/prometheus_multiproc/
ENV TLDEXTRACT_CACHE=/tmp/logprep/tld_extract_cache/
WORKDIR /home/logprep

ENTRYPOINT ["logprep"]
