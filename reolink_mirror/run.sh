#!/usr/bin/with-contenv bashio

bashio::log.info "Starting Reolink NVR Mirror..."

exec python3 /app.py
