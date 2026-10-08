#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
WorldCam Plugin - YouTube helper
Adapted from TVGarden (by Lululla) for WorldCam.

Resolves YouTube URLs using yt-dlp with:
- non-blocking friendly API (call from twisted.deferToThread)
- format fallback chain in a single yt-dlp invocation
- android_vr client first (no JS runtime required)
- JS runtime detection (node/bun/quickjs) as fallback
"""

import subprocess
import re
import sys
from os.path import exists
from shutil import which
from urllib.parse import unquote


def _make_logger():
    """Try plugin Logger, fall back to a simple stdout logger (CLI mode)."""
    try:
        from .utils import Logger  # type: ignore
        return Logger()
    except Exception:
        pass

    class _StdoutLogger:
        def _p(self, lvl, msg, *args):
            try:
                line = msg % args if args else msg
            except Exception:
                line = msg
            print("[WorldCam YouTube][%s] %s" % (lvl, line))

        def debug(self, msg, *a):   self._p("DEBUG", msg, *a)
        def info(self, msg, *a):    self._p("INFO",  msg, *a)
        def warning(self, msg, *a): self._p("WARN",  msg, *a)
        def error(self, msg, *a):   self._p("ERROR", msg, *a)

    return _StdoutLogger()


log = _make_logger()


# Receivers are slow: starting yt-dlp alone can take 10+ seconds
VERSION_TIMEOUT = 60
RESOLVE_TIMEOUT = 150

# Progressive MP4 first (VOD), then anything playable (live = HLS)
FORMAT_CHAIN = "18/22/best[ext=mp4][protocol^=http]/best"

# Attempts in order: extra yt-dlp arguments for each run
CLIENT_ATTEMPTS = [
    ["--extractor-args", "youtube:player_client=android_vr"],
    [],
]

# JavaScript runtimes yt-dlp can use besides deno (enabled if installed)
JS_RUNTIMES = (("node", "node"), ("bun", "bun"), ("quickjs", "qjs"))

_ytdlp_cmd = None
_js_args = None


def find_js_runtime_args():
    """--js-runtimes arguments for an installed runtime (empty if none)."""
    global _js_args
    if _js_args is None:
        _js_args = []
        for runtime, binary in JS_RUNTIMES:
            path = which(binary)
            if path:
                log.info("JavaScript runtime found: %s" % path)
                _js_args = ["--js-runtimes", "%s:%s" % (runtime, path)]
                break
    return _js_args


def find_ytdlp():
    """Return the command (list) used to run yt-dlp, or None."""
    global _ytdlp_cmd
    if _ytdlp_cmd:
        return _ytdlp_cmd

    candidates = []
    found = which("yt-dlp")
    if found:
        candidates.append([found])
    for path in ("/usr/bin/yt-dlp", "/usr/local/bin/yt-dlp"):
        if exists(path) and [path] not in candidates:
            candidates.append([path])
    for python in (sys.executable, "/usr/bin/python3", "/usr/bin/python"):
        if python and exists(python):
            candidates.append([python, "-m", "yt_dlp"])

    for cmd in candidates:
        try:
            result = subprocess.run(
                cmd + ["--version"],
                capture_output=True, text=True, timeout=VERSION_TIMEOUT)
            if result.returncode == 0:
                log.info("yt-dlp found: %s (version %s)" %
                         (" ".join(cmd), result.stdout.strip()))
                _ytdlp_cmd = cmd
                return cmd
        except subprocess.TimeoutExpired:
            log.warning("yt-dlp too slow to start: %s" % " ".join(cmd))
        except Exception as e:
            log.debug("yt-dlp candidate %s failed: %s" % (" ".join(cmd), e))

    log.error("yt-dlp not found")
    return None


def extract_video_id(url):
    """Extract the video ID from any YouTube URL form."""
    patterns = [
        r'(?:https?://)?(?:www\.|m\.)?youtube\.com/watch\?(?:.*&)?v=([^&#]+)',
        r'(?:https?://)?youtu\.be/([^?&#/]+)',
        r'(?:https?://)?(?:www\.)?youtube\.com/embed/([^/?&#]+)',
        r'(?:https?://)?(?:www\.)?youtube-nocookie\.com/embed/([^/?&#]+)',
        r'(?:https?://)?(?:www\.)?youtube\.com/v/([^/?&#]+)',
        r'(?:https?://)?(?:www\.)?youtube\.com/shorts/([^/?&#]+)',
        r'(?:https?://)?(?:www\.)?youtube\.com/live/([^/?&#]+)',
    ]
    try:
        decoded = unquote(url)
        for pattern in patterns:
            match = re.search(pattern, decoded, re.IGNORECASE)
            if match:
                return match.group(1)
    except Exception as e:
        log.error("Error extracting video ID: %s" % e)
    return None


def _short_error(stderr):
    """Last meaningful yt-dlp error line."""
    lines = [l.strip() for l in (stderr or "").splitlines() if l.strip()]
    errors = [l for l in lines if l.startswith("ERROR")]
    text = (errors or lines or ["unknown error"])[-1]
    text = text.replace("ERROR: ", "")
    return text[:160]


def _run_ytdlp(cmd):
    """Run one yt-dlp command; return (stream_url, error_message)."""
    log.info("yt-dlp: %s" % " ".join(cmd))
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=RESOLVE_TIMEOUT)
    except subprocess.TimeoutExpired:
        log.warning("yt-dlp timeout")
        return None, "yt-dlp timeout"
    except Exception as e:
        log.warning("yt-dlp error: %s" % e)
        return None, str(e)

    for line in (result.stdout or "").splitlines():
        line = line.strip()
        if line.startswith(("http://", "https://")):
            log.info("yt-dlp OK: %s..." % line[:80])
            return line, None

    log.warning("yt-dlp failed (code %s): %s" %
                (result.returncode,
                 (result.stderr[-500:] if result.stderr else "")))
    return None, _short_error(result.stderr)


def get_stream_with_ytdlp(ytdlp_cmd, video_id):
    """Resolve video_id; return (stream_url, error_message)."""
    youtube_url = "https://www.youtube.com/watch?v=" + video_id
    base = ytdlp_cmd + [
        "-g", "--no-playlist", "--no-warnings",
        "--socket-timeout", "20",
        "-f", FORMAT_CHAIN,
    ] + find_js_runtime_args()

    error = None
    for extra in CLIENT_ATTEMPTS:
        stream_url, error = _run_ytdlp(base + extra + [youtube_url])
        if stream_url:
            return stream_url, None
        if error == "yt-dlp timeout":
            break
    return None, error


def resolve_youtube(url):
    """Resolve a YouTube URL; return (stream_url, error_message)."""
    video_id = extract_video_id(url)
    if not video_id:
        log.error("Cannot extract video ID from: %s" % url)
        return None, "invalid YouTube URL"

    ytdlp = find_ytdlp()
    if not ytdlp:
        return None, "yt-dlp is not installed"

    return get_stream_with_ytdlp(ytdlp, video_id)


def get_youtube_stream(url):
    """Resolve a YouTube URL; return the stream URL or None."""
    return resolve_youtube(url)[0]


def get_diagnostics():
    """Return environment info for testing/troubleshooting."""
    import platform
    diag = {
        "python":        sys.version.split()[0],
        "platform":      platform.platform(),
        "machine":       platform.machine(),
        "ytdlp_cmd":     None,
        "ytdlp_version": None,
        "js_runtime":    None,
    }
    cmd = find_ytdlp()
    if cmd:
        diag["ytdlp_cmd"] = " ".join(cmd)
        try:
            r = subprocess.run(cmd + ["--version"], capture_output=True,
                               text=True, timeout=VERSION_TIMEOUT)
            if r.returncode == 0:
                diag["ytdlp_version"] = r.stdout.strip()
        except Exception:
            pass
    js_args = find_js_runtime_args()
    if js_args:
        diag["js_runtime"] = js_args[-1]
    return diag