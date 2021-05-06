FROM ubuntu:bionic

ARG PROXY
ENV HTTP_PROXY "$PROXY"
ENV HTTPS_PROXY "$PROXY"

RUN apt-get update
RUN apt-get install python3-pip -y

RUN pip3 install --upgrade pip

RUN DEBIAN_FRONTEND=noninteractive apt-get install -y locales
RUN sed -i -e 's/# en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/' /etc/locale.gen && \
    dpkg-reconfigure --frontend=noninteractive locales && \
    update-locale LANG=en_US.UTF-8
ENV LANG en_US.UTF-8

RUN mkdir -p /dev/log

RUN echo "1234"

COPY . /usr/share/logprep
WORKDIR /usr/share/logprep
RUN python3 -m pip install -r requirements.txt

CMD PYTHONPATH='.' python3 logprep/run_logprep.py quickstart/exampledata/config/pipeline.yml
