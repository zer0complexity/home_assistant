# Reolink Video Library Manager

A Home Assistant add-on that manages Reolink NVR and camera recordings uploaded via FTP to Home Assistant.

## Features

- **Automated Snapshot Generation**: Automatically monitors the FTP upload folder (recursively across any directory depth) and generates a matching `.jpg` thumbnail snapshot for every video at a configurable time offset (default: 5 seconds in). If the video is shorter than the configured offset, it automatically falls back to 0s.
- **Identical Naming**: Companion snapshot images share the exact base name and directory path as the source video file (`sub/dir/recording.mp4` $\rightarrow$ `sub/dir/recording.jpg`).
- **Configurable Retention Policy**: Automatically purges recordings and snapshot files older than a configurable number of days (default: 7 days) on a scheduled interval (default: every 24 hours).
- **Directory Tree Pruning**: Cleans up empty subdirectories automatically once all expired files inside them have been purged.
- **Upload Stabilization**: Detects in-progress FTP file writes and waits for transfers to finish before invoking thumbnail extraction.

## Configuration

Example configuration:

```yaml
watch_directory: "/media/reolink_mirror"
snapshot_offset: 5
retention_days: 7
purge_interval_hours: 24
```

### Configuration Options

| Option | Type | Default | Description |
|---|---|---|---|
| `watch_directory` | string | `"/media/reolink_mirror"` | Root directory where the Reolink NVR uploads video files via FTP. |
| `snapshot_offset` | integer | `5` | Time offset (in seconds) to capture the snapshot frame. |
| `retention_days` | integer | `7` | Number of days to retain video recordings before deletion. |
| `purge_interval_hours` | integer | `24` | Interval (in hours) at which the retention purge runs. |

## Dashboard Cards

The add-on installs custom Lovelace cards automatically at
`/config/www/video-library-manager-cards.js` whenever it starts.

### Dashboard Resource Registration

Register the cards bundle once as a Lovelace resource:

1. Go to **Settings > Dashboards > Resources**.
2. Select **Add Resource**.
3. Enter `/local/video-library-manager-cards.js?v=0.4.4` as the URL and select
   **JavaScript Module** as the resource type.
4. Select **Create**. Refresh the dashboard if the custom cards are not listed.

When updating the add-on with a new card version, update the `v=` value in the
resource URL to make the browser load the new JavaScript file.

---

### Camera Events Card (`custom:camera-events-card`)

Displays a 1-column grid of `video-event-cards` for all recordings matching a specific camera ID in a media directory.

#### Configuration Options

| Option | Type | Required | Description |
|---|---|---|---|
| `camera_id` | integer | Yes | 0-based camera ID (e.g. `0`, `1`). Automatically formatted as 2 digits (`00`, `01`) when matching filenames. |
| `media_dir` | string | Yes | The media directory name under `/media` (e.g., `"reolink_mirror"`). |
| `camera_name` | string | No | Optional camera display name (e.g. `"Driveway"`). If provided, sets card header title to `"[camera_name] Events"` instead of `"Camera [id] Events"`. |

#### Example Usage

```yaml
type: custom:camera-events-card
camera_id: 0
camera_name: Front Door
media_dir: reolink_mirror
```

File names in `media_dir` follow the format `NVR_dd_YYYYMMDDHHmmSS` (e.g., `NVR_00_20260904120000.jpg` and `NVR_00_20260904120000.mp4`).

---

### Video Event Card (`custom:video-event-card`)

Displays an individual event thumbnail image with a title showing the video timestamp in long date and time format (set by browser locale), and opens the associated video in a modal player dialog when selected.

#### Example Usage

```yaml
type: custom:video-event-card
image: media-source://media_source/local/reolink_mirror/NVR_00_20260904120000.jpg
video: media-source://media_source/local/reolink_mirror/NVR_00_20260904120000.mp4
```

Both values must be media-source identifiers, not direct filesystem paths or `/media/local/...` URLs.

## Reolink NVR / Camera Setup

1. Configure an FTP server in Home Assistant (such as the Home Assistant FTP add-on) pointing to `/media/reolink_mirror` (or your chosen path).
2. On your Reolink NVR or camera:
   - Navigate to **Network > Advanced > FTP Settings**.
   - Set the FTP Server IP to your Home Assistant IP.
   - Set the Directory to your watched directory.
   - Configure Schedule / Triggers (e.g., Motion, Person, Vehicle).
3. Start the **Reolink Video Library Manager** add-on. Videos uploaded to the watch directory will be automatically processed and thumbnails generated.
