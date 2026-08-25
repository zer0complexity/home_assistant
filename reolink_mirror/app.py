#!/usr/bin/env python3
"""Reolink NVR Mirror.

Continuously mirrors Reolink NVR motion recordings (sub stream) to local media
storage so they can be browsed and played from Home Assistant with minimal
latency (no NVR round-trip on view).

Design notes (derived from the reolink-aio library and the HA core Reolink
integration):
  * A single long-lived ``Host`` is used for the lifetime of the process so the
    NVR session/token is reused (~1 re-login/hour) instead of leaking sessions.
  * Each poll issues one lightweight Baichuan ``findAlarmVideo`` search per
    channel (trigger=MOTION), NOT a heavyweight re-scan of all recordings.
  * Downloads are deduplicated by filename so the expensive NVR-side
    ``NvrDownload`` packaging runs exactly once per clip.
  * Files whose end time is very recent are skipped for a cycle so we don't try
    to download a clip the NVR is still writing.
"""

import asyncio
import json
import logging
import re
import sys
from contextlib import aclosing
from datetime import datetime, timedelta
from pathlib import Path

from reolink_aio.api import Host
from reolink_aio.exceptions import ReolinkError
from reolink_aio.typings import VOD_trigger

OPTIONS_PATH = Path("/data/options.json")
STATE_PATH = Path("/data/state.json")

# How often to enforce the local retention window (purge old clips).
PURGE_INTERVAL = timedelta(hours=4)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
)
_LOGGER = logging.getLogger("reolink_mirror")


def load_options() -> dict:
    return json.loads(OPTIONS_PATH.read_text())


def load_state() -> dict:
    try:
        return json.loads(STATE_PATH.read_text())
    except Exception:
        return {"downloaded": []}


def save_state(state: dict) -> None:
    # Keep only a bounded history of downloaded filenames.
    state["downloaded"] = state.get("downloaded", [])[-2000:]
    try:
        STATE_PATH.write_text(json.dumps(state))
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("Could not persist state: %s", err)


def safe_name(name: str) -> str:
    """Make a camera name safe for use as a directory name."""
    keep = []
    for ch in name.strip().lower():
        keep.append(ch if (ch.isalnum() or ch in (" ", "-", "_")) else " ")
    cleaned = "".join(keep).strip().replace(" ", "_")
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned or "camera"


async def grab_thumbnail(src: Path, sec: float, timeout: float = 30.0) -> bool:
    """Extract a single frame ~``sec`` seconds into ``src`` as a JPEG.

    The thumbnail is written next to ``src`` with the SAME base name (only the
    extension changes), so its leading timestamp matches the video exactly.
    Returns True on success. ffmpeg is invoked via asyncio so the poll loop is
    never blocked.
    """
    dst = src.with_suffix(".jpg")
    try:
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-ss", str(sec), "-i", str(src),
            "-frames:v", "1", "-q:v", "2", "-an", "-y", str(dst),
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
    except FileNotFoundError:
        _LOGGER.warning("ffmpeg not found; cannot create thumbnail for %s", src)
        return False
    try:
        rc = await asyncio.wait_for(proc.wait(), timeout)
    except (TimeoutError, asyncio.TimeoutError):
        proc.kill()
        await proc.wait()
        _LOGGER.warning("Thumbnail extraction timed out for %s", src)
        return False
    ok = rc == 0 and dst.exists() and dst.stat().st_size > 0
    if ok:
        _LOGGER.info("Thumbnail %s (at %.1fs)", dst, sec)
    return ok


async def make_thumbnail(src: Path, sec: float) -> None:
    """Thumbnail ``sec`` seconds in, falling back to the start of the clip."""
    if not await grab_thumbnail(src, sec=sec):
        await grab_thumbnail(src, sec=0.0)


async def download_clip(host: Host, channel: int, vod, dest: Path, thumb_offset: float) -> bool:
    """Download a single VOD clip to ``dest`` over the Baichuan TCP channel.

    Uses reolink-aio PR #186 (``host.baichuan.download_vod``) because the HTTP
    ``cmd=Download`` path is broken on recent Reolink NVR firmware (the NVR
    drops the download connection -> "Server disconnected"). The Baichuan path
    uses the same TCP connection (port 9000) that the motion search already
    uses. Returns True on success; the partial file is removed on failure.
    """
    tmp = dest.with_suffix(dest.suffix + ".part")
    try:
        # Fetch the expected size up front so we can verify a complete transfer.
        info = await host.baichuan.get_vod_file_info(channel, vod.file_name, stream="sub")
        dest.parent.mkdir(parents=True, exist_ok=True)
        written = 0
        gen = host.baichuan.download_vod(channel, vod.file_name, info=info, timeout=60)
        async with aclosing(gen) as chunks:
            with open(tmp, "wb") as fh:
                async for chunk in chunks:
                    fh.write(chunk)
                    written += len(chunk)
        # Baichuan yields exactly info.size bytes; treat anything else as failed.
        if written != info.size:
            raise ReolinkError(f"incomplete download: {written} of {info.size} bytes")
        tmp.replace(dest)
        _LOGGER.info("Downloaded %s -> %s (%d bytes)", vod.file_name, dest, written)
        return True
    except ReolinkError as err:
        _LOGGER.warning("Failed to download %s: %s", vod.file_name, err)
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("Unexpected error downloading %s: %s", vod.file_name, err)
    # Clean up partial file on failure.
    try:
        if tmp.exists():
            tmp.unlink()
    except Exception:  # noqa: BLE001
        pass
    return False


