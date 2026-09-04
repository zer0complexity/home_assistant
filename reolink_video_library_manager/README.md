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

## Reolink NVR / Camera Setup

1. Configure an FTP server in Home Assistant (such as the Home Assistant FTP add-on) pointing to `/media/reolink_mirror` (or your chosen path).
2. On your Reolink NVR or camera:
   - Navigate to **Network > Advanced > FTP Settings**.
   - Set the FTP Server IP to your Home Assistant IP.
   - Set the Directory to your watched directory.
   - Configure Schedule / Triggers (e.g., Motion, Person, Vehicle).
3. Start the **Reolink Video Library Manager** add-on. Videos uploaded to the watch directory will be automatically processed and thumbnails generated.
