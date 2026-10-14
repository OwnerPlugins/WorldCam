#!/bin/bash

version='7.1'
changelog='Player no longer closes when zapping, stale YouTube answers ignored, YouTube channel and live links resolved, webcams exported to bouquets play (YouTube via ytdlpwrapper), location export exports its own webcams, M3U playlists no longer duplicated, Top Webcams and Locations open the selected row, lists load without freezing the GUI, no opkg at startup, updates from OwnerPlugins, installer installs yt-dlp on Python 3 images.'

TMPPATH=/tmp/WorldCam-install
FILEPATH=/tmp/WorldCam-main.tar.gz

echo "Starting WorldCam installation..."

if [ ! -d /usr/lib64 ]; then
    PLUGINPATH=/usr/lib/enigma2/python/Plugins/Extensions/WorldCam
else
    PLUGINPATH=/usr/lib64/enigma2/python/Plugins/Extensions/WorldCam
fi

cleanup() {
    echo "Cleaning up temporary files..."
    [ -d "$TMPPATH" ] && rm -rf "$TMPPATH"
    [ -f "$FILEPATH" ] && rm -f "$FILEPATH"
    [ -d "/tmp/WorldCam-main" ] && rm -rf "/tmp/WorldCam-main"
    [ -f "/tmp/worldcam.tar.gz" ] && rm -f "/tmp/worldcam.tar.gz"
}

detect_os() {
    if [ -f /var/lib/dpkg/status ]; then
        OSTYPE="DreamOs"
        STATUS="/var/lib/dpkg/status"
    elif [ -f /etc/opkg/opkg.conf ] || [ -f /var/lib/opkg/status ]; then
        OSTYPE="OE"
        STATUS="/var/lib/opkg/status"
    else
        OSTYPE="Unknown"
        STATUS=""
    fi
    echo "Detected OS type: $OSTYPE"
}

detect_os

cleanup
mkdir -p "$TMPPATH"

# Refresh the package lists once
FEED_UPDATED=0
update_feeds() {
    [ "$FEED_UPDATED" = "1" ] && return
    echo "Updating package lists..."
    case "$OSTYPE" in
        "DreamOs") apt-get update >/dev/null 2>&1 ;;
        "OE") opkg update >/dev/null 2>&1 ;;
    esac
    FEED_UPDATED=1
}

install_pkg() {
    pkg=$1
    if [ -n "$STATUS" ] && grep -qx "Package: $pkg" "$STATUS" 2>/dev/null; then
        echo "$pkg already installed"
        return 0
    fi
    update_feeds
    echo "Installing $pkg..."
    case "$OSTYPE" in
        "DreamOs")
            apt-get install -y "$pkg" >/dev/null 2>&1 && return 0 ;;
        "OE")
            opkg install "$pkg" >/dev/null 2>&1 && return 0 ;;
        *)
            echo "Cannot install $pkg on unknown OS type"
            return 1 ;;
    esac
    echo "Could not install $pkg, continuing anyway..."
    return 1
}

if ! command -v wget >/dev/null 2>&1; then
    install_pkg wget
    command -v wget >/dev/null 2>&1 || { echo "wget is required"; exit 1; }
fi

# WorldCam is Python 3 only (images may have python3 without 'python')
if ! command -v python3 >/dev/null 2>&1; then
    echo "ERROR: WorldCam requires a Python 3 image"
    exit 1
fi
echo "Python: $(python3 --version 2>&1)"

install_pkg python3-six

if [ "$OSTYPE" = "OE" ]; then
    echo "Installing additional multimedia packages..."
    for pkg in ffmpeg exteplayer3 gstplayer enigma2-plugin-systemplugins-serviceapp; do
        install_pkg "$pkg"
    done
fi

# yt-dlp: needed for YouTube webcams
ytdlp_ok() {
    command -v yt-dlp >/dev/null 2>&1 || python3 -c "import yt_dlp" >/dev/null 2>&1
}

if ! ytdlp_ok; then
    install_pkg python3-yt-dlp
fi
if ! ytdlp_ok; then
    echo "yt-dlp not in the feed, installing it with pip..."
    command -v pip3 >/dev/null 2>&1 || install_pkg python3-pip
    if command -v pip3 >/dev/null 2>&1; then
        pip3 install -U yt-dlp >/dev/null 2>&1 || \
            pip3 install -U --break-system-packages yt-dlp >/dev/null 2>&1
    fi
fi
if ytdlp_ok; then
    echo "yt-dlp OK: $(yt-dlp --version 2>/dev/null || python3 -m yt_dlp --version 2>/dev/null)"
else
    echo "WARNING: yt-dlp could not be installed: YouTube webcams will not play"
fi

echo "Downloading WorldCam..."
wget --no-check-certificate "https://github.com/OwnerPlugins/WorldCam/archive/refs/heads/main.tar.gz" -O "$FILEPATH"
if [ $? -ne 0 ]; then
    echo "Failed to download WorldCam package!"
    cleanup
    exit 1
fi

