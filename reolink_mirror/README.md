# Reolink NVR Mirror

Continuously mirrors **motion** recordings from a Reolink NVR to Home
Assistant's local media folder, so clips can be browsed and played from
**Media → My media** with minimal latency (no round-trip to the NVR on view).

The NVR already records every motion event to its own disk. This add-on polls
the NVR on an interval, finds new motion clips, and downloads them (sub stream,
H.264) to `/media` — it never re-records, so there's exactly one mp4 per event.

## How it works

- One long-lived connection to the NVR (session reused; ~1 re-login/hour).
- Every `poll_interval` seconds, one lightweight motion-search per channel.
- Downloads are deduplicated by filename — each clip is fetched exactly once.
- Clips still being written (ended very recently) are skipped for a cycle.
- Files land in `/media/<media_subdir>/<camera>/<timestamp>.mp4`, plus a
  matching `<timestamp>.jpg` thumbnail captured `thumbnail_offset` seconds
  after the motion trigger (same leading timestamp as its video).
- Each cycle also deletes local clips older than `mirror_hours` (retention).

## Installation (from this repository, via the HA UI)

This add-on is distributed as a Home Assistant add-on repository, so you can
install and update it entirely from the web UI — no SSH or host access needed.

1. **Settings → Add-ons → Add-on Store → ⋮ (top-right) → Repositories**.
2. Add this repository URL:
   `https://github.com/zer0complexity/home_assistant` → **Add** → **Close**.
3. The **Reolink NVR Mirror** card appears in the store → click it → **Install**
   (Supervisor builds the image on-device; the first build takes a few minutes).
4. Set the **Configuration** (see below), then **Start**. Watch the **Log** tab
   for the "Connected. Channels: …" line.

Updates: bump `version` in `config.yaml`; the store will offer an update.

## Configuration

| Option | Default | Description |
| --- | --- | --- |
| `nvr_host` | — | NVR IP address. |
| `nvr_port` | `80` | NVR HTTP port. |
| `nvr_username` | `admin` | NVR username. |
| `nvr_password` | — | NVR password (masked in the UI). |
| `poll_interval` | `30` | Seconds between polls (10–3600). |
| `search_window_minutes` | `30` | How far back each poll searches (5–1440). |
| `media_subdir` | `reolink_mirror` | Subfolder under `/media` for clips. |
| `mirror_hours` | `48` | Hours of clips to keep locally (1–720). Older clips are deleted each cycle. |
| `thumbnail_offset` | `8.0` | Seconds into the clip to capture the thumbnail (0–30). Falls back to 0s for shorter clips. |

## Viewing clips

Clips appear under **Media → My media → reolink_mirror → `<camera>`**. They play
directly from the HA disk. Because the media browser does not transcode, the
**sub stream (H.264)** is downloaded for reliable playback across browsers.

## Notes

- Distributed as an add-on repository (see Installation above). To release an
  update, bump `version` in `config.yaml` and push; users update from the store.
- Retention is automatic: clips older than `mirror_hours` are deleted every
  ~4 hours, so local disk usage stays bounded to that window.
