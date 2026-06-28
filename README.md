<h1 align="center">🌍 You WorldCam Plugin</h1>

[![Version](https://img.shields.io/badge/Version-6.8-blue.svg)](https://github.com/Belfagor2005/WorldCam)
[![Enigma2](https://img.shields.io/badge/Enigma2-Plugin-ff6600.svg)](https://www.enigma2.net)
[![Python](https://img.shields.io/badge/Python-3-blue.svg)](https://www.python.org)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python package](https://github.com/OwnerPlugins/WorldCam/actions/workflows/pylint.yml/badge.svg)](https://github.com/OwnerPlugins/WorldCam/actions/workflows/pylint.yml)
[![Ruff Status](https://github.com/OwnerPlugins/WorldCam/actions/workflows/ruff.yml/badge.svg)](https://github.com/OwnerPlugins/WorldCam/actions/workflows/ruff.yml)

[![Visitors](https://komarev.com/ghpvc/?username=Belfagor2005&label=Repository%20Views&color=blueviolet)](https://github.com/Belfagor2005)
[![Donate](https://img.shields.io/badge/_-Donate-red.svg?logo=githubsponsors&labelColor=555555&style=for-the-badge)](https://ko-fi.com/lululla)
[![Donate](https://img.shields.io/badge/_-Donate-green.svg?logo=githubsponsors&labelColor=555555&style=for-the-badge)](https://paypal.me/belfagor2005)

**WorldCam** is an Enigma2 plugin that allows you to view live webcams from around the world,  
with a simple, fast, and stable interface.  
Completely rewritten and optimized in version **6.0**,  
the plugin now offers new features and greater reliability.

---

🚀 **What's new from version > 5.0**

⚡️ **Fast and interactive UI management**
Asynchronous webcam loading and smooth navigation between categories.

🇺🇳 **Dynamic flag icons for language/country**
Automatic mapping based on system language or country name.

✅ **New integrated player**
Direct support for HLS streams (.m3u8), YouTube streaming, and two fallback options where available.

🔎 **Fully revamped SkylineWebcams scraper**
Faster and fully compatible with recent site updates.

🛠️ **Advanced console + file logger**
Supports INFO, DEBUG, ERROR, CRITICAL levels, with color-coded terminal output and persistent logs in `/tmp/worldcam/worldcam.log`.

🧹 **Safe screen cleanup and management**
Automatic memory cleanup to prevent leaks or crashes.

🔁 **Integrated aspect ratio handling**
Stores and restores the correct aspect ratio for each video stream.

📁 **Favorites list now available**
You can now manage your favorite webcams from the main menu.
While watching a webcam, just press the **Blue button** to add or remove it from your **Favorites**.

🟩 **Favorites toggle shortcut (Green button)**  
Quickly add or remove the selected webcam from your favorites list while browsing.

🟨 **One-click Favorites to Bouquet export (Yellow button)**  
Instantly export your favorite webcams into a channel bouquet without opening menus.

▶️ **Next/Previous webcam navigation in player**  
You can now switch between webcams directly from the player using ch+/ch- arrows.

🧩 **Guaranteed compatibility from Python 2.7 to 3.9+**
Safe use of cross-version libraries and methods, with automatic fallbacks.

---

## 🎥 YouTube Player Support

The WorldCam plugin supports playing YouTube streams with three fallback mechanisms to ensure smooth playback:

1. **Direct playback using yt\_dlp and eServiceReference**
   The plugin tries to play YouTube videos directly by extracting the stream URL with yt\_dlp.

This ensures maximum compatibility and reliability for YouTube streams.

---

# 📋 Local List Format for WorldCam

WorldCam supports loading a local list file containing webcam entries.  
Each line in the list must contain the **name** and the **stream URL** of the webcam,  
separated by one of the following delimiters:

* 🔹 `:::` (triple colon)  
* 🔹 `;;` (double semicolon)  
* 🔹 `###` (triple hash)  
* 🔹 `::` (double colon)  
* 🔹 `;` (semicolon)  

### 📝 Example lines:

```

Camera 1:::[http://example.com/stream1.m3u8](http://example.com/stream1.m3u8)
My Cam;;[http://example.com/stream2.m3u8](http://example.com/stream2.m3u8)
Another Cam###[http://example.com/stream3.m3u8](http://example.com/stream3.m3u8)
Cam Name::[http://example.com/stream4.m3u8](http://example.com/stream4.m3u8)
SimpleCam;[http://example.com/stream5.m3u8](http://example.com/stream5.m3u8)
YouTube Cam;[https://www.youtube.com/watch?v=dQw4w9WgXcQ](https://www.youtube.com/watch?v=dQw4w9WgXcQ)
SimpleCam###http://example.com/stream5.m3u8](http://example.com/stream5.m3u8
YouTube Cam###https://www.youtube.com/watch?v=dQw4w9WgXcQ](https://www.youtube.com/watch?v=dQw4w9WgXc
```

---

## 🎥 YouTube streams in Local List

YouTube URLs can be included directly in the local list as valid webcam entries.  
The plugin will automatically detect YouTube links and use its internal player fallback to stream them.

---

## 📂 Where to put the local list file?

Place your local list file (for example, named `worldcam_list.txt`) inside the following folder:

```
/usr/lib/enigma2/python/Plugins/Extensions/WorldCam/Playlist/
```

---

## ⚙️ Requirements
- Enigma2 STB (Dreambox, Vu+, Zgemma, etc.)  
- Active internet connection  
- Python ≥ 3.0
---

## 🧪 Debug & Log
Logs are saved at:  

```
/tmp/worldcam/worldcam.log
```

You can check internal events and requested video streams directly.  
If errors or malfunctions occur, please send this file for support.
---

## 📌 Notes

- This plugin is released under the **CC BY-NC-SA 4.0** license  
- Redistribution without attribution is not allowed  
- The plugin **does not use external extensions** or complicated dependencies  
- Any code modification must keep the original header intact

---

## 🙏 Credits

- Original project: **Lululla**  
- Stream source: [SkylineWebcams.com](https://www.skylinewebcams.com)  
- Graphic support: Public flags and icons

---
```

