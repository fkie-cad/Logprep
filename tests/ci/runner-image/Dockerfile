FROM ubuntu:bionic

ARG PROXY
ENV HTTP_PROXY "$PROXY"
ENV HTTPS_PROXY "$PROXY"

RUN apt-get update && apt-get install python3-pip wget openjdk-11-jdk -y

RUN pip3 install --upgrade pip
RUN pip3 install tox
RUN pip3 install ansible
RUN pip3 install deepdiff

RUN DEBIAN_FRONTEND=noninteractive apt-get install -y locales
RUN sed -i -e 's/# en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/' /etc/locale.gen && \
    dpkg-reconfigure --frontend=noninteractive locales && \
    update-locale LANG=en_US.UTF-8
ENV LANG en_US.UTF-8

ENV KAFKA_VERSION kafka_2.12-2.5.1
RUN wget -q http://apache.mirror.iphh.net/kafka/2.5.1/"$KAFKA_VERSION".tgz -O /tmp/"$KAFKA_VERSION".tgz
RUN tar xfz /tmp/"$KAFKA_VERSION".tgz -C /opt && mv /opt/kafka* /opt/kafka
RUN rm /tmp/"$KAFKA_VERSION".tgz

RUN mkdir -p /dev/log

# Required to fix wheel hash error when building pex
RUN apt-get install unzip -y
RUN pip3 install wheel && pip3 install wheel --upgrade
