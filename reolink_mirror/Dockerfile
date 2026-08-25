ARG BUILD_FROM=ghcr.io/home-assistant/base:3.21
FROM ${BUILD_FROM}

# Install Python and the reolink-aio library (pure Python; deps publish musllinux wheels).
RUN apk add --no-cache python3 py3-pip \
    && pip3 install --no-cache-dir --break-system-packages reolink-aio

COPY run.sh /
COPY app.py /
RUN chmod a+x /run.sh

CMD [ "/run.sh" ]
