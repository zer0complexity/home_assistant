# home_assistant

Home Assistant configuration and custom add-ons.

## Add-on repository

This repository is also a Home Assistant **add-on repository**. To install its
add-ons from the Home Assistant UI:

1. **Settings → Add-ons → Add-on Store → ⋮ → Repositories**.
2. Add: `https://github.com/zer0complexity/home_assistant` → **Add**.
3. Install the add-on from the store and start it.

### Add-ons

- **[Reolink NVR Mirror](reolink_mirror/)** — continuously mirrors Reolink NVR
  motion recordings (sub stream) to local media storage for fast, low-latency
  browsing and playback in Home Assistant.
- **[Reolink Video Library Manager](reolink_video_library_manager/)** — manages
  FTP-uploaded Reolink NVR and camera recordings, generates matching snapshot
  thumbnails at a configurable offset, and automatically purges expired recordings.
