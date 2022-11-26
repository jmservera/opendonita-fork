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
# upnp 1.0.3 does not correctly work with python3.10
COPY patch/HTTP.py /usr/lib/python3.10/site-packages/upnp/HTTP.py

# Web server
EXPOSE 80
# Robot server
EXPOSE 20008
# upnp
EXPOSE 1900/udp
EXPOSE 5000


# Use unbuffered output for the logs
CMD ["python3", "congaserver.py", "80", "20008", "true", "true"]