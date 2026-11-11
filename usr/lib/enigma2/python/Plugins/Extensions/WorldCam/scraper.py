#!/usr/bin/python
# -*- coding: utf-8 -*-

from re import search, escape, findall, DOTALL, IGNORECASE
from os import listdir
from os.path import (
    exists,
    isfile,
    join,
)
import hashlib
from os import makedirs
from threading import Lock

from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from concurrent.futures import ThreadPoolExecutor
import time

from .utils import Logger

# =========================================================================
# Thumbnail support (added for thumbnail-enabled lists)
# =========================================================================
THUMBNAIL_DIR = "/tmp/worldcam_thumbs"
_thumb_lock = Lock()
_active_thumb_downloads = set()


"""
#########################################################
#                                                       #
#  Worldcam Cam Scraper from Plugin                     #
#  Completely rewritten and optimized in version *5.0*  #
#  Version: 5.8                                         #
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

BASE_URL = "https://www.skylinewebcams.com"
STREAM_BASE_URL = "https://hd-auth.skylinewebcams.com"

# Languages available on skylinewebcams.com (others fall back to English)
SKYLINE_LANGUAGES = (
    "en", "it", "es", "de", "fr", "pl", "el", "hr", "sl", "ru", "zh")

# Fetched pages are cached for one hour
CACHE_TTL = 3600

def safe_log_string(text):
    """Safely encode strings for logging"""
    if isinstance(text, bytes):
        return text.decode("utf-8", "replace")
    return text


class SkylineScraper:
    """
    A scraper class for extracting webcam streams and related information
    from skylinewebcams.com, supporting caching and multi-language.
    """
    BASE_URL = "https://www.skylinewebcams.com"
    HEADERS = {"User-Agent": "Mozilla/5.0",
               "Accept-Language": "en-US,en;q=0.5"}

    def __init__(self, lang="en"):
        """
        Initialize scraper with language and setup cache and timer.
        """
        self.logger = Logger()
        self.logger.info("Entering __init__")
        self.lang = lang if lang in SKYLINE_LANGUAGES else "en"
        self.cache = {}

    def clear_cache(self):
        """Clear the internal content cache."""
        self.logger.info("Entering clear_cache")
        self.cache = {}

    def get_full_url(self, path):
        """Return a full absolute URL with proper formatting"""
        if path.startswith("http"):
            return path
        if path.startswith("//"):
            return "https:" + path
        if path.startswith("/"):
            return self.BASE_URL + path
        return self.BASE_URL + "/" + path

    def is_direct_stream(self, url):
        """Check if URL is a direct video stream"""
        video_extensions = [
            '.m3u8', '.mp4', '.m4v', '.flv', '.ts', '.mov', '.mkv']
        url_lower = url.lower()
        return (any(url_lower.endswith(ext) for ext in video_extensions) or
                'm3u8' in url_lower or 'mp4' in url_lower or
                'stream' in url_lower or 'explore.org' in url_lower)

    def get_stream_url(self, webcam_page_url):
        """
        Extract the streaming URL from a webcam page.
        """
        self.logger.info("Entering get_stream_url")
        try:
            lower_url = webcam_page_url.lower()
            if ('youtube.com' in lower_url or 'youtu.be' in lower_url or
                    'youtube-nocookie.com' in lower_url):
                return webcam_page_url

            if self.is_direct_stream(webcam_page_url):
                return webcam_page_url

            if 'explore.org' in webcam_page_url and 'm3u8' in webcam_page_url:
                return webcam_page_url

            content = self.fetch(webcam_page_url, use_cache=False)
            if not content:
                return None

            # NUOVO PATTERN: Accetta sia apici singoli che doppi
            hls_match = search(r"source:\s*[\"']([^\"']+\.m3u8[^\"']*)[\"']", content)
            if hls_match:
                relative_url = hls_match.group(1)
                id_match = search(r"\?a=([^&\"']+)", relative_url)
                if id_match:
                    video_id = id_match.group(1)
                    self.logger.info("Found HLS stream with video ID: " + video_id)
                    return STREAM_BASE_URL + "/live.m3u8?a=" + video_id

            # Fallback per YouTube
            yt_match = search(r"videoId:\s*'([^']+)'", content)
            if yt_match:
                video_id = yt_match.group(1)
                return "https://www.youtube.com/watch?v=" + video_id

            self.logger.warning("No stream URL found in the page: " + webcam_page_url)
        except Exception as e:
            self.logger.error("Error parsing stream URL from {}: {}".format(webcam_page_url, str(e)))
        return None

    def fetch(self, url, use_cache=True):
        """Fetch the content of the URL with enhanced encoding handling"""
        safe_url = str(url)

        if use_cache and safe_url in self.cache:
            fetched, cached = self.cache[safe_url]
            if time.time() - fetched < CACHE_TTL:
                return cached
            del self.cache[safe_url]

        try:
            req = Request(safe_url, headers=self.HEADERS)
            response = urlopen(req, timeout=15)

            if response is None:
                return ""

            content = response.read()
            if not content:
                return ""

            try:
                decoded_content = content.decode("utf-8", errors="replace")
            except Exception:
                try:
                    decoded_content = content.decode("latin-1")
                except BaseException:
                    decoded_content = content.decode("utf-8", errors="ignore")

            if use_cache:
                self.cache[safe_url] = (time.time(), decoded_content)

            return decoded_content

        except (HTTPError, URLError) as e:
            self.logger.error(f"Fetch error: {str(e)}")
        except Exception as e:
            self.logger.error(f"Unexpected error: {str(e)}")

        return ""

    @staticmethod
    def parse_countries(html, language="en"):
        """Extract country links and names from the main page."""
        pattern = r'<a href="/' + escape(language) + r'/webcam/([^/"]+)\.html">([^<]+)</a>'
        try:
            return findall(pattern, html, IGNORECASE)
        except Exception as e:
            Logger().error("Error parsing countries: " + str(e))
            return []

    @staticmethod
    def parse_categories(html, language="en"):
        """Extract main categories from homepage HTML."""
        # NUOVO PATTERN: Cerca i link con class="cam-link" e span class="cam-title"
        pattern = r'<a\s+[^>]*class="[^"]*cam-link[^"]*"[^>]*href="([^"]+)"[^>]*>.*?<span\s+class="cam-title">([^<]+)</span>'
        try:
            return findall(pattern, html, DOTALL)
        except Exception as e:
            Logger().error("Error parsing categories: " + str(e))
            return []

    @staticmethod
    def parse_webcams(html, language="en", base_url="https://www.skylinewebcams.com"):
        """Extract webcams and their thumbnails."""
        webcams = []
        # Regex aggiornata: cerca prima data-src, poi src
        pattern = r'<span class="thumb">.*?<img\s+(?:data-src|src)="([^"]+)"[^>]*>.*?<a\s+class="cam-title"\s+href="([^"]+)"[^>]*>([^<]+)</a>'
        
        matches = findall(pattern, html, DOTALL)
        
        Logger().info(f"[DEBUG PARSER] Lunghezza HTML: {len(html)} caratteri")
        Logger().info(f"[DEBUG PARSER] Webcam trovate dal regex: {len(matches)}")
        
        if not matches:
            Logger().warning("[DEBUG PARSER] NESSUN MATCH! Ecco i primi 1000 caratteri dell'HTML:")
            Logger().warning(html[:1000])

        for match in matches:
            thumbnail = match[0]
            href = match[1]
            name = match[2].strip()

            if "Advertisement" in name or not href:
                continue

            if href.startswith('http'):
                full_url = href
            else:
                full_url = base_url + (href if href.startswith('/') else '/' + href)

            webcams.append({
                "url": full_url,
                "thumbnail": thumbnail,
                "name": name
            })
            
            if len(webcams) == 1:
                Logger().info(f"[DEBUG PARSER] Esempio prima webcam -> Nome: {name}, Thumb: {thumbnail}")

        return webcams

    @staticmethod
    def parse_locations(html, language="en", country_code=None):
        """Extract locations (regions/cities) from a country page."""
        locations = []
        # NUOVO PATTERN: Cerca i link nel nav "chips" o nella lista
        pattern = r'<nav class="chips">.*?</nav>'
        nav_match = search(pattern, html, DOTALL)

        if nav_match:
            nav_html = nav_match.group(0)
            link_pattern = r'<a href="([^"]+)"[^>]*>([^<]+)</a>'
            for href, name in findall(link_pattern, nav_html):
                locations.append((href, name.strip()))
        else:
            # Fallback per il vecchio layout se il nav non c'è
            location_pattern = r'<a href="([^"]+)" class="[^"]*\bbtn\b[^"]*\bbtn-primary\b[^"]*"[^>]*>([^<]+)</a>'
            for href, name in findall(location_pattern, html):
                locations.append((href, name.strip()))

        return locations

    def get_countries(self, category_url=None):
        """Get countries from a category page or homepage."""
        url = category_url or (self.BASE_URL + "/" + self.lang + "/webcam.html")
        html = self.fetch(url)

        countries = []
        seen_urls = set()  # <--- FILTRO DOPPIONI
        try:
            for path, name in self.parse_countries(html, self.lang):
                full_url = f"{self.BASE_URL}/{self.lang}/webcam/{path}.html"
                if full_url not in seen_urls:
                    seen_urls.add(full_url)
                    countries.append({"name": name, "url": full_url})
        except Exception as e:
            self.logger.error("Error in get_countries: " + str(e))
        return countries

    def get_categories(self):
        """Get main categories from categories page."""
        url = f"{self.BASE_URL}/{self.lang}/categories.html"
        html = self.fetch(url)

        categories = []
        try:
            for path, name in self.parse_categories(html, self.lang):
                full_url = self.get_full_url(path)
                categories.append({"name": name, "url": full_url})
        except Exception as e:
            self.logger.error("Error in get_categories: " + str(e))
        return categories

    def get_top_webcams(self):
        """Get featured webcams from the homepage."""
        url = f"{self.BASE_URL}/{self.lang}/top-live-cams.html"
        html = self.fetch(url)
        if not html:
            return []
        try:
            webcams = self.parse_webcams(html, self.lang, self.BASE_URL)
            return [w for w in webcams if w.get("name") and w.get("url") and "Advertisement" not in w["name"]]
        except Exception as e:
            self.logger.error("Error in get_top_webcams: " + str(e))
            return []

    def get_locations(self, country_url=None):
        """Fetch and parse the list of locations for a given country URL."""
        content = self.fetch(country_url)
        locations = []
        location_data = self.parse_locations(content, self.lang)

        for url, name in location_data:
            full_url = self.get_full_url(url)
            locations.append({"name": name, "url": full_url})

        return locations

    def get_webcams(self, page_url=None):
        """Ottiene le webcam per una pagina usando il nuovo parser robusto"""
        html = self.fetch(page_url)
        if not html:
            return []
        return self.parse_webcams(html, self.lang, self.BASE_URL)

    def get_local_playlists(self, playlists_path=None):
        """Return list of filenames in playlists directory including M3U files."""
        user_lists = []
        if not exists(playlists_path):
            return user_lists
        try:
            for filename in listdir(playlists_path):
                full_path = join(playlists_path, filename)
                if isfile(full_path):
                    ext = filename.lower().split('.')[-1]
                    if ext in ('txt', 'm3u', 'm3u8', 'list'):
                        user_lists.append(filename)
            return user_lists
        except Exception as e:
            self.logger.error(f"Error reading playlists directory: {str(e)}")
            return user_lists

    def parse_local_playlist_file(self, path):
        """Legge le liste utente locali (txt) separate da :::, ;;, ###, ::, ;"""
        webcams = []
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"): 
                        continue
                    
                    # Trova il delimitatore corretto
                    for delim in (":::", ";;", "###", "::", ";"):
                        if delim in line:
                            parts = line.split(delim, 1)
                            name = parts[0].strip()
                            url = parts[1].strip()
                            if url:
                                webcams.append({"name": name, "url": url, "thumbnail": ""})
                            break
        except Exception as e:
            self.logger.error(f"Error parsing local playlist {path}: {e}")
        return webcams

    def get_continents(self):
        """Estrae i continenti e i loro paesi dal file JSON locale"""
        import json
        from os.path import dirname, join
        continents = []
        try:
            json_path = join(dirname(__file__), "cowntry_code.json")
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            groups = data.get("continent_groups", {})
            for cont_name, countries_dict in groups.items():
                c_list = []
                for c_name, c_code in countries_dict.items():
                    c_url = f"{self.BASE_URL}/{self.lang}/webcam/{c_code}.html"
                    c_list.append({"name": c_name, "url": c_url})
                continents.append({"name": cont_name, "countries": c_list})
        except Exception as e:
            self.logger.error(f"Error loading continents: {e}")
            
        return sorted(continents, key=lambda x: x["name"])


