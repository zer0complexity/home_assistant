ARG BUILD_FROM=ghcr.io/home-assistant/base:3.21
FROM ${BUILD_FROM}

# Install Python, ffmpeg, and watchdog for file system monitoring
RUN apk add --no-cache python3 py3-pip ffmpeg \
    && pip3 install --no-cache-dir --break-system-packages \
       "watchdog==6.0.0"

COPY run.sh /
COPY app.py /
RUN chmod a+x /run.sh

CMD [ "/run.sh" ]
