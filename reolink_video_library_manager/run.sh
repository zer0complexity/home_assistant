#!/usr/bin/with-contenv bashio

set -e

bashio::log.info "Starting Reolink Video Library Manager..."

if [[ ! -f /opt/reolink_video_library_manager/video-library-manager-cards.js ]]; then
	bashio::log.error "Video Library Manager Cards source is missing from the add-on image"
	exit 1
fi

mkdir -p /config/www
cp /opt/reolink_video_library_manager/video-library-manager-cards.js /config/www/video-library-manager-cards.js
# Also maintain video-event-card.js copy for backward compatibility
cp /opt/reolink_video_library_manager/video-library-manager-cards.js /config/www/video-event-card.js

if [[ ! -s /config/www/video-library-manager-cards.js ]]; then
	bashio::log.error "Video Library Manager Cards was not installed in the Home Assistant configuration directory"
	exit 1
fi

bashio::log.info "Installed Video Library Manager Cards at /config/www/video-library-manager-cards.js"

exec python3 /app.py
