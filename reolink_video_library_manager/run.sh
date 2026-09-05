#!/usr/bin/with-contenv bashio

set -e

bashio::log.info "Starting Reolink Video Library Manager..."

if [[ ! -f /opt/reolink_video_library_manager/video-event-card.js ]]; then
	bashio::log.error "Video Event Card source is missing from the add-on image"
	exit 1
fi

mkdir -p /config/www
cp /opt/reolink_video_library_manager/video-event-card.js /config/www/video-event-card.js

if [[ ! -s /config/www/video-event-card.js ]]; then
	bashio::log.error "Video Event Card was not installed in the Home Assistant configuration directory"
	exit 1
fi

bashio::log.info "Installed Video Event Card at /config/www/video-event-card.js"

exec python3 /app.py
