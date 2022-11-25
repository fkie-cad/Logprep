FROM python:3.11-slim as build

ADD . /logprep
WORKDIR /logprep
RUN apt-get update && apt-get -y install libhyperscan-dev librdkafka-dev
RUN python -m pip install --upgrade pip wheel
RUN python setup.py sdist bdist_wheel


FROM python:3.11-slim as prod
RUN useradd -s /bin/sh -m -c "logprep user" logprep
USER logprep
ENV PATH=/home/logprep/.local/bin:$PATH
COPY --from=build /logprep/dist/logprep-0+unknown-py3-none-any.whl /
RUN apt-get update && apt-get -y install libhyperscan-dev librdkafka-dev
RUN pip install logprep-0+unknown-py3-none-any.whl
ENV PROMETHEUS_MULTIPROC_DIR=/tmp/logprep/prometheus_multiproc/
ENV TLDEXTRACT_CACHE=/tmp/logprep/tld_extract_cache/
WORKDIR /home/logprep

ENTRYPOINT ["logprep"]
