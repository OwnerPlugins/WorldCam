import subprocess
from importlib.util import find_spec
from shutil import which
from os.path import exists

REQUIRED_PACKAGES = {
    "ffmpeg": "ffmpeg",
    "exteplayer3": "exteplayer3",
    "streamlink": "streamlink",
    "yt-dlp": "yt-dlp",
    "youtube-dl": "youtube-dl",
    "gstplayer": "gst-play-1.0",
    "requests": "requests",
    "serviceapp": "/etc/enigma2/serviceapp.conf",
    "streamlinkwrapper": "/usr/lib/enigma2/python/Plugins/Extensions/StreamlinkWrapper",
    "ytdlpwrapper": "/usr/lib/enigma2/python/Plugins/Extensions/YtdlpWrapper",
    "ytdlwrapper": "/usr/lib/enigma2/python/Plugins/Extensions/YtdlWrapper",
}

OPKG_PACKAGES = [
    "ffmpeg",
    "exteplayer3",
    "enigma2-plugin-systemplugins-serviceapp",
    "gstplayer",
    "streamlink",
    "enigma2-plugin-extensions-streamlinkwrapper",
    "enigma2-plugin-extensions-ytdlpwrapper",
    "enigma2-plugin-extensions-ytdlwrapper",
    "{py}-yt-dlp",
    "{py}-youtube-dl",
    "{py}-requests",
    "gstreamer1.0-plugins-good",
    "gstreamer1.0-plugins-bad",
    "gstreamer1.0-plugins-ugly",
    "gstreamer1.0-libav"
]


def get_python_variant():
    return "python3" if which("python3") else "python"


def _has_ytdlp():
    """
    yt-dlp is usable if either the binary or the Python module
    (python3 -m yt_dlp) is available.
    """
    if which("yt-dlp") is not None:
        return True
    for path in ("/usr/bin/yt-dlp", "/usr/local/bin/yt-dlp"):
        if exists(path):
            return True
    # Fallback: python module (found without importing it: slow)
    try:
        return find_spec("yt_dlp") is not None
    except Exception:
        return False


def check_requirements(logger=None):
    """
    Check optional dependencies needed for YouTube playback.
    Returns a list of missing component names (str).
    """
    missing = []

    # yt-dlp: binary OR python module
    if not _has_ytdlp():
        missing.append("yt-dlp")

    # streamlink (binary)
    if which("streamlink") is None:
        missing.append("streamlink")

    if logger and missing:
        logger.warning("Missing optional components: " + ", ".join(missing))
    return missing


def install_missing_packages(missing, logger=None):
    python_variant = get_python_variant()
    try:
        subprocess.call(["opkg", "update"])
        for pkg in OPKG_PACKAGES:
            name = pkg.replace("{py}", python_variant)
            base = name.split("/")[-1].replace("enigma2-plugin-extensions-",
                                               "").replace("{py}-", "").replace(python_variant + "-", "")
            if base in missing or base.split("-")[0] in missing:
                cmd = ["opkg", "install", name]
                if logger:
                    logger.info("Installing: " + " ".join(cmd))
                subprocess.call(cmd)
        return True
    except Exception as e:
        if logger:
            logger.error("Failed to install packages: " + str(e))
        return False
