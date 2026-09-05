#!/usr/bin/with-contenv bashio

bashio::log.info "Starting Reolink Video Library Manager..."

mkdir -p /config/www
cp /opt/reolink_video_library_manager/video-event-card.js /config/www/video-event-card.js
bashio::log.info "Installed Video Event Card at /config/www/video-event-card.js"

exec python3 /app.py
