#!/usr/bin/python
# -*- coding: utf-8 -*-

from json import load, dump
from os import makedirs, remove, listdir
from os.path import abspath, dirname, exists, isfile, join, isdir

from re import search, sub
import sys
from time import strftime
from threading import Lock
import html

from urllib.parse import quote, urlparse, urlunparse
from enigma import eDVBDB, eEnv
from Tools.Directories import resolveFilename, SCOPE_CURRENT_SKIN, SCOPE_PLUGINS

try:
    from Components.AVSwitch import AVSwitch
except ImportError:
    from Components.AVSwitch import eAVControl as AVSwitch

from . import _
from . import checkdependencies

"""
#########################################################
#                                                       #
#  Worldcam Utils for Plugin                            #
#  Version: 5.0                                         #
#  Created by Lululla (https://github.com/Belfagor2005) #
#  License: CC BY-NC-SA 4.0                             #
#  https://creativecommons.org/licenses/by-nc-sa/4.0    #
#  Last Modified: "18:30 - 20250703"                    #
#                                                       #
#  Credits:                                             #
#  - Original concept Lululla                           #
#  Usage of this code without proper attribution        #
#  is strictly prohibited.                              #
#  For modifications and redistribution,                #
#  please maintain this credit header.                  #
#########################################################
"""
__author__ = "Lululla"

# Python 3 runtime
PY3 = True

# Plugin path and resources
PLUGIN_PATH = dirname(__file__)
COUNTRY_CODES_FILE = {}
COUNTRY_CODES_FILE = join(PLUGIN_PATH, "cowntry_code.json")
DEFAULT_ICON = join(PLUGIN_PATH, "pics/webcam.png")


def reload_services():
    """Reload the list of services"""
    eDVBDB.getInstance().reloadServicelist()
    eDVBDB.getInstance().reloadBouquets()


class Logger:
    _instance = None
    _initialized = False
    LEVELS = {
        "DEBUG": ("\033[92m", "[DEBUG]"),    # green
        "INFO": ("\033[97m", "[INFO] "),     # white
        "WARNING": ("\033[93m", "[WARN] "),  # yellow
        "ERROR": ("\033[91m", "[ERROR]"),    # red
        "CRITICAL": ("\033[95m", "[CRIT] ")  # magenta
    }
    END = "\033[0m"
    _lock = Lock()

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(Logger, cls).__new__(cls)
        return cls._instance

    def __init__(self, log_path=None, clear_on_start=True):
        if self._initialized:
            return

        self._initialized = True

        log_dir = "/tmp/worldcam"

        if not exists(log_dir):
            try:
                makedirs(log_dir)
            except Exception:
                pass

        # Set default log path if not provided
        self.log_path = log_path or join(log_dir, "worldcam.log")

        # Clear log if requested
        if clear_on_start and exists(self.log_path):
            try:
                remove(self.log_path)
            except Exception as e:
                print(f"Couldn't clear log file: {str(e)}")

    def log(self, message, level="INFO", *args):
        # Get prefix and label, default to INFO if unknown level
        prefix, label = self.LEVELS.get(level, self.LEVELS["INFO"])
        timestamp = strftime("%Y-%m-%d %H:%M:%S")

        # Create formatted console message with colors
        console_msg = f"{timestamp} {label} {prefix}{message}{self.END}"
        print(console_msg)

        # Write to log file (without color codes)
        if self.log_path:
            try:
                with open(self.log_path, "a") as f:
                    f.write(f"{timestamp} {label} {message}\n")
            except Exception as e:
                print(f"Log write failed: {str(e)}")

    @staticmethod
    def _format(message, args):
        """message % args, never raising on a format mismatch"""
        if not args:
            return message
        try:
            return message % args
        except (TypeError, ValueError):
            return " ".join([str(message)] + [str(a) for a in args])

    def debug(self, message, *args):
        self.log(self._format(message, args), "DEBUG")

    def info(self, message, *args):
        self.log(self._format(message, args), "INFO")

    def warning(self, message, *args):
        self.log(self._format(message, args), "WARNING")

    def error(self, message, *args):
        self.log(self._format(message, args), "ERROR")

    def critical(self, message, *args):
        self.log(self._format(message, args), "CRITICAL")

    def exception(self, message, *args):
        exc_info = self._get_exception_info()
        self.log(
            "EXCEPTION: %s\n%s" % (self._format(message, args), exc_info),
            "ERROR")

    def _get_exception_info(self):
        """Get formatted exception info"""
        import sys
        import traceback
        exc_type, exc_value, exc_traceback = sys.exc_info()
        return ''.join(
            traceback.format_exception(
                exc_type,
                exc_value,
                exc_traceback))

    # def info(self, message, *args):
        # self.log(message, "INFO")

    # def warning(self, message, *args):
        # self.log(message, "WARNING")

    # def error(self, message, *args):
        # self.log(message, "ERROR")

    # def critical(self, message, *args):
        # self.log(message, "CRITICAL")

    # def debug(self, message, *args):
        # self.log(message, "DEBUG")