def _normalize_thumbnail_url(url):
    if not url:
        return None
    url = url.strip()
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/"):
        return "https://www.skylinewebcams.com" + url
    if not url.startswith(("http://", "https://")):
        return "https://cdn.skylinewebcams.com/" + url.lstrip("/")
    return url


def webp_to_jpg_url(thumbnail_url):
    url = _normalize_thumbnail_url(thumbnail_url)
    if not url:
        return None
    if url.lower().endswith(".webp"):
        url = url[:-5]  # rimuove .webp
        # Sostituisce 'live' con 'social' (es. live522.webp -> social522.jpg)
        url = url.replace("live", "social")
        url = url + ".jpg"
    return url


def _get_thumbnail_info(thumbnail_url):
    jpg_url = webp_to_jpg_url(thumbnail_url)
    if not jpg_url:
        return None, None
    url_hash = hashlib.md5(jpg_url.encode("utf-8")).hexdigest()
    local_path = join(THUMBNAIL_DIR, url_hash + ".jpg")
    return local_path, jpg_url


def get_thumbnail_path(thumbnail_url):
    local_path, _ = _get_thumbnail_info(thumbnail_url)
    if local_path and exists(local_path) and isfile(local_path):
        return local_path
    return None


def download_thumbnail(thumbnail_url):
    """Download a thumbnail to THUMBNAIL_DIR."""
    local_path, jpg_url = _get_thumbnail_info(thumbnail_url)
    if not local_path:
        return None

    if exists(local_path) and isfile(local_path):
        try:
            with open(local_path, "rb") as f:
                if f.read(4).startswith((b'\xff\xd8', b'\x89PNG')):
                    return local_path
        except Exception:
            pass

    with _thumb_lock:
        if jpg_url in _active_thumb_downloads:
            return None
        _active_thumb_downloads.add(jpg_url)

    try:
        makedirs(THUMBNAIL_DIR, exist_ok=True)
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://www.skylinewebcams.com/",
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8"
        }

        try:
            import requests
            resp = requests.get(jpg_url, headers=headers, timeout=10)
            data = resp.content
        except ImportError:
            req = Request(jpg_url, headers=headers)
            data = urlopen(req, timeout=10).read()

        if not data or not (data.startswith(b'\xff\xd8') or data.startswith(b'\x89PNG')):
            return None

        with open(local_path, "wb") as f:
            f.write(data)
        return local_path
    except Exception:
        return None
    finally:
        with _thumb_lock:
            _active_thumb_downloads.discard(jpg_url)

def download_all_thumbnails(urls):
    """Scarica tutte le anteprime in parallelo (10 alla volta)."""
    with ThreadPoolExecutor(max_workers=10) as executor:
        list(executor.map(download_thumbnail, urls))
