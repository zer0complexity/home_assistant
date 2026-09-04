#!/usr/bin/env python3
"""Reolink Video Library Manager.

Monitors an FTP upload directory for Reolink video recordings, generates
companion snapshot thumbnails at a configurable timestamp offset, and purges
recordings older than a configurable retention period.
"""

import asyncio
import json
import logging
import os
import signal
import sys
import time
from pathlib import Path
from typing import Set

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

OPTIONS_PATH = Path("/data/options.json")

# Recognized video file extensions
VIDEO_EXTENSIONS: Set[str] = {
    ".mp4",
    ".mkv",
    ".avi",
    ".mov",
    ".flv",
    ".ts",
    ".wmv",
    ".webm",
    ".m4v",
    ".264",
    ".h264",
    ".265",
    ".h265",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
)
_LOGGER = logging.getLogger("reolink_video_library_manager")


def load_options() -> dict:
    """Load configuration options from Home Assistant options file."""
    defaults = {
        "watch_directory": "/media/reolink",
        "snapshot_offset": 5,
        "retention_days": 7,
        "purge_interval_hours": 24,
    }
    if OPTIONS_PATH.exists():
        try:
            data = json.loads(OPTIONS_PATH.read_text())
            defaults.update(data)
        except Exception as err:
            _LOGGER.warning("Could not read %s, using defaults: %s", OPTIONS_PATH, err)
    return defaults


def is_video_file(path: Path) -> bool:
    """Check if a path corresponds to a supported video format."""
    return path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS


