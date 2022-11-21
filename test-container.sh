#!/bin/bash
# alpine:3.16
docker build -t opendonita:test .
#docker run -it --rm -p 8099:8099 -p 1900:1900 -p 20008:20008 -p 5000:5000 opendonita:test
id=$(docker run -d --network host opendonita:test)
docker logs $id -f
docker kill $id