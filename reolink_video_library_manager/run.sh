#!/usr/bin/with-contenv bashio

bashio::log.info "Starting Reolink Video Library Manager..."

exec python3 /app.py
