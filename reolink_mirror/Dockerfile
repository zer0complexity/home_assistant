ARG BUILD_FROM=ghcr.io/home-assistant/base:3.21
FROM ${BUILD_FROM}

# Install Python, ffmpeg (for thumbnails), and reolink-aio.
# We install the Baichuan VOD-download PR branch (PR #186) because the released
# HTTP `cmd=Download` path is broken on recent Reolink NVR firmware (the NVR
# drops the download connection). The tarball install avoids needing git.
RUN apk add --no-cache python3 py3-pip ffmpeg \
    && pip3 install --no-cache-dir --break-system-packages \
       "https://github.com/1eft0ver/reolink_aio/archive/refs/heads/baichuan-vod-download.tar.gz"

COPY run.sh /
COPY app.py /
RUN chmod a+x /run.sh

CMD [ "/run.sh" ]
