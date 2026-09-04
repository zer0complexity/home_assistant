ARG BUILD_FROM=ghcr.io/home-assistant/base:3.21
FROM ${BUILD_FROM}

# Install Python, ffmpeg (for thumbnails), and the released reolink-aio library
# (pure Python; deps publish musllinux wheels).
RUN apk add --no-cache python3 py3-pip ffmpeg \
    && pip3 install --no-cache-dir --break-system-packages \
       "reolink-aio==0.21.15"

COPY run.sh /
COPY app.py /
RUN chmod a+x /run.sh

CMD [ "/run.sh" ]
