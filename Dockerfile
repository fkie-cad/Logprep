FROM python:3.11-slim as build

ADD . /logprep
WORKDIR /logprep
RUN apt-get update && apt-get -y install build-essential pkg-config libhyperscan-dev librdkafka-dev
RUN python -m venv /opt/venv
# Make sure we use the virtualenv:
ENV PATH="/opt/venv/bin:$PATH"
RUN python -m pip install --upgrade pip wheel
RUN python setup.py sdist bdist_wheel
RUN pip install /logprep/dist/logprep-0+unknown-py3-none-any.whl


FROM python:3.11-slim as prod
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
