#!/bin/sh

EVENT_NUM=100000

export PROMETHEUS_MULTIPROC_DIR="/tmp/logprep"

rm -rf $PROMETHEUS_MULTIPROC_DIR
mkdir -p $PROMETHEUS_MULTIPROC_DIR

WORKING_DIR=$(pwd)
cd examples/compose

docker compose down
docker compose up -d kafka opensearch dashboards grafana

printf "Waiting 30 seconds for kafka to be healthy\n"
sleep 30

cd $WORKING_DIR

logprep run examples/exampledata/config/http_pipeline.yml &
HTTP_CONN=$(pgrep logprep | head -1) 

printf "Logprep http input pid: %s\n" $HTTP_CONN

sleep 10
logprep generate http --input-dir ./examples/exampledata/input_logdata/ --target-url http://localhost:9000 --events $EVENT_NUM --batch-size $(($EVENT_NUM / 10)) && sleep 10 && kill $HTTP_CONN && killall logprep

cd examples/compose

docker compose up -d prometheus
sleep 10

cd $WORKING_DIR
logprep run examples/exampledata/config/pipeline.yml