# Own file name: the generic favorites.json is used by other plugins too
FAVORITES_FILE = join(
    eEnv.resolve("${sysconfdir}/enigma2"), "worldcam_favorites.json")
# File used by older versions (read once to migrate the favorites)
OLD_FAVORITES_FILE = join(
    eEnv.resolve("${sysconfdir}/enigma2"), "favorites.json")


# Update the safe_encode_url function
def safe_encode_url(url):
    """Safely encode URLs with non-ASCII characters"""
    if isinstance(url, str):
        try:
            parsed = urlparse(url)
            netloc = parsed.netloc.encode('idna').decode('ascii')
            path = quote(parsed.path, safe='/-_')
            query = quote(parsed.query, safe='=&')
            return urlunparse((
                parsed.scheme,
                netloc,
                path,
                parsed.params,
                query,
                parsed.fragment
            ))
        except Exception:
            # Fallback to UTF-8 encoding
            return url.encode('utf-8', 'ignore').decode('utf-8', 'ignore')
    return url


def encode_url(url):
    """Properly encode URLs with special characters"""
    if not url.startswith('http'):
        return url

    parsed = urlparse(url)
    encoded_path = quote(parsed.path)
    safe_url = urlunparse((
        parsed.scheme,
        parsed.netloc,
        encoded_path,
        parsed.params,
        parsed.query,
        parsed.fragment
    ))
    return safe_url


def clean_html_entities(text):
    """Clean HTML entities like &amp; &quot; etc."""
    if not text:
        return text

    try:
        # Unescape HTML entities
        cleaned = html.unescape(text)

        # Additional cleaning for specific cases
        cleaned = cleaned.replace('&amp;', '&')
        cleaned = cleaned.replace('&quot;', '"')
        cleaned = cleaned.replace('&apos;', "'")
        cleaned = cleaned.replace('&lt;', '<')
        cleaned = cleaned.replace('&gt;', '>')
        cleaned = cleaned.replace('&nbsp;', ' ')

        return cleaned.strip()
    except Exception as e:
        Logger().error(f"Error cleaning HTML entities: {str(e)}")
        return text


# try export with#
# DESCRIPTION Alghero - Mugoni Beach
# SERVICE
# 4097:0:1:46DE:221E:EC:0:0:0:0:streamlink%3a//https%3a//www.skylinewebcams.com/it/webcam/italia/sardegna/sassari/stintino.html:Sassari
# - Stintino - La Pelosa

def is_skyline_page(url):
    """True for a skylinewebcams.com webcam page (not a direct stream)"""
    u = (url or "").lower()
    return "skylinewebcams.com" in u and u.split("?")[0].endswith(".html")