async def grab_thumbnail(src: Path, sec: int, timeout: float = 30.0) -> bool:
    """Extract a single frame ~``sec`` seconds into ``src`` as a JPEG.

    The snapshot is written in the same directory with the exact same base name
    and a .jpg extension. If extraction at ``sec`` fails (e.g. clip is shorter),
    retries at offset 0.
    """
    dst = src.with_suffix(".jpg")
    if dst.exists() and dst.stat().st_size > 0:
        return True

    async def _run_ffmpeg(offset_sec: int) -> bool:
        try:
            proc = await asyncio.create_subprocess_exec(
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-ss",
                str(offset_sec),
                "-i",
                str(src),
                "-frames:v",
                "1",
                "-q:v",
                "2",
                "-an",
                "-y",
                str(dst),
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            rc = await asyncio.wait_for(proc.wait(), timeout)
            return rc == 0 and dst.exists() and dst.stat().st_size > 0
        except (TimeoutError, asyncio.TimeoutError):
            try:
                proc.kill()
                await proc.wait()
            except Exception:
                pass
            _LOGGER.warning("FFmpeg extraction timed out for %s at %ds", src, offset_sec)
            return False
        except FileNotFoundError:
            _LOGGER.error("ffmpeg executable not found in PATH")
            return False
        except Exception as err:
            _LOGGER.error("Error executing ffmpeg on %s: %s", src, err)
            return False

    # Attempt at configured offset
    success = await _run_ffmpeg(sec)
    if not success and sec > 0:
        _LOGGER.debug("Snapshot extraction at %ds failed for %s, retrying at 0s", sec, src)
        success = await _run_ffmpeg(0)

    if success:
        _LOGGER.info("Generated snapshot: %s", dst)
    else:
        _LOGGER.warning("Failed to generate snapshot for %s", src)

    return success


async def wait_for_file_stability(path: Path, check_interval: float = 2.0, max_checks: int = 30) -> bool:
    """Wait until an uploading file has finished writing and stabilized in size."""
    if not path.exists():
        return False

    try:
        last_size = path.stat().st_size
    except OSError:
        return False

    checks = 0
    while checks < max_checks:
        await asyncio.sleep(check_interval)
        if not path.exists():
            return False
        try:
            current_size = path.stat().st_size
        except OSError:
            return False

        if current_size > 0 and current_size == last_size:
            return True

        last_size = current_size
        checks += 1

    _LOGGER.warning("File %s did not stabilize after %d checks", path, max_checks)
    return False


def purge_old_records(watch_dir: Path, retention_days: int) -> None:
    """Purge files older than retention_days and delete any empty subdirectories."""
    if not watch_dir.exists():
        return

    now = time.time()
    cutoff = now - (retention_days * 86400)
    deleted_files = 0
    deleted_dirs = 0

    _LOGGER.info("Starting purge scan on %s (retention: %d days)...", watch_dir, retention_days)

    # 1. Delete files older than cutoff
    for root, _, files in os.walk(watch_dir):
        root_path = Path(root)
        for fname in files:
            file_path = root_path / fname
            try:
                stat = file_path.stat()
                if stat.st_mtime < cutoff:
                    file_path.unlink()
                    deleted_files += 1
                    _LOGGER.debug("Purged old file: %s", file_path)
            except Exception as err:
                _LOGGER.warning("Could not check/delete %s: %s", file_path, err)

    # 2. Clean up empty subdirectories (bottom-up)
    for root, dirs, files in os.walk(watch_dir, topdown=False):
        dir_path = Path(root)
        if dir_path == watch_dir:
            continue
        try:
            if not any(dir_path.iterdir()):
                dir_path.rmdir()
                deleted_dirs += 1
                _LOGGER.debug("Removed empty directory: %s", dir_path)
        except Exception as err:
            _LOGGER.warning("Could not remove directory %s: %s", dir_path, err)

    _LOGGER.info("Purge completed: %d files deleted, %d empty directories removed", deleted_files, deleted_dirs)


class VideoQueueHandler(FileSystemEventHandler):
    """Watchdog event handler that schedules stable video processing."""

    def __init__(self, loop: asyncio.AbstractEventLoop, queue: asyncio.Queue):
        super().__init__()
        self.loop = loop
        self.queue = queue

    def on_created(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            p = Path(event.src_path)
            if p.suffix.lower() in VIDEO_EXTENSIONS:
                self.loop.call_soon_threadsafe(self.queue.put_nowait, p)

    def on_moved(self, event: FileSystemEvent) -> None:
        if not event.is_directory and hasattr(event, "dest_path"):
            p = Path(event.dest_path)
            if p.suffix.lower() in VIDEO_EXTENSIONS:
                self.loop.call_soon_threadsafe(self.queue.put_nowait, p)


async def scan_and_queue_missing_snapshots(watch_dir: Path, queue: asyncio.Queue) -> None:
    """Scan existing files in watch_dir and queue any videos missing snapshots."""
    if not watch_dir.exists():
        return

    _LOGGER.info("Scanning %s for videos missing snapshots...", watch_dir)
    count = 0
    loop = asyncio.get_running_loop()

    def _sync_scan():
        videos_to_queue = []
        for root, _, files in os.walk(watch_dir):
            root_path = Path(root)
            for fname in files:
                fpath = root_path / fname
                if fpath.suffix.lower() in VIDEO_EXTENSIONS:
                    snapshot = fpath.with_suffix(".jpg")
                    if not snapshot.exists() or snapshot.stat().st_size == 0:
                        videos_to_queue.append(fpath)
        return videos_to_queue

    missing = await loop.run_in_executor(None, _sync_scan)
    for video in missing:
        await queue.put(video)
        count += 1

    if count > 0:
        _LOGGER.info("Found and queued %d videos missing snapshots", count)
    else:
        _LOGGER.info("All existing videos already have snapshots")


async def video_worker(queue: asyncio.Queue, snapshot_offset: int) -> None:
    """Worker task processing video files for snapshot extraction."""
    while True:
        video_path: Path = await queue.get()
        try:
            if not video_path.exists():
                continue

            snapshot_path = video_path.with_suffix(".jpg")
            if snapshot_path.exists() and snapshot_path.stat().st_size > 0:
                continue

            # Wait for upload to complete
            stable = await wait_for_file_stability(video_path)
            if stable:
                await grab_thumbnail(video_path, snapshot_offset)
        except asyncio.CancelledError:
            break
        except Exception as err:
            _LOGGER.exception("Unexpected error processing video %s: %s", video_path, err)
        finally:
            queue.task_done()


async def purge_scheduler(watch_dir: Path, retention_days: int, interval_hours: int) -> None:
    """Periodically execute the purge task."""
    loop = asyncio.get_running_loop()
    interval_seconds = interval_hours * 3600

    while True:
        try:
            await loop.run_in_executor(None, purge_old_records, watch_dir, retention_days)
        except asyncio.CancelledError:
            break
        except Exception as err:
            _LOGGER.exception("Error during retention purge: %s", err)

        await asyncio.sleep(interval_seconds)


async def main() -> None:
    """Main service lifecycle entry point."""
    options = load_options()
    watch_dir = Path(options["watch_directory"])
    snapshot_offset = int(options.get("snapshot_offset", 5))
    retention_days = int(options.get("retention_days", 7))
    purge_interval_hours = int(options.get("purge_interval_hours", 24))

    _LOGGER.info("Reolink Video Library Manager starting with options:")
    _LOGGER.info("  watch_directory: %s", watch_dir)
    _LOGGER.info("  snapshot_offset: %d seconds", snapshot_offset)
    _LOGGER.info("  retention_days: %d days", retention_days)
    _LOGGER.info("  purge_interval_hours: %d hours", purge_interval_hours)

    # Ensure watch directory exists
    if not watch_dir.exists():
        try:
            watch_dir.mkdir(parents=True, exist_ok=True)
            _LOGGER.info("Created watch directory: %s", watch_dir)
        except Exception as err:
            _LOGGER.error("Could not create watch directory %s: %s", watch_dir, err)

    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()

    # Start background processing worker
    worker_task = asyncio.create_task(video_worker(queue, snapshot_offset))

    # Start periodic retention purge task
    purge_task = asyncio.create_task(
        purge_scheduler(watch_dir, retention_days, purge_interval_hours)
    )

    # Initial scan for existing videos
    await scan_and_queue_missing_snapshots(watch_dir, queue)

    # Start watchdog filesystem observer
    event_handler = VideoQueueHandler(loop, queue)
    observer = Observer()
    observer.schedule(event_handler, str(watch_dir), recursive=True)
    observer.start()
    _LOGGER.info("Filesystem observer started recursively on %s", watch_dir)

    stop_event = asyncio.Event()

    def _stop(*args):
        _LOGGER.info("Shutdown signal received")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _stop)
        except NotImplementedError:
            pass

    try:
        await stop_event.wait()
    finally:
        _LOGGER.info("Stopping observer and worker tasks...")
        observer.stop()
        await loop.run_in_executor(None, observer.join)
        worker_task.cancel()
        purge_task.cancel()
        await asyncio.gather(worker_task, purge_task, return_exceptions=True)
        _LOGGER.info("Reolink Video Library Manager stopped.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