def _purge_old_sync(opts: dict) -> int:
    """Blocking retention pass; run in an executor so it never stalls the loop.

    Files are named ``<yyyymmddhhmmss>_<camera>.mp4``; the embedded timestamp is
    authoritative, so retention is robust across restarts and file copies.
    """
    hours = int(opts.get("mirror_hours", 48))
    cutoff = datetime.now() - timedelta(hours=hours)
    media_root = Path("/media") / opts.get("media_subdir", "reolink_mirror")
    if not media_root.exists():
        return 0
    removed = 0
    for path in media_root.glob("*/*"):
        if path.suffix.lower() not in (".mp4", ".jpg"):
            continue
        match = re.match(r"(\d{14})_", path.name)
        if not match:
            continue
        try:
            ts = datetime.strptime(match.group(1), "%Y%m%d%H%M%S")
        except ValueError:
            continue
        if ts < cutoff:
            try:
                path.unlink()
                removed += 1
            except OSError as err:
                _LOGGER.warning("Could not delete %s: %s", path, err)
    return removed


async def purge_old(opts: dict, state: dict) -> None:
    """Enforce the retention window, throttled to roughly every 4 hours."""
    now_ts = datetime.now().timestamp()
    next_purge = float(state.get("next_purge_ts", 0.0))
    if now_ts < next_purge:
        return
    removed = await asyncio.get_running_loop().run_in_executor(
        None, _purge_old_sync, opts
    )
    if removed:
        _LOGGER.info(
            "Purged %d clip(s) older than %dh", removed, int(opts.get("mirror_hours", 48))
        )
    state["next_purge_ts"] = datetime.now().timestamp() + PURGE_INTERVAL.total_seconds()
    save_state(state)


async def sync_once(host: Host, opts: dict, state: dict) -> None:
    """One poll cycle across all channels."""
    now = datetime.now().astimezone()
    window = timedelta(minutes=int(opts.get("search_window_minutes", 30)))
    start = now - window
    poll_interval = int(opts.get("poll_interval", 30))
    thumb_offset = float(opts.get("thumbnail_offset", 2.0))
    media_root = Path("/media") / opts.get("media_subdir", "reolink_mirror")

    downloaded = set(state.get("downloaded", []))
    new_downloads = []

    for channel in sorted(host.channels):
        try:
            camera_name = host.camera_name(channel) or f"channel_{channel}"
        except Exception:  # noqa: BLE001
            camera_name = f"channel_{channel}"
        cam_dir = media_root / safe_name(camera_name)

        try:
            _, vod_files = await host.request_vod_files(
                channel,
                start,
                now,
                status_only=False,
                stream="sub",
                trigger=VOD_trigger.MOTION,
            )
        except ReolinkError as err:
            _LOGGER.warning("Search failed for channel %s: %s", channel, err)
            continue
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Unexpected search error channel %s: %s", channel, err)
            continue

        for vod in vod_files:
            fname = vod.file_name
            if fname in downloaded or fname in new_downloads:
                continue
            # Skip clips that ended very recently (may still be written).
            end_time = getattr(vod, "end_time", None)
            if isinstance(end_time, datetime):
                et = end_time
                if et.tzinfo is None:
                    et = et.astimezone()
                if (now - et) < timedelta(seconds=max(poll_interval, 30)):
                    continue

            ts = getattr(vod, "start_time_id", None) or now.strftime("%Y%m%d%H%M%S")
            dest = cam_dir / f"{ts}_{safe_name(camera_name)}.mp4"
            if dest.exists():
                new_downloads.append(fname)
                continue
            if await download_clip(host, channel, vod, dest, thumb_offset):
                new_downloads.append(fname)
                # Capture a thumbnail ~``thumb_offset``s after the trigger.
                await make_thumbnail(dest, thumb_offset)

    if new_downloads:
        downloaded.update(new_downloads)
        state["downloaded"] = sorted(downloaded)
        save_state(state)

    # Enforce the retention window (throttled internally to ~every 4 hours).
    await purge_old(opts, state)


async def main() -> None:
    opts = load_options()
    state = load_state()

    # Use the default HTTP session/connector. The single-connection workaround
    # for the firmware bug was tried (v0.3.x) and did not help; the Baichuan
    # download path (PR #186) is the actual fix and uses its own TCP socket.
    host = Host(
        opts["nvr_host"],
        opts["nvr_username"],
        opts["nvr_password"],
        port=int(opts.get("nvr_port", 80)),
        stream="sub",
    )

    poll_interval = int(opts.get("poll_interval", 30))
    _LOGGER.info(
        "Connecting to NVR %s:%s (poll=%ss, window=%s min)",
        opts["nvr_host"],
        opts.get("nvr_port", 80),
        poll_interval,
        opts.get("search_window_minutes", 30),
    )

    try:
        await host.get_host_data()
        _LOGGER.info("Connected. Channels: %s", list(host.channels))
    except Exception as err:  # noqa: BLE001
        _LOGGER.error("Initial connection to NVR failed: %s", err)
        # Continue; the retry loop below will keep trying.
    finally:
        # Never hold more than one Host; we reuse this one for the process life.
        pass

    try:
        while True:
            try:
                await sync_once(host, opts, state)
            except Exception as err:  # noqa: BLE001
                _LOGGER.error("Sync cycle failed: %s", err)
            await asyncio.sleep(poll_interval)
    finally:
        try:
            await host.logout()
        except Exception:  # noqa: BLE001
            pass


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
