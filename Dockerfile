ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base
FROM $BUILD_FROM

# Install requirements for add-on
ENV PYTHONUNBUFFERED=1
RUN apk add --update --no-cache python3 py3-pip gcc python3-dev libc-dev \
    zlib-dev libjpeg-turbo-dev linux-headers && ln -sf python3 /usr/bin/python
RUN python3 -m pip install pillow iot-upnp

WORKDIR /app
COPY init.py .
COPY congaserver.py .
COPY congaModules ./congaModules
COPY html ./html

# Web server
EXPOSE 80
# Robot server
EXPOSE 20008

# Use unbuffered output for the logs
CMD ["python3","-u", "congaserver.py", "80", "20008","true"]