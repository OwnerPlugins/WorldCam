#!/usr/bin/python
# -*- coding: utf-8 -*-

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

import time
import hashlib
import json
from os import listdir, makedirs, remove
from os.path import exists, isfile, join, dirname
from re import search, escape, findall, DOTALL, IGNORECASE
from threading import Lock
from concurrent.futures import ThreadPoolExecutor
from subprocess import run, DEVNULL
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .utils import Logger

THUMBNAIL_DIR = "/tmp/worldcam_thumbs"
_thumb_lock = Lock()
_active_thumb_downloads = set()

BASE_URL = "https://www.skylinewebcams.com"
STREAM_BASE_URL = "https://hd-auth.skylinewebcams.com"

SKYLINE_LANGUAGES = (
    "en", "it", "es", "de", "fr", "pl", "el", "hr", "sl", "ru", "zh")
CACHE_TTL = 3600

def is_direct_stream(url):
    video_extensions = ['.m3u8', '.mp4', '.m4v', '.flv', '.ts', '.mov', '.mkv']
    url_lower = url.lower()
    return (any(url_lower.endswith(ext) for ext in video_extensions) or
            'm3u8' in url_lower or 'mp4' in url_lower or
            'stream' in url_lower or 'explore.org' in url_lower)

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
        url = url[:-5]
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
    if local_path:
        png_path = local_path.replace(".jpg", ".png")
        if exists(png_path) and isfile(png_path):
            return png_path
        if exists(local_path) and isfile(local_path):
            return local_path
    return None

def download_thumbnail(thumbnail_url):
    local_path, jpg_url = _get_thumbnail_info(thumbnail_url)
    if not local_path:
        return None

    png_path = local_path.replace(".jpg", ".png")

    if exists(png_path) and isfile(png_path):
        return png_path

    if exists(local_path) and isfile(local_path):
        try: remove(local_path)
        except Exception: pass

    with _thumb_lock:
        if jpg_url in _active_thumb_downloads:
            return None
        _active_thumb_downloads.add(jpg_url)

    try:
        makedirs(THUMBNAIL_DIR, exist_ok=True)
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; SM-G960F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
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
        
        # Master Format 160x90 con Padding Nero per non deformare l'immagine
        try:
            run([
                "ffmpeg", "-y", "-i", local_path, 
                "-vf", "scale=160:90:force_original_aspect_ratio=decrease,pad=160:90:(ow-iw)/2:(oh-ih)/2:black",
                png_path
            ], stdout=DEVNULL, stderr=DEVNULL, timeout=5)
            
            if exists(png_path):
                remove(local_path)
                return png_path
        except Exception:
            pass
            
        return local_path
    except Exception:
        return None
    finally:
        with _thumb_lock:
            _active_thumb_downloads.discard(jpg_url)


def download_all_thumbnails(urls):
    with ThreadPoolExecutor(max_workers=10) as executor:
        list(executor.map(download_thumbnail, urls))


