#!/bin/sh

DOCKER_BUILDKIT=1 \
docker build \
    -t musicbot \
    -t musicbot:deploy \
    .

USER=$1
HOST=$2

docker save musicbot:deploy | bzip2 | pv | ssh ${USER}@${HOST} docker load
