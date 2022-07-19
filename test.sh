#!/bin/bash
# alpine:3.16
docker build --build-arg BUILD_FROM=ghcr.io/home-assistant/amd64-base -t opendonita:0.1 .
docker run -it --rm -p 8000:80 opendonita:0.1