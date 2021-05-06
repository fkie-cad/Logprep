FROM openjdk:11-jre

ENV DEBIAN_FRONTEND noninteractive
ENV KAFKA_VERSION kafka_2.12-2.5.1

RUN apt-get update && apt-get install -y zookeeper wget supervisor

RUN wget -q http://apache.mirror.iphh.net/kafka/2.5.1/"$KAFKA_VERSION".tgz -O /tmp/"$KAFKA_VERSION".tgz
RUN tar xfz /tmp/"$KAFKA_VERSION".tgz -C /opt/ && mv /opt/kafka* /opt/kafka
RUN rm /tmp/"$KAFKA_VERSION".tgz

RUN mkdir -p /var/zookeeper/data_dir
RUN mkdir -p /var/kafka/log_data

ENV KAFKA_CONFIG_FILE /opt/kafka/config/server.properties

#Update "log.dirs" in Kafka server.properties config
RUN sed -i "s@log.dirs=.*@log.dirs=/tmp/kafka-logs@g" $KAFKA_CONFIG_FILE

#Update "listeners" in Kafka server.properties config
RUN sed -i "s@#listeners=.*@listeners=PLAINTEXT://0.0.0.0:9092@g" $KAFKA_CONFIG_FILE

#Update "advertised.listeners" in Kafka server.properties config
RUN sed -i "s@.*dvertised.listeners=.*@advertised.listeners=PLAINTEXT://172.17.0.2:9092@g" $KAFKA_CONFIG_FILE

#Update "num.partitions" in Kafka server.properties config
RUN sed -i "s@.*um.partitions=.*@num.partitions=20@g" $KAFKA_CONFIG_FILE

ADD supervisor_conf/kafka.conf supervisor_conf/zookeeper.conf /etc/supervisor/conf.d/

EXPOSE 2181 9092

CMD ["supervisord", "-n"]