echo "Extracting package..."
tar -xzf "$FILEPATH" -C "$TMPPATH"
if [ $? -ne 0 ]; then
    echo "Failed to extract WorldCam package!"
    cleanup
    exit 1
fi

echo "Installing plugin files..."
mkdir -p "$PLUGINPATH"

if [ -d "$TMPPATH/WorldCam-main/usr/lib/enigma2/python/Plugins/Extensions/WorldCam" ]; then
    cp -r "$TMPPATH/WorldCam-main/usr/lib/enigma2/python/Plugins/Extensions/WorldCam"/* "$PLUGINPATH/" 2>/dev/null
    echo "Copied from standard plugin directory"
elif [ -d "$TMPPATH/WorldCam-main/usr/lib64/enigma2/python/Plugins/Extensions/WorldCam" ]; then
    cp -r "$TMPPATH/WorldCam-main/usr/lib64/enigma2/python/Plugins/Extensions/WorldCam"/* "$PLUGINPATH/" 2>/dev/null
    echo "Copied from lib64 plugin directory"
elif [ -d "$TMPPATH/WorldCam-main/usr" ]; then
    cp -r "$TMPPATH/WorldCam-main/usr"/* /usr/ 2>/dev/null
    echo "Copied entire usr structure"
else
    echo "Could not find plugin files in extracted archive"
    echo "Available directories in tmp:"
    find "$TMPPATH" -type d | head -10
    cleanup
    exit 1
fi

sync

echo "Verifying installation..."
if [ -d "$PLUGINPATH" ] && [ -n "$(ls -A "$PLUGINPATH" 2>/dev/null)" ]; then
    echo "Plugin directory found and not empty: $PLUGINPATH"
    echo "Contents:"
    ls -la "$PLUGINPATH/" | head -10
else
    echo "Plugin installation failed or directory is empty!"
    cleanup
    exit 1
fi

if [ "$OSTYPE" = "OE" ]; then
    echo "Installing streaming dependencies..."
    for pkg in \
        streamlink \
        enigma2-plugin-extensions-streamlinkwrapper \
        enigma2-plugin-extensions-streamlinkproxy \
        enigma2-plugin-extensions-ytdlpwrapper \
        enigma2-plugin-extensions-ytdlwrapper \
        python3-re \
        gstreamer1.0-plugins-bad \
        gstreamer1.0-plugins-ugly \
        gstreamer1.0-libav; do
        install_pkg "$pkg"
    done
fi

echo "Creating YouTube cookies file..."
mkdir -p /etc/enigma2
cat > /etc/enigma2/yt_cookies.txt << 'EOF'
# Netscape HTTP Cookie File
.youtube.com	TRUE	/	TRUE	2147483647	CONSENT	YES+cb.20210615-14-p0.it+FX+294
.youtube.com	TRUE	/	TRUE	2147483647	PREF	f1=50000000
EOF
echo "YouTube cookies file created"

cleanup
sync

FILE="/etc/image-version"
box_type=$(sed -n '1p' /etc/hostname 2>/dev/null || echo "Unknown")
# distro_value=$(grep '^distro=' "$FILE" 2>/dev/null | awk -F '=' '{print $2}')
# distro_version=$(grep '^version=' "$FILE" 2>/dev/null | awk -F '=' '{print $2}')
distro_value="Unknown"
distro_version="Unknown"
if [ -r /etc/os-release ]; then
    distro_value=$(grep '^NAME=' /etc/os-release 2>/dev/null | cut -d'"' -f2)
    distro_version=$(grep '^VERSION_ID=' /etc/os-release 2>/dev/null | cut -d'"' -f2)
elif [ -r /etc/issue ]; then
    distro_value=$(head -n 1 /etc/issue 2>/dev/null | awk '{print $1}')
    distro_version=$(head -n 1 /etc/issue 2>/dev/null | awk '{print $2}')
elif [ -r /etc/vtiversion.info ]; then
    distro_value=$(head -n 1 /etc/vtiversion.info 2>/dev/null)
elif [ -r /etc/issue.net ]; then
    distro_value=$(head -n 1 /etc/issue.net 2>/dev/null | awk '{print $1}')
    distro_version=$(head -n 1 /etc/issue.net 2>/dev/null | awk '{print $2}')
fi

[ -z "$distro_value" ] && distro_value="Unknown"
[ -z "$distro_version" ] && distro_version="Unknown"
python_vers=$(python3 --version 2>&1)

cat <<EOF

#########################################################
#       WorldCam $version INSTALLED SUCCESSFULLY        #
#                developed by LULULLA                   #
#               https://corvoboys.org                   #
#########################################################
#        Restart Enigma2 to use the plugin              #
#########################################################
^^^^^^^^^^Debug information:
BOX MODEL: $box_type
OS SYSTEM: $OSTYPE
PYTHON: $python_vers
IMAGE NAME: ${distro_value:-Unknown}
IMAGE VERSION: ${distro_version:-Unknown}
CHANGELOG: $changelog
PLUGIN PATH: $PLUGINPATH
PLUGIN VERSION: $version
EOF

exit 0