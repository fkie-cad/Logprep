FROM python:3.9-slim as build

ADD . /logprep
WORKDIR /logprep
RUN python -m pip install --upgrade pip && python -m pip install wheel
RUN python setup.py sdist bdist_wheel


FROM python:3.9-slim as prod
RUN useradd -s /bin/sh -m -c "logprep user" logprep
USER logprep
ENV PATH=/home/logprep/.local/bin:$PATH
COPY --from=build /logprep/dist/logprep-0+unknown-py3-none-any.whl /
RUN pip install logprep-0+unknown-py3-none-any.whl
ENV PROMETHEUS_MULTIPROC_DIR=/tmp/logprep/prometheus_multiproc/
ENV TLDEXTRACT_CACHE=/tmp/logprep/tld_extract_cache/
WORKDIR /home/logprep

ENTRYPOINT ["logprep"]
