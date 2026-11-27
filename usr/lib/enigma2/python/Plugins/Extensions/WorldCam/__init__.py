# -*- coding: utf-8 -*-
import gettext
from os import environ
from os.path import join, dirname, exists, getsize, isdir
from Components.Language import language
from Tools.Directories import resolveFilename, SCOPE_PLUGINS

__author__ = "Lululla"
__email__ = "ekekaz@gmail.com"
__copyright__ = 'Copyright (c) 2024 Lululla'
__license__ = "GPL-v2"
__version__ = "7.7"

PLUGIN_VERSION = __version__
PLUGIN_PATH = dirname(__file__)
DEFAULT_ICON = join(PLUGIN_PATH, "pics/webcam.png")
BASE_URL = "https://www.skylinewebcams.com"

PluginLanguageDomain = 'WorldCam'
PluginLanguagePath = 'Extensions/WorldCam/locale'
AgentRequest = 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.130 Safari/537.36 OPR/66.0.3515.115'
installer_url = 'aHR0cHM6Ly9yYXcuZ2l0aHVidXNlcmNvbnRlbnQuY29tL093bmVyUGx1Z2lucy9Xb3JsZENhbS9tYWluL2luc3RhbGxlci5zaA=='
developer_url = 'aHR0cHM6Ly9hcGkuZ2l0aHViLmNvbS9yZXBvcy9Pd25lclBsdWdpbnMvV29ybGRDYW0='


def _(txt):
    """
    Translate the given text using gettext, with fallback and debug print.
    """
    if not txt:
        return ""
    translated = gettext.dgettext(PluginLanguageDomain, txt)
    if translated:
        return translated
    print(
        "[%s] fallback to default translation for %s" %
        (PluginLanguageDomain, txt))
    return gettext.gettext(txt)


def paypal():
    return _(
        "Like this plugin?\n"
        "Buy me a coffee by scanning QR code.\n"
        "Your support keeps development alive!\n"
    )


def localeInit():
    """
    Initialize locale environment and bind plugin's translation domain.
    """
    environ["LANGUAGE"] = language.getLanguage()[:2]
    gettext.bindtextdomain(
        PluginLanguageDomain,
        resolveFilename(
            SCOPE_PLUGINS,
            PluginLanguagePath))


localeInit()
language.addCallback(localeInit)


def _auto_install_streamlink_plugin():
    """Installa automaticamente il plugin Skyline per Streamlink di sistema"""
    try:
        import sys
        streamlink_plugins_dir = None
        
        # Trova la cartella dei plugin di Streamlink nel sistema
        for path in sys.path:
            if "site-packages" in path:
                test_dir = join(path, "streamlink", "plugins")
                if isdir(test_dir):
                    streamlink_plugins_dir = test_dir
                    break
                    
        if not streamlink_plugins_dir:
            return
            
        plugin_file = join(streamlink_plugins_dir, "skylinewebcams.py")
        
        # Se il plugin non esiste (o è corrotto), lo crea
        if not exists(plugin_file) or getsize(plugin_file) < 100:
            plugin_code = '''import re
from urllib.request import Request, urlopen
from streamlink.plugin import Plugin, pluginmatcher
from streamlink.stream.hls import HLSStream

STREAM_BASE_URL = "https://hd-auth.skylinewebcams.com"

@pluginmatcher(re.compile(r"https?://(?:www\\.)?skylinewebcams\\.com/.*\\.html"))
class SkylineWebcams(Plugin):
    def _get_streams(self):
        headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; SM-G960F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            "Accept-Language": "en-US,en;q=0.5",
            "Referer": "https://skylinewebcams.com",
        }
        req = Request(self.url, headers=headers)
        content = urlopen(req, timeout=15).read().decode("utf-8", errors="ignore")
        
        stream_url = None
        hls_match = re.search(r'(?:url|source)\\s*:\\s*[\\'"]([^\\'"]+\\.m3u8[^\\'"]*)[\\'"]', content)
        if hls_match:
            relative_url = hls_match.group(1)
            id_match = re.search(r"\\?a=([^&\\"']+)", relative_url)
            if id_match:
                stream_url = STREAM_BASE_URL + "/live.m3u8?a=" + id_match.group(1)
            elif relative_url.startswith("http"):
                stream_url = relative_url
                
        if stream_url:
            return {"live": HLSStream(self.session, stream_url, headers=headers)}

__plugin__ = SkylineWebcams
'''
            with open(plugin_file, "w", encoding="utf-8") as f:
                f.write(plugin_code)
            print("[WorldCam] Streamlink SkylineWebcams plugin auto-installed.")
    except Exception as e:
        print("[WorldCam] Failed to auto-install Streamlink plugin: %s" % str(e))


_auto_install_streamlink_plugin()

from Components.config import config, ConfigSubsection, ConfigSelection

# Initialize plugin configuration
config.plugins.WorldCam = ConfigSubsection()
config.plugins.WorldCam.youtube_wrapper = ConfigSelection(default="streamlink", choices=[
    ("yt-dlp", "yt-dlp"),
    ("streamlink", "Streamlink"),
    ("auto", "Auto (Fallback)")
])
config.plugins.WorldCam.skyline_wrapper = ConfigSelection(default="streamlink", choices=[
    ("streamlink", "Streamlink"),
    ("yt-dlp", "yt-dlp"),
    ("auto", "Auto (Fallback)")
])
config.plugins.WorldCam.export_delay = ConfigSelection(default="0.5", choices=[
    ("0.0", "0.0s (Fast/Risky)"),
    ("0.3", "0.3s (Quick)"),
    ("0.5", "0.5s (Balanced)"),
    ("1.0", "1.0s (Safe)")
])
config.plugins.WorldCam.export_workers = ConfigSelection(default="2", choices=[
    ("1", "1 (Safe)"),
    ("2", "2 (Balanced)"),
    ("3", "3 (Fast)"),
    ("5", "5 (Risky)")
])