def bouquet_service_lines(url, name):
    """
    #SERVICE / #DESCRIPTION lines for a webcam.
    Returns (lines, kind) with kind 'youtube', 'streamlink' or 'direct'.
    - YouTube: https://www.youtube.com/watch?v=ID, played from the
      bouquet by the yt-dlp wrapper plugin
    - skylinewebcams pages: streamlink:// (streamlink wrapper plugin)
    - anything else is a direct stream
    """
    url = str(url or "").replace("\r", " ").replace("\n", " ").strip()
    name = str(name or "").replace("\r", " ").replace("\n", " ").strip()
    if is_youtube_url(url):
        kind = "youtube"
        url = convert_youtube_embed_to_watch(url)
        service_url = url.replace(":", "%3a")
    elif is_skyline_page(url):
        kind = "streamlink"
        service_url = "streamlink%3a//" + url.replace(":", "%3a")
    else:
        kind = "direct"
        service_url = url.replace(":", "%3a")
    lines = "#SERVICE 4097:0:1:0:0:0:0:0:0:0:%s:%s\n#DESCRIPTION %s\n" % (
        service_url, name.replace(":", "%3a"), name)
    return lines, kind


class FavoritesManager:
    @staticmethod
    def _migrate_old_file():
        """Copy WorldCam favorites from the old generic favorites.json"""
        if exists(FAVORITES_FILE) or not exists(OLD_FAVORITES_FILE):
            return
        try:
            with open(OLD_FAVORITES_FILE, "r", encoding="utf-8") as f:
                data = load(f)
            # Only a WorldCam list: [{"name": ..., "url": ...}, ...]
            if isinstance(data, list) and all(
                    isinstance(x, dict) and set(x) == {"name", "url"}
                    for x in data):
                with open(FAVORITES_FILE, "w", encoding="utf-8") as f:
                    dump(data, f, indent=4, ensure_ascii=False)
                Logger().info("Favorites migrated to " + FAVORITES_FILE)
        except Exception as e:
            Logger().warning("Favorites migration skipped: %s" % str(e))

    @staticmethod
    def load_favorites():
        """Load favorites from the JSON file"""
        FavoritesManager._migrate_old_file()
        if not exists(FAVORITES_FILE):
            return []
        try:
            with open(FAVORITES_FILE, "r", encoding="utf-8") as f:
                data = load(f)
            return data if isinstance(data, list) else []
        except Exception as e:
            Logger().error(f"Error loading favorites: {str(e)}")
            return []

    @staticmethod
    def save_favorites(favorites):
        """Save favorites to the JSON file"""
        try:
            with open(FAVORITES_FILE, "w", encoding="utf-8") as f:
                dump(favorites, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            Logger().error(f"Error saving favorites: {str(e)}")
            return False

    @staticmethod
    def add_favorite(name, url):
        """Add a webcam to favorites"""
        favorites = FavoritesManager.load_favorites()

        # Already there
        if any(fav["url"] == url for fav in favorites):
            return False

        favorites.append({"name": name, "url": url})
        return FavoritesManager.save_favorites(favorites)

    @staticmethod
    def remove_favorite(url):
        """Remove a webcam from favorites"""
        favorites = FavoritesManager.load_favorites()
        new_favorites = [fav for fav in favorites if fav["url"] != url]

        if len(new_favorites) == len(favorites):
            return False  # Not found

        return FavoritesManager.save_favorites(new_favorites)

    @staticmethod
    def is_favorite(url):
        """Check whether a URL is in favorites"""
        return any(
            fav["url"] == url for fav in FavoritesManager.load_favorites())

    @staticmethod
    def export_to_bouquet(webcams=None, title=None):
        """
        Export webcams to an Enigma2 bouquet.
        Without arguments the favorites are exported to
        'WorldCam Favorites'; otherwise the given webcams go to their
        own bouquet named after title.
        """
        try:
            if webcams is None:
                webcams = FavoritesManager.load_favorites()
                display_name = "WorldCam Favorites"
                bouquet_name = "userbouquet.worldcam_favorites.tv"
                if not webcams:
                    return False, _("No favorites to export")
            else:
                title = title or "Webcams"
                display_name = "WorldCam - %s" % title
                safe = "".join(
                    c for c in title.lower() if c.isalnum() or c == "_")[:30]
                bouquet_name = "userbouquet.worldcam_%s.tv" % (
                    safe or "webcams")
                if not webcams:
                    return False, _("No webcams to export")

            bouquet_dir = eEnv.resolve("${sysconfdir}/enigma2")
            if not exists(bouquet_dir):
                makedirs(bouquet_dir)
            bouquet_path = join(bouquet_dir, bouquet_name)

            exported = 0
            kinds = set()
            with open(bouquet_path, "w", encoding="utf-8") as f:
                f.write("#NAME %s\n" % display_name)
                for cam in webcams:
                    url = cam.get("url")
                    if not url:
                        continue
                    lines, kind = bouquet_service_lines(
                        url, cam.get("name", ""))
                    f.write(lines)
                    kinds.add(kind)
                    exported += 1

            if not exported:
                try:
                    remove(bouquet_path)
                except Exception:
                    pass
                return False, _("No valid streams found")

            # Add to the bouquet list (once)
            bouquets_path = join(bouquet_dir, "bouquets.tv")
            if not exists(bouquets_path):
                with open(bouquets_path, "w") as f:
                    f.write("#NAME Bouquets (TV)\n")

            with open(bouquets_path, "r") as f:
                content = f.read()

            bouquet_ref = '#SERVICE 1:7:1:0:0:0:0:0:0:0:FROM BOUQUET "%s" ORDER BY bouquet' % bouquet_name
            if bouquet_ref not in content:
                with open(bouquets_path, "a") as f:
                    if content and not content.endswith("\n"):
                        f.write("\n")
                    f.write(bouquet_ref + "\n")

            reload_services()

            message = _("Exported %d webcams to '%s'") % (
                exported, display_name)
            if "youtube" in kinds:
                message += "\n\n" + _(
                    "YouTube entries play from the bouquet only with the "
                    "yt-dlp wrapper plugin "
                    "(enigma2-plugin-extensions-ytdlpwrapper).")
            if "streamlink" in kinds:
                message += "\n\n" + _(
                    "SkylineWebcams entries play from the bouquet only with "
                    "the streamlink wrapper plugin "
                    "(enigma2-plugin-extensions-streamlinkwrapper).")
            return True, message
        except Exception as e:
            Logger().error(f"Export error: {str(e)}")
            return False, _("Export failed: ") + str(e)


def isPythonFolder():
    path = "/usr/lib/"
    for name in listdir(path):
        fullname = join(path, name)
        if not isfile(fullname) and "python" in name:
            print(fullname)
            print("sys.version_info =", sys.version_info)
            x = join(fullname, "site-packages", "streamlink")
            print(x)
            if exists(x):
                return x
    return False


def is_streamlinkproxy_available():
    """Verifica se StreamlinkProxy è installato"""
    try:
        import subprocess
        result = subprocess.run(
            ["opkg", "list-installed", "enigma2-plugin-extensions-streamlinkproxy"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        return "enigma2-plugin-extensions-streamlinkproxy" in result.stdout
    except Exception:
        return False


def is_streamlink_available():
    streamlink_folder = isPythonFolder()
    return streamlink_folder


def get_streamlink_path():
    """Find streamlink executable in common locations"""
    possible_paths = [
        "/usr/bin/streamlink",
        "/usr/local/bin/streamlink",
        join(dirname(abspath(__file__)), "bin/streamlink")
    ]

    for path in possible_paths:
        if exists(path):
            return path
    return None


def is_exteplayer3_Available():
    from enigma import eEnv
    path = eEnv.resolve("$bindir/exteplayer3")
    return isfile(path)


def b64encoder(source):
    """Encode a string to base64, ensuring bytes input for Python 3."""
    import base64
    if PY3:
        source = source.encode("utf-8")
    content = base64.b64encode(source).decode("utf-8")
    return content


def b64decoder(data):
    """Robust base64 decoding with padding correction, returns decoded utf-8 string or empty on error."""
    import base64
    data = data.strip()
    pad = len(data) % 4
    if pad == 1:  # Invalid base64 length
        return ""
    if pad:
        data += "=" * (4 - pad)
    try:
        decoded = base64.b64decode(data)
        return decoded.decode("utf-8") if PY3 else decoded
    except Exception as e:
        print("Base64 decoding error: %s" % e)
        return ""


def get_system_language():
    """Retrieve system language from Enigma2 settings file."""
    try:
        with open("/etc/enigma2/settings", "r") as settings_file:
            for line in settings_file:
                if "config.osd.language=" in line:
                    lang = line.split("=")[1].strip().split("_")[0]
                    return lang
    except Exception:
        pass
    return "en"  # Default language


def disable_summary(screen_instance):
    """Disable summary features safely on a screen instance."""
    try:
        if hasattr(screen_instance, "createSummary"):
            screen_instance.createSummary = lambda: None

        if hasattr(screen_instance, "summary"):
            delattr(screen_instance, "summary")

        if not hasattr(screen_instance, "summary"):
            screen_instance.summary = None

        if not hasattr(screen_instance, "SimpleSummary"):
            screen_instance.SimpleSummary = None

    except Exception as e:
        logger = Logger()
        logger.error("Error disabling summary: " + str(e))


def safe_cleanup(screen_instance):
    """Perform safe cleanup on a screen instance with error handling."""
    logger = Logger()
    logger.info("safe_cleanup:")
    try:
        if hasattr(
                screen_instance,
                "cleanup") and callable(
                screen_instance.cleanup):
            screen_instance.cleanup()
        else:
            logger.debug(
                "No cleanup method for " +
                screen_instance.__class__.__name__)
    except Exception as e:
        logger.error(
            "Cleanup error in " +
            screen_instance.__class__.__name__ +
            ": " +
            str(e))


def _sort_by_name(items):
    """
    If items is a list of strings, sort directly.
    If items is a list of dicts with "name", sort by the name key.
    """
    if not items:
        return items
    if isinstance(items[0], str):
        return sorted(items, key=lambda x: x.lower())
    elif isinstance(items[0], dict) and "name" in items[0]:
        return sorted(items, key=lambda x: x["name"].lower())
    else:
        return items


def get_ytdlp_path():
    """Return the system yt-dlp executable path if available."""
    possible_paths = [
        "/usr/bin/yt-dlp",
        "/usr/local/bin/yt-dlp",
    ]

    for path in possible_paths:
        if exists(path):
            return path
    return None


def is_ytdlp_available(logger=None):
    """
    Check whether yt-dlp is available as a system binary.
    Returns True if a working yt-dlp binary is found, False otherwise.
    (Uses youtube_helper.find_ytdlp which auto-detects the binary.)
    """
    try:
        from .youtube_helper import find_ytdlp
        cmd = find_ytdlp()
        if cmd:
            if logger:
                logger.info("yt-dlp binary available: %s" % " ".join(cmd))
            return True
        if logger:
            logger.error("yt-dlp binary not found")
        return False
    except Exception as e:
        if logger:
            logger.error("yt-dlp availability check failed: %s" % str(e))
        return False

def extract_list_item(current, logger=None):
    """
    Universal function to extract item data from list selection
    Returns: (item_name, item_data) or (None, None) on error
    """
    try:
        if logger:
            logger.debug(f"Elemento selezionato: {str(current)[:100]}...")

        # Gestione struttura Enigma2 standard
        if isinstance(current, list) and len(current) > 0:
            # Caso 1: Elemento con struttura [nome, dati, ...]
            if len(current) >= 2:
                return current[0], current[1]
            # Caso 2: Elemento con solo nome
            elif len(current) == 1:
                return current[0], None

        # Gestione oggetti MenuList particolari
        elif hasattr(current, '__getitem__'):
            return current[0], current[1] if len(current) > 1 else None

        logger.error(f"Struttura elemento non supportata: {type(current)}")
        return None, None

    except Exception as e:
        if logger:
            logger.error(f"Errore estrazione elemento: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
        return None, None


# Language to flag mapping
language_flag_mapping = {
    "ar": "🇸🇦",  # Arabic
    "bg": "🇧🇬",  # Bulgarian
    "cs": "🇨🇿",  # Czech
    "de": "🇩🇪",  # German
    "el": "🇬🇷",  # Greek
    "en": "🇬🇧",  # English
    "es": "🇪🇸",  # Spanish
    "fa": "🇮🇷",  # Persian
    "fr": "🇫🇷",  # French
    "he": "🇮🇱",  # Hebrew
    "hr": "🇭🇷",  # Croatian
    "hu": "🇭🇺",  # Hungarian
    "it": "🇮🇹",  # Italian
    "jp": "🇯🇵",  # Japanese
    "ko": "🇰🇷",  # Korean
    "mk": "🇲🇰",  # Macedonian
    "nl": "🇳🇱",  # Dutch
    "pl": "🇵🇱",  # Polish
    "pt": "🇵🇹",  # Portuguese
    "ro": "🇷🇴",  # Romanian
    "ru": "🇷🇺",  # Russian
    "sk": "🇸🇰",  # Slovak
    "sl": "🇸🇮",  # Slovenian
    "sq": "🇦🇱",  # Albanian
    "sr": "🇷🇸",  # Serbian
    "th": "🇹🇭",  # Thai
    "tr": "🇹🇷",  # Turkish
    "vi": "🇻🇳",  # Vietnamese
    "zh": "🇨🇳",  # Chinese

    # AMERICA
    "argentina": "🇦🇷",  # Argentina
    "bb": "🇧🇧",  # Barbados
    "bm": "🇧🇲",  # Bermuda
    "bq": "🇧🇶",  # Paesi Bassi Caraibici
    "bo": "🇧🇴",  # Bolivia
    "br": "🇧🇷",  # Brasile
    "ca": "🇨🇦",  # Canada
    "cl": "🇨🇱",  # Cile
    "cr": "🇨🇷",  # Costa Rica
    "ec": "🇪🇨",  # Ecuador
    "sv": "🇸🇻",  # El Salvador
    "gd": "🇬🇩",  # Grenada
    "hn": "🇭🇳",  # Honduras
    "vni": "🇻🇮",  # Isole Vergini Americane
    "mx": "🇲🇽",  # Messico
    "pa": "🇵🇦",  # Panama
    "pe": "🇵🇪",  # Perù
    "do": "🇩🇴",  # Repubblica Dominicana
    "sx": "🇸🇽",  # Sint Maarten
    "us": "🇺🇸",  # Stati Uniti
    "uy": "🇺🇾",  # Uruguay
    "ve": "🇻🇪",  # Venezuela

    # AFRICA
    "cv": "🇨🇻",  # Capo Verde
    "eg": "🇪🇬",  # Egitto
    "ke": "🇰🇪",  # Kenya
    "mu": "🇲🇺",  # Mauritius
    "sn": "🇸🇳",  # Senegal
    "sc": "🇸🇨",  # Seychelles
    "za": "🇿🇦",  # Sudafrica
    "zm": "🇿🇲",  # Zambia
    "tz": "🇹🇿",  # Zanzibar (Tanzania)

    # ASIA
    "cn": "🇨🇳",  # Cina
    "ae": "🇦🇪",  # Emirati Arabi Uniti
    "ph": "🇵🇭",  # Filippine
    "jo": "🇯🇴",  # Giordania
    "id": "🇮🇩",  # Indonesia
    "il": "🇮🇱",  # Israele
    "mv": "🇲🇻",  # Maldive
    "lk": "🇱🇰",  # Sri Lanka
    "vn": "🇻🇳",  # Vietnam
}


CATEGORY_ICONS = {
    _("User Lists"): "user_lists.png",
    _("Continents"): "continents.png",
    _("Countries"): "countries.png",
    _("Categories"): "categories.png",
    _("Top Webcams"): "top_webcams.png",
    _("AMERICAS"): "americas.png",
    _("EUROPE"): "europe.png",
    _("AFRICA"): "africa.png",
}


def get_category_icon(icon_file_name):
    """
    Return the full file path of a category icon image.
    """
    plugin_path = dirname(__file__)
    full_path = join(plugin_path, "countries", icon_file_name)
    print("Icon path: %s" % full_path)
    return full_path


# Loading data
try:
    with open(COUNTRY_CODES_FILE, "r", encoding="utf-8") as f:
        worldcam_data = load(f)
    translations = worldcam_data.get("translations", {})
except Exception as e:
    logger = Logger()
    logger.error("Error loading country codes: " + str(e))
    country_codes = {}
    translations = {}


# Creating the flat map for research
country_map = {}
for lang, countries in translations.items():
    for name, code in countries.items():
        country_map[name.lower()] = code
        country_map[sub(r'\W', '', name.lower())] = code


def get_country_code(country_name):
    """Find country code with flexible matches"""
    if not country_name or not country_map:
        return None

    # Normalize the input
    name_clean = country_name.strip().lower()
    name_no_punct = sub(r'\W', '', name_clean)
    # Search by accuracy
    return (
        country_map.get(name_clean) or
        country_map.get(name_no_punct) or
        next((code for name, code in country_map.items()
              if name in name_clean or name_clean in name), None)
    )


# Flag Path Function
def get_flag_path(country_code=None):
    """
    Find the country code by matching various forms of country names.
    Returns None if no match is found.
    """
    if not country_code:
        country_code = "en"  # Default

    special_cases = {"ar": "argentina.png", "bm": "bm.png"}
    filename = special_cases.get(country_code, f"{country_code}.png")

    # Routes to check
    paths_to_check = [
        join(resolveFilename(SCOPE_CURRENT_SKIN), "countries", filename),
        join(dirname(__file__), "countries", filename),
        join(dirname(__file__), "pics", "webcam.png")
    ]

    # Return the first valid path
    for path in paths_to_check:
        if isfile(path):
            return path

    return paths_to_check[-1]  # Default icon


# Example usage
# country_name = "Germany"
# country_code = get_country_code(country_name)  # Returns 'de'
# flag_path = get_flag_path(country_code)  # Returns .../countries/de.png


class AspectManager:
    """Manages aspect ratio settings for the plugin"""

    def __init__(self):
        try:
            self.init_aspect = self.get_current_aspect()
            print("[INFO] Initial aspect ratio:", self.init_aspect)
        except Exception as e:
            print("[ERROR] Failed to initialize aspect manager:", str(e))
            self.init_aspect = 0  # Fallback

    def get_current_aspect(self):
        """Get current aspect ratio setting"""
        try:
            aspect = AVSwitch().getAspectRatioSetting()
            # Assicurati che sia un intero valido
            return int(aspect) if aspect is not None else 0
        except (ValueError, TypeError, Exception) as e:
            print("[ERROR] Failed to get aspect ratio:", str(e))
            return 0  # Default 4:3

    def set_aspect(self, aspect_ratio):
        """Set aspect ratio based on string (e.g., '16:9', '4:3')"""
        try:
            aspect_map = {
                "4:3": 0,
                "16:9": 1,
                "16:10": 2,
                "auto": 3
            }

            if aspect_ratio in aspect_map:
                new_aspect = aspect_map[aspect_ratio]
                print("[INFO] Setting aspect ratio to:",
                      aspect_ratio, "(", new_aspect, ")")
                AVSwitch().setAspectRatio(new_aspect)
                return True
            else:
                print("[ERROR] Unknown aspect ratio:", aspect_ratio)
                return False

        except Exception as e:
            print("[ERROR] Failed to set aspect ratio:", str(e))
            return False

    def restore_aspect(self):
        """Restore original aspect ratio"""
        try:
            if hasattr(self, 'init_aspect') and self.init_aspect is not None:
                print("[INFO] Restoring aspect ratio to:", self.init_aspect)
                AVSwitch().setAspectRatio(self.init_aspect)
            else:
                print("[WARNING] No initial aspect ratio to restore")
        except Exception as e:
            print("[ERROR] Failed to restore aspect ratio:", str(e))


# Global variable for the current system language
_current_language = get_system_language()


def set_current_language(lang):
    """Set the current system language."""
    global _current_language
    _current_language = lang


def get_current_language():
    """Get the current system language."""
    return _current_language


def check_and_warn_dependencies(logger=None):
    try:
        missing = checkdependencies.check_requirements(logger=logger)
        if missing and logger:
            logger.warning(
                "Missing optional components: %s",
                ", ".join(missing))
        return missing
    except Exception as e:
        if logger:
            logger.error("Error checking dependencies: %s", str(e))
        return []

# =========================================================================
# YouTube / ServiceApp helpers (added for player.py rewrite)
# =========================================================================

SERVICE_MP3        = 4097   # servicemp3 - always available
SERVICE_GSTPLAYER  = 5001   # requires ServiceApp
SERVICE_EXTEPLAYER3 = 5002  # requires ServiceApp


def is_youtube_url(url):
    """Check if URL points to YouTube."""
    if not url or not isinstance(url, str):
        return False
    u = url.lower()
    return ("youtube.com" in u
            or "youtu.be" in u
            or "youtube-nocookie.com" in u)


def convert_youtube_embed_to_watch(url):
    """
    Convert any YouTube URL (embed, nocookie, live, shorts, youtu.be)
    to the canonical https://www.youtube.com/watch?v=ID form.
    Other URLs are returned unchanged.
    """
    if not is_youtube_url(url):
        return url
    # Channel live embed: keep it a channel URL (resolved as /live)
    m = search(r'/embed/live_stream\?(?:.*&)?channel=([^&#]+)', url)
    if m:
        return "https://www.youtube.com/channel/%s/live" % m.group(1)
    patterns = [
        r'(?:youtube-nocookie\.com|youtube\.com)/embed/([^/?#&]+)',
        r'youtube\.com/live/([^/?#&]+)',
        r'youtu\.be/([^/?#&]+)',
        r'youtube\.com/shorts/([^/?#&]+)',
        r'youtube\.com/v/([^/?#&]+)',
    ]
    for pattern in patterns:
        m = search(pattern, url)
        if m:
            return "https://www.youtube.com/watch?v=%s" % m.group(1)
    return url


def has_serviceapp():
    """Check if the ServiceApp system plugin is installed."""
    try:
        return isdir(resolveFilename(
            SCOPE_PLUGINS, "SystemPlugins/ServiceApp"))
    except Exception:
        return False


def get_service_type(preferred=None):
    """
    Return the best eServiceReference type for playback.

    preferred: 'auto' (default), 'exteplayer3', 'gstplayer', 'mp3'.
    exteplayer3/gstplayer need ServiceApp, otherwise 4097 is used.
    """
    if preferred in ("exteplayer3", "gstplayer"):
        if has_serviceapp():
            return (SERVICE_EXTEPLAYER3 if preferred == "exteplayer3"
                    else SERVICE_GSTPLAYER)
        Logger().warning(
            "Player '%s' requires ServiceApp, falling back to 4097"
            % preferred)
    # 4097 by default: with ServiceApp installed, 4097 already follows
    # the player chosen in the ServiceApp settings
    return SERVICE_MP3


def timer_connect(timer, callback):
    """
    Connect an eTimer callback on both DreamOS and OE images.
    The returned connection object (DreamOS) MUST be kept alive by the
    caller, otherwise the callback is disconnected immediately.
    """
    try:
        return timer.timeout.connect(callback)
    except AttributeError:
        timer.callback.append(callback)
        return None