class SkylineScraper:
    BASE_URL = "https://www.skylinewebcams.com"
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; SM-G960F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
        "Accept-Language": "en-US,en;q=0.5"
    }

    def __init__(self, lang="en"):
        self.logger = Logger()
        self.lang = lang if lang in SKYLINE_LANGUAGES else "en"
        self.cache = {}

    def clear_cache(self):
        self.cache = {}

    def get_full_url(self, path):
        if path.startswith("http"): return path
        if path.startswith("//"): return "https:" + path
        if path.startswith("/"): return self.BASE_URL + path
        return self.BASE_URL + "/" + path

    def get_stream_url(self, webcam_page_url):
        try:
            lower_url = webcam_page_url.lower()
            if ('youtube.com' in lower_url or 'youtu.be' in lower_url):
                return webcam_page_url
            if is_direct_stream(webcam_page_url):
                return webcam_page_url

            content = self.fetch(webcam_page_url, use_cache=False)
            if not content: return None

            hls_match = search(r'(?:url|source)\s*:\s*[\'"]([^\'"]+\.m3u8[^\'"]*)[\'"]', content)
            if hls_match:
                relative_url = hls_match.group(1)
                id_match = search(r"\?a=([^&\"']+)", relative_url)
                if id_match:
                    return STREAM_BASE_URL + "/live.m3u8?a=" + id_match.group(1)
                elif relative_url.startswith("http"):
                    return relative_url

            yt_match = search(r'videoId\s*:\s*[\'"]([^\'"]+)[\'"]', content)
            if yt_match:
                return "https://www.youtube.com/watch?v=" + yt_match.group(1)
        except Exception as e:
            self.logger.error(f"Error parsing stream URL from {webcam_page_url}: {str(e)}")
        return None

    def fetch(self, url, use_cache=True):
        safe_url = str(url)
        if use_cache and safe_url in self.cache:
            fetched, cached = self.cache[safe_url]
            if time.time() - fetched < CACHE_TTL: return cached
            del self.cache[safe_url]
        try:
            req = Request(safe_url, headers=self.HEADERS)
            response = urlopen(req, timeout=15)
            if response is None: return ""
            content = response.read()
            if not content: return ""
            try:
                decoded_content = content.decode("utf-8", errors="replace")
            except Exception:
                try: decoded_content = content.decode("latin-1")
                except BaseException: decoded_content = content.decode("utf-8", errors="ignore")
            if use_cache: self.cache[safe_url] = (time.time(), decoded_content)
            return decoded_content
        except (HTTPError, URLError) as e:
            self.logger.error(f"Fetch error: {str(e)}")
        except Exception as e:
            self.logger.error(f"Unexpected error: {str(e)}")
        return ""

    @staticmethod
    def parse_countries(html, language="en"):
        pattern = r'<a href="/' + escape(language) + r'/webcam/([^/"]+)\.html">([^<]+)</a>'
        try: return findall(pattern, html, IGNORECASE)
        except Exception as e:
            Logger().error("Error parsing countries: " + str(e))
            return []

    @staticmethod
    def parse_categories(html, language="en"):
        pattern = r'<a\s+[^>]*class="[^"]*cam-link[^"]*"[^>]*href="([^"]+)"[^>]*>.*?<span\s+class="cam-title">([^<]+)</span>'
        try: return findall(pattern, html, DOTALL)
        except Exception as e:
            Logger().error("Error parsing categories: " + str(e))
            return []

    @staticmethod
    def parse_webcams(html, language="en", base_url="https://www.skylinewebcams.com"):
        webcams = []
        pattern = r'<span class="thumb">.*?<img\s+(?:data-src|src)="([^"]+)"[^>]*>.*?<a\s+class="cam-title"\s+href="([^"]+)"[^>]*>([^<]+)</a>'
        matches = findall(pattern, html, DOTALL)
        for match in matches:
            thumbnail, href, name = match[0], match[1], match[2].strip()
            if "Advertisement" in name or not href: continue
            full_url = href if href.startswith('http') else base_url + (href if href.startswith('/') else '/' + href)
            webcams.append({"url": full_url, "thumbnail": thumbnail, "name": name})
        return webcams

    @staticmethod
    def parse_locations(html, language="en", country_slug=None):
        locations = []
        if not country_slug: return locations
        pattern = r'<a\s+[^>]*href="(/' + escape(language) + r'/webcam/' + escape(country_slug) + r'/([^/"]+)(?:\.html)?)"[^>]*>([^<]+)</a>'
        matches = findall(pattern, html, IGNORECASE | DOTALL)
        seen_urls = set()
        for full_path, sub_slug, name in matches:
            if not sub_slug or sub_slug == country_slug: continue
            full_url = f"https://www.skylinewebcams.com{full_path}"
            if not full_url.endswith(".html"): full_url += ".html"
            if full_url not in seen_urls:
                seen_urls.add(full_url)
                locations.append((full_url, name.strip()))
        return locations

    def get_countries(self, category_url=None):
        url = category_url or (self.BASE_URL + "/" + self.lang + "/webcam.html")
        html = self.fetch(url)
        countries, seen_urls = [], set()
        try:
            for path, name in self.parse_countries(html, self.lang):
                full_url = f"{self.BASE_URL}/{self.lang}/webcam/{path}.html"
                if full_url not in seen_urls:
                    seen_urls.add(full_url)
                    countries.append({"name": name, "url": full_url})
        except Exception as e: self.logger.error("Error in get_countries: " + str(e))
        return countries

    def get_categories(self):
        url = f"{self.BASE_URL}/{self.lang}/categories.html"
        html = self.fetch(url)
        categories = []
        try:
            for path, name in self.parse_categories(html, self.lang):
                categories.append({"name": name, "url": self.get_full_url(path)})
        except Exception as e: self.logger.error("Error in get_categories: " + str(e))
        return categories

    def get_top_webcams(self):
        url = f"{self.BASE_URL}/{self.lang}/top-live-cams.html"
        html = self.fetch(url)
        if not html: return []
        try:
            webcams = self.parse_webcams(html, self.lang, self.BASE_URL)
            return [w for w in webcams if w.get("name") and w.get("url") and "Advertisement" not in w["name"]]
        except Exception as e:
            self.logger.error("Error in get_top_webcams: " + str(e))
            return []

    def get_locations(self, country_url=None):
        content = self.fetch(country_url)
        slug_match = search(r'/webcam/([^/]+)\.html', country_url)
        country_slug = slug_match.group(1) if slug_match else None
        location_data = self.parse_locations(content, self.lang, country_slug)
        return [{"name": name, "url": url} for url, name in location_data]

    def get_webcams(self, page_url=None):
        html = self.fetch(page_url)
        if not html: return []
        return self.parse_webcams(html, self.lang, self.BASE_URL)

    def get_local_playlists(self, playlists_path=None):
        user_lists = []
        if not exists(playlists_path): return user_lists
        try:
            for filename in listdir(playlists_path):
                full_path = join(playlists_path, filename)
                if isfile(full_path) and filename.lower().split('.')[-1] in ('txt', 'm3u', 'm3u8', 'list'):
                    user_lists.append(filename)
            return user_lists
        except Exception as e:
            self.logger.error(f"Error reading playlists directory: {str(e)}")
            return user_lists

    def parse_local_playlist_file(self, path):
        webcams = []
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"): continue
                    for delim in (":::", ";;", "###", "::", ";"):
                        if delim in line:
                            parts = line.split(delim, 1)
                            if len(parts) == 2 and parts[1].strip():
                                webcams.append({"name": parts[0].strip(), "url": parts[1].strip(), "thumbnail": ""})
                            break
        except Exception as e:
            self.logger.error(f"Error parsing local playlist {path}: {e}")
        return webcams

    def get_continents(self):
        url = f"{self.BASE_URL}/{self.lang}/webcam.html"
        html = self.fetch(url)
        continents = []
        if not html: return continents
        pattern = r'<div class="[^"]*menu[^"]*">\s*<h2 class="menu-nm">([^<]+)</h2>\s*<div class="menu-list">(.*?)</div>'
        matches = findall(pattern, html, DOTALL)
        for cont_name, links_html in matches:
            c_list = []
            for href, name in findall(r'<a href="([^"]+)">([^<]+)</a>', links_html):
                c_list.append({"name": name.strip(), "url": self.get_full_url(href)})
            if c_list:
                continents.append({"name": cont_name.strip(), "countries": c_list})
        return sorted(continents, key=lambda x: x["name"])
