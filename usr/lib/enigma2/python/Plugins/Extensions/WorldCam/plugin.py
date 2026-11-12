#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
#########################################################
#                                                       #
#  Worldcam Player from Web Plugin                      #
#  Completely rewritten and optimized in version *5.0*  #
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
from os import makedirs
from os.path import exists, join, splitext, getsize
from re import findall
from urllib.request import Request, urlopen

from enigma import (
    RT_HALIGN_LEFT,
    RT_VALIGN_CENTER,
    eListboxPythonMultiContent,
    eTimer,
    gFont,
    getDesktop,
    loadPNG,
)
from Tools.LoadPixmap import LoadPixmap

from Components.ActionMap import HelpableActionMap
from Components.Button import Button
from Components.Label import Label
from Components.MenuList import MenuList
from Components.MultiContent import MultiContentEntryPixmapAlphaTest, MultiContentEntryText
from Components.Pixmap import Pixmap
from Screens.ChoiceBox import ChoiceBox
from Screens.Console import Console
from Screens.MessageBox import MessageBox
from Screens.Screen import Screen

from . import (
    _, AgentRequest, installer_url, paypal, PLUGIN_VERSION, PLUGIN_PATH, DEFAULT_ICON
)
from .player import WorldCamPlayer
from .scraper import (
    SKYLINE_LANGUAGES, SkylineScraper, get_thumbnail_path, download_all_thumbnails
)
from .utils import (
    CATEGORY_ICONS, FavoritesManager, Logger, b64decoder, disable_summary, get_category_icon,
    get_country_code, get_current_language, get_flag_path, get_system_language,
    language_flag_mapping, set_current_language, timer_connect,
)

logger = Logger()
current_language = get_system_language()
if current_language not in SKYLINE_LANGUAGES:
    current_language = "en"
set_current_language(current_language)
screen_width = getDesktop(0).size().width()

if screen_width == 2560:
    ROW_HEIGHT_THUMB = 130
elif screen_width == 1920:
    ROW_HEIGHT_THUMB = 110
else:
    ROW_HEIGHT_THUMB = 90

_failed_thumbs = set()

def version_tuple(version):
    return tuple(int(x) for x in findall(r"\d+", str(version)))

class WebcamList(MenuList):
    def __init__(self, items):
        MenuList.__init__(self, items, True, eListboxPythonMultiContent)
        self.currsel = -1
        self.currpos = 0
        font_size = 46 if screen_width == 2560 else (40 if screen_width == 1920 else 28)
        self.l.setFont(0, gFont("Regular", font_size))
        self.l.setItemHeight(ROW_HEIGHT_THUMB)

    def setCurrentIndex(self, idx):
        if 0 <= idx < len(self.list):
            self.currsel = idx
            self.currpos = idx
            self.instance.moveSelectionTo(idx)
    def getCurrentIndex(self): return self.instance.getCurrentIndex()
    def getSelectionIndex(self): return self.currsel
    def setCurrentPosition(self, pos):
        self.currpos = pos
        self.instance.moveSelectionTo(pos)
    def getCurrentPosition(self): return self.currpos
    def destroy(self):
        self.lang = None
        if hasattr(self, "cams"): del self.cams
        if hasattr(self, "items"): del self.items

def wcListEntry(name, idx, image_path=None, is_webcam=False):
    res = [name]
    
    # Dimensioni del testo
    if screen_width == 2560:
        text_pos, text_size = (215, 0), (1000, ROW_HEIGHT_THUMB)
    elif screen_width == 1920:
        text_pos, text_size = (185, 0), (690, ROW_HEIGHT_THUMB)
    else:
        text_pos, text_size = (140, 0), (470, ROW_HEIGHT_THUMB)

    png = None
    if image_path and exists(image_path) and idx < 250:
        try: png = LoadPixmap(image_path)
        except Exception: png = None
    
    if not png:
        try: png = LoadPixmap(DEFAULT_ICON)
        except Exception: png = None

    if png:
        if is_webcam:
            # Le webcam usano il formato orizzontale grande (160x90 a 1920)
            if screen_width == 2560:
                size = (192, 108)
            elif screen_width == 1920:
                size = (160, 90)
            else:
                size = (120, 70)
            pos = (10, (ROW_HEIGHT_THUMB - size[1]) // 2)
        else:
            # Le bandiere/icone usano ESATTAMENTE il tuo formato 120x70
            if screen_width == 2560:
                size = (180, 105) # Proporzionale per UHD
            elif screen_width == 1920:
                size = (120, 70)  # La tua dimensione esatta
            else:
                size = (100, 58)  # Proporzionale per HD
            pos = (10, (ROW_HEIGHT_THUMB - size[1]) // 2)
            
        res.append(MultiContentEntryPixmapAlphaTest(pos=pos, size=size, png=png))
    
    res.append(MultiContentEntryText(pos=text_pos, size=text_size, font=0, text=name, color=0xA6D1FE, flags=RT_HALIGN_LEFT | RT_VALIGN_CENTER))
    return res

def showlist(data, list_widget, _retry=False):
    current_idx = 0
    try: current_idx = list_widget.getCurrentIndex()
    except Exception: pass

    try: list_widget.l.setItemHeight(ROW_HEIGHT_THUMB)
    except Exception: pass

    plist = []
    pending_thumbs = []

    for idx, item in enumerate(data):
        name = item.get("name", "") if isinstance(item, dict) else item
        icon = item.get("icon") if isinstance(item, dict) else None
        thumbnail = item.get("thumbnail") if isinstance(item, dict) else None

        # Capisce se è una webcam o un'icona generica
        is_webcam = thumbnail is not None

        image_path = None
        if thumbnail:
            image_path = get_thumbnail_path(thumbnail)
            if image_path is None and thumbnail not in _failed_thumbs and idx < 50:
                pending_thumbs.append(thumbnail)
        elif icon:
            image_path = icon if icon.startswith("/") else get_category_icon(icon)
        else:
            country_code = get_country_code(name)
            if country_code: image_path = get_flag_path(country_code)
            else: image_path = DEFAULT_ICON

        plist.append(wcListEntry(name, idx, image_path=image_path, is_webcam=is_webcam))

    try: list_widget.l.setList([])
    except Exception: pass

    try:
        list_widget.setList(plist)
        if hasattr(list_widget, "instance"):
            list_widget.instance.invalidate()
    except Exception:
        if hasattr(list_widget, "l") and hasattr(list_widget.l, "setList"):
            list_widget.l.setList(plist)

    if _retry and 0 < current_idx < len(plist):
        try: list_widget.setCurrentIndex(current_idx)
        except Exception: pass

    if pending_thumbs and not _retry:
        def on_done(_res=None):
            if not list_widget or not hasattr(list_widget, "instance"): return
            try: showlist(data, list_widget, _retry=True)
            except Exception: pass

        from twisted.internet import threads
        d = threads.deferToThread(download_all_thumbnails, pending_thumbs)
        d.addCallback(on_done)
        d.addErrback(lambda _f: None)


class WebcamBaseScreen(Screen):
    def __init__(self, session, lang=None):
        Screen.__init__(self, session)
        self.logger = Logger()
        self.session = session
        self.lang = lang or get_current_language()
        self.skin_path = self.get_skin_path()
        self.skin = self.load_skin()
        self["list"] = WebcamList([])
        self.screen_closed = False
        self._async_title = None
        self.onClose.append(self._mark_closed)

    def _mark_closed(self): self.screen_closed = True

    def run_async(self, func, callback, title=None):
        self._async_title = title
        if title is not None and "title" in self: self["title"].setText(_("Loading..."))
        from twisted.internet import threads
        d = threads.deferToThread(func)
        d.addCallback(self._async_done, callback)
        d.addErrback(self._async_failed, callback)

    def _async_done(self, result, callback):
        if self.screen_closed: return
        if self._async_title is not None and "title" in self: self["title"].setText(self._async_title)
        callback(result)

    def _async_failed(self, failure, callback):
        self.logger.error("Loading error: %s" % failure.getErrorMessage())
        self._async_done(None, callback)

    def get_skin_path(self):
        if screen_width == 2560: return join(PLUGIN_PATH, "skin/uhd")
        elif screen_width == 1920: return join(PLUGIN_PATH, "skin/fhd")
        return join(PLUGIN_PATH, "skin/hd")

    def load_skin(self):
        skin_file = "WorldCamMainScreen.xml"
        skin_path = join(self.skin_path, skin_file)
        try:
            with open(skin_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            self.logger.error(f"Skin loading error: {str(e)}")
            # FALLBACK SKIN: Se il file XML manca, usa questo layout di emergenza
            return """
            <screen name="WorldCamMainScreen" position="center,center" size="900,650" title="WorldCam" flags="wfNoBorder">
                <widget name="title" position="10,10" size="880,40" font="Regular;30" halign="center" transparent="1" />
                <widget name="list" position="10,60" size="880,520" scrollbarMode="showOnDemand" />
                <widget name="key_red" position="10,590" size="200,40" font="Regular;20" halign="center" transparent="1" />
                <widget name="key_green" position="230,590" size="200,40" font="Regular;20" halign="center" transparent="1" />
                <widget name="key_yellow" position="450,590" size="200,40" font="Regular;20" halign="center" transparent="1" />
                <widget name="key_blue" position="670,590" size="200,40" font="Regular;20" halign="center" transparent="1" />
            </screen>
            """

    def set_flag_icon(self):
        if "flag_icon" in self:
            flag_path = get_flag_path(self.lang)
            if exists(flag_path):
                pixmap = loadPNG(flag_path)
                if pixmap: self["flag_icon"].instance.setPixmap(pixmap)

    def get_flag_icon(self): return get_flag_path(self.lang)


class WorldCamMainScreen(WebcamBaseScreen):
    def __init__(self, session, lang=None):
        super().__init__(session, lang)
        disable_summary(self)
        self.logger.info("Initializing WorldCamMainScreen")
        self["flag_icon"] = Pixmap()
        self["language_label"] = Label(self.lang.upper())
        self["paypal"] = Label(paypal())
        self["title"] = Label(_("WorldCam v{}").format(PLUGIN_VERSION))
        self["key_red"] = Button(_("Exit"))
        self["key_green"] = Button(_("Select"))
        self["key_yellow"] = Button(_("Update"))
        self["key_blue"] = Button(_("Menu"))
        self.Update = False
        self.new_version = ""
        self.new_changelog = ""
        self.categories = [
            {"key": "user_lists", "name": _("User Lists"), "icon": "user_lists.png", "screen": WorldCamLocalScreen},
            {"key": "favorites", "name": _("Favorites"), "icon": "favorite.png", "screen": WorldCamFavoritesScreen},
            {"key": "continents", "name": _("Continents"), "icon": "continents.png", "screen": WorldCamContinentScreen},
            {"key": "countries", "name": _("Countries"), "icon": "countries.png", "screen": WorldCamCountryScreen},
            {"key": "categories", "name": _("Categories"), "icon": "categories.png", "screen": WorldCamCategoryScreen},
            {"key": "top_webcams", "name": _("Top Webcams"), "icon": "top_webcams.png", "screen": WorldCamTopScreen},
        ]

        self["actions"] = HelpableActionMap(self, "WorldCamActions", {
            "ok": self.on_item_selected, "cancel": self.close, "red": self.close,
            "green": self.on_item_selected, "yellow": self.update_plugin,
            "blue": self.open_menu, "menu": self.open_menu, "about": self.open_about_direct
        })
        self.timer = eTimer()
        self.timer_conn = timer_connect(self.timer, self.check_update_silent)
        self.timer.start(500, 1)
        self.onLayoutFinish.append(self.initialize)
        self.onLayoutFinish.append(self.set_flag_icon)

    def initialize(self):
        try:
            showlist(self.categories, self["list"])
            if self.categories:
                self["list"].setCurrentIndex(0)
                self.setCurrentSelection(0)
        except Exception as e: self.logger.error("Error during initialize: %s" % str(e))

    def setCurrentSelection(self, index):
        if index < 0 or index >= len(self["list"].list): return
        self["list"].setCurrentIndex(index)
        self["list"].instance.moveSelectionTo(index)
        self.currsel = index

    def on_item_selected(self):
        try:
            index = self["list"].getCurrentIndex()
            if index is None or index < 0 or index >= len(self.categories):
                index = getattr(self, "currsel", 0)
            if 0 <= index < len(self.categories):
                self.session.open(self.categories[index]["screen"], lang=self.lang)
        except Exception as e: self.logger.error("CRITICAL ERROR: %s" % str(e))

    def open_menu(self, result=None):
        try:
            self.menu_items = [(_("Change language"), self.change_language), (_("Update plugin"), self.update_plugin), (_("Settings"), self.open_settings), (_("About"), self.open_about)]
            choices = [(label, index) for index, (label, _) in enumerate(self.menu_items)]
            self.current_menu = self.session.openWithCallback(self.menu_callback, ChoiceBox, title=_("Select an option"), list=choices)
        except Exception as e: self.logger.error("Error opening menu: %s" % str(e))

    def menu_callback(self, selection):
        try:
            if selection is not None:
                index = selection[1]
                label, callback = self.menu_items[index]
                if callable(callback):
                    self.current_menu = None
                    callback()
        except Exception as e: self.logger.error("Exception during menu callback: %s" % str(e))

    def change_language(self):
        try:
            from .LanguageScreen import LanguageScreen
            self.session.openWithCallback(self.on_language_selected, LanguageScreen, self.lang, dict((code, flag) for code, flag in language_flag_mapping.items() if code in SKYLINE_LANGUAGES))
        except Exception as e: self.logger.error(f"Language screen error: {str(e)}"); self.open_menu()

    def on_language_selected(self, new_lang):
        if new_lang is None: return
        try:
            set_current_language(new_lang)
            self.lang = new_lang
            self["language_label"].setText(self.get_english_name(self.lang))
            self.set_flag_icon()
            self.initialize()
            self.show_message(_("Language changed to %s") % self.get_english_name(new_lang), timeout=3)
        except Exception as e: self.logger.error(f"Error changing language: {str(e)}")

    def get_english_name(self, code):
        english_names = {"en": "English", "it": "Italian", "ar": "Arabic", "bg": "Bulgarian", "cs": "Czech", "de": "German", "el": "Greek", "es": "Spanish", "fa": "Persian", "fr": "French", "he": "Hebrew", "hr": "Croatian", "hu": "Hungarian", "ja": "Japanese", "ko": "Korean", "mk": "Macedonian", "nl": "Dutch", "pl": "Polish", "pt": "Portuguese", "ro": "Romanian", "ru": "Russian", "sk": "Slovak", "sl": "Slovenian", "sq": "Albanian", "sr": "Serbian", "th": "Thai", "tr": "Turkish", "vi": "Vietnamese", "zh": "Chinese"}
        return english_names.get(code, code.upper())

    def show_message(self, message, type=MessageBox.TYPE_INFO, timeout=0):
        self.session.openWithCallback(None, MessageBox, message, type, timeout=timeout)

    def open_settings(self): self.defer_message(_("Settings functionality coming soon!"))
    def check_update_silent(self): self.update_plugin(silent=True)

    def update_plugin(self, silent=False):
        from twisted.internet import threads
        d = threads.deferToThread(self._fetch_remote_version)
        d.addCallback(self._version_fetched, silent)
        d.addErrback(self._version_failed, silent)

    @staticmethod
    def _fetch_remote_version():
        req = Request(b64decoder(installer_url), headers={"User-Agent": AgentRequest})
        page = urlopen(req, timeout=15).read().decode("utf-8")
        remote_version, remote_changelog = "0.0", ""
        for line in page.split("\n"):
            line = line.strip()
            if line.startswith("version"): remote_version = line.split("=", 1)[-1].strip().strip("'").strip('"')
            elif line.startswith("changelog"): remote_changelog = line.split("=", 1)[-1].strip().strip("'").strip('"'); break
        return remote_version, remote_changelog

    def _version_failed(self, failure, silent):
        if not silent and not self.screen_closed:
            self.defer_message(_("Unable to fetch version info:\n{}").format(failure.getErrorMessage()), MessageBox.TYPE_ERROR)

    def _version_fetched(self, result, silent):
        if self.screen_closed: return
        remote_version, remote_changelog = result
        self.new_version, self.new_changelog = str(remote_version), str(remote_changelog)
        if version_tuple(PLUGIN_VERSION) < version_tuple(self.new_version): self.ask_update()
        elif not silent:
            self.defer_message(_("You are already running the latest version: {}").format(PLUGIN_VERSION), MessageBox.TYPE_INFO)

    def ask_update(self):
        def ask():
            msg = _("New version %(version)s available\n\nChangelog:\n%(changelog)s\n\nDo you want to install it now?") % {"version": self.new_version, "changelog": self.new_changelog}
            self.session.openWithCallback(self.install_update, MessageBox, msg, MessageBox.TYPE_YESNO)
        self._defer_timer = eTimer()
        self._defer_timer_conn = timer_connect(self._defer_timer, ask)
        self._defer_timer.start(100, True)

    def install_update(self, answer=False):
        if answer:
            try: self.session.open(Console, _("Upgrading..."), cmdlist=["wget -q --no-check-certificate " + b64decoder(installer_url) + " -O - | /bin/sh"], finishedCallback=self.update_callback, closeOnSuccess=False)
            except Exception as e: self.defer_message(_("Update failed:\n%s") % str(e), MessageBox.TYPE_ERROR)
        else: self.defer_message(_("Update Aborted!"), MessageBox.TYPE_INFO)

    def update_callback(self, result=None):
        if result in (None, 0):
            self.session.openWithCallback(lambda *args: self.close(), MessageBox, _("Update completed successfully!\n\nRestart Enigma2 to use the new version."), type=MessageBox.TYPE_INFO, timeout=4)
        else: self.defer_message(_("Update encountered an error (code: %s)") % str(result), MessageBox.TYPE_ERROR)

    def get_about_text(self): return _("WorldCam v%s\n\nLive webcam viewer featuring global locations\n\nDeveloped by Lululla") % PLUGIN_VERSION
    def open_about(self): self.session.openWithCallback(self.open_menu, MessageBox, self.get_about_text(), MessageBox.TYPE_INFO)
    def open_about_direct(self): self.session.open(MessageBox, self.get_about_text(), MessageBox.TYPE_INFO)

    def defer_message(self, text, mtype=MessageBox.TYPE_INFO):
        self._defer_timer = eTimer()
        self._defer_timer_conn = timer_connect(self._defer_timer, lambda: self.session.open(MessageBox, text, type=mtype))
        self._defer_timer.start(100, True)


class WorldCamFavoritesScreen(WebcamBaseScreen):
    def __init__(self, session, lang=None):
        super().__init__(session, lang)
        disable_summary(self)
        self["title"] = Label(_("Your Favorites"))
        self["flag_icon"] = Pixmap()
        self["language_label"] = Label(self.lang.upper())
        self["paypal"] = Label(paypal())
        self["key_red"] = Button(_("Exit"))
        self["key_green"] = Button(_("Play"))
        self["key_yellow"] = Button(_("Remove"))
        self["key_blue"] = Button(_("Export"))
        self["actions"] = HelpableActionMap(self, "WorldCamActions", {"ok": self.on_item_selected, "cancel": self.close, "red": self.close, "green": self.on_item_selected, "yellow": self.remove_favorite, "blue": self.export_favorites})
        self.favorites = []
        self.onLayoutFinish.append(self.load_favorites)
        self.onLayoutFinish.append(self.set_flag_icon)

    def load_favorites(self):
        try:
            self.favorites = FavoritesManager.load_favorites()
            if not self.favorites:
                showlist([], self["list"])
                self["title"].setText(_("No favorites yet"))
                self["key_yellow"].setText("")
                return
            showlist(self.favorites, self["list"])
            self["list"].setCurrentIndex(0)
            self["title"].setText(_("Your Favorites"))
            self["key_yellow"].setText(_("Remove"))
        except Exception as e: self.logger.error("Error loading favorites: %s" % str(e))

    def remove_favorite(self):
        index = self["list"].getCurrentIndex()
        if index is None or index < 0 or index >= len(self.favorites): return
        webcam = self.favorites[index]
        if FavoritesManager.remove_favorite(webcam["url"]): self.load_favorites()

    def export_favorites(self):
        success, message = FavoritesManager.export_to_bouquet()
        self.session.open(MessageBox, message, MessageBox.TYPE_INFO if success else MessageBox.TYPE_ERROR)

    def on_item_selected(self):
        index = self["list"].getCurrentIndex()
        if index is None or index < 0 or index >= len(self.favorites): return
        self.session.open(WorldCamPlayer, webcams=self.favorites, current_index=index)


class WorldCamLocalScreen(WebcamBaseScreen):
    def __init__(self, session, lang=None):
        super().__init__(session, lang)
        disable_summary(self)
        self.scraper = SkylineScraper(self.lang)
        self["title"] = Label(_("User Lists"))
        self["flag_icon"] = Pixmap()
        self["language_label"] = Label(self.lang.upper())
        self["paypal"] = Label(paypal())
        self["key_red"] = Button(_("Exit"))
        self["key_green"] = Button()
        self["key_yellow"] = Button()
        self["key_blue"] = Button()
        self["actions"] = HelpableActionMap(self, "WorldCamActions", {"ok": self.on_item_selected, "cancel": self.close})
        self.user_lists = []
        self.onLayoutFinish.append(self.load_user_lists)
        self.onLayoutFinish.append(self.set_flag_icon)

    def load_user_lists(self):
        try:
            playlists_path = join(PLUGIN_PATH, "Playlists")
            self.user_lists = self.scraper.get_local_playlists(playlists_path)
            if not exists(playlists_path): 
                makedirs(playlists_path)
            
            if not self.user_lists:
                self["title"].setText(_("No playlists found"))
                return
            
            clean_lists = [splitext(name)[0] for name in self.user_lists]
            
            items = []
            for name in clean_lists:
                lname = name.lower()
                if "youtube" in lname or "yt" in lname:
                    icon = "youtube.png"
                elif "hasbahca" in lname:
                    icon = "hasbahca.png"
                elif "webcam.pl" in lname or "webcampl" in lname:
                    icon = "webcampl.png"
                elif "favorite" in lname or "preferiti" in lname:
                    icon = "favorite.png"
                else:
                    icon = "user_lists.png"
                    
                items.append({"name": name, "icon": icon})
                
            showlist(items, self["list"])
            if items: 
                self["list"].setCurrentIndex(0)
                
        except Exception as e: 
            self.logger.error("Error loading user playlists: %s" % str(e))

    def on_item_selected(self):
        try:
            idx = self["list"].getCurrentIndex()
            if not self.user_lists or idx < 0 or idx >= len(self.user_lists): return
            self.session.open(WorldCamLocal, self.user_lists[idx], lang=self.lang)
        except Exception as e: self.logger.error("Error on item selected: %s" % str(e))


class WorldCamLocal(WebcamBaseScreen):
    def __init__(self, session, playlists, lang=None):
        super().__init__(session, lang)
        disable_summary(self)
        self.category = playlists
        self.scraper = SkylineScraper(self.lang)
        self["title"] = Label(splitext(playlists)[0])
        self.webcams = []
        self["flag_icon"] = Pixmap()
        self["language_label"] = Label(self.lang.upper())
        self["paypal"] = Label(paypal())
        self["key_red"] = Button(_("Exit"))
        self["key_green"] = Button()
        self["key_yellow"] = Button()
        self["key_blue"] = Button()
        self["actions"] = HelpableActionMap(self, "WorldCamActions", {"ok": self.on_item_selected, "cancel": self.close})
        self.onLayoutFinish.append(self.load_webcams)
        self.onLayoutFinish.append(self.set_flag_icon)

    def load_webcams(self):
        path = join(PLUGIN_PATH, "Playlists", self.category)
        try:
            if not exists(path) or getsize(path) == 0:
                self["title"].setText(_("Empty or missing playlist"))
                return
            self.webcams = self.scraper.parse_local_playlist_file(path) or []
            if not self.webcams: self["title"].setText(_("No valid webcams in playlist"))
            else:
                showlist(self.webcams, self["list"])
                self["list"].setCurrentIndex(0)
        except Exception as e: self.logger.error(f"Error loading playlist: {str(e)}")

    def on_item_selected(self):
        index = self["list"].getCurrentIndex()
        if index is None or index < 0 or index >= len(self.webcams): return
        self.session.open(WorldCamPlayer, webcams=self.webcams, current_index=index)


class WorldCamContinentScreen(WebcamBaseScreen):
    def __init__(self, session, lang=None):
        super().__init__(session, lang)
        disable_summary(self)
        self.scraper = SkylineScraper(self.lang)
        self["title"] = Label(_("Continents"))
        self["flag_icon"] = Pixmap()
        self["language_label"] = Label(self.lang.upper())
        self["paypal"] = Label(paypal())
        self["key_red"] = Button(_("Exit"))
        self["key_green"] = Button()
        self["key_yellow"] = Button()
        self["key_blue"] = Button()
        self["actions"] = HelpableActionMap(self, "WorldCamActions", {"ok": self.on_item_selected, "cancel": self.close})
        self.continents = []
        self.onLayoutFinish.append(self.load_continents)
        self.onLayoutFinish.append(self.set_flag_icon)

    def load_continents(self): self.run_async(self.scraper.get_continents, self._continents_loaded, _("Continents"))

    def _continents_loaded(self, continents):
        try:
            if continents is None: 
                raise ValueError("no data")
            self.continents = continents
            
            items = []
            for c in self.continents:
                c_name = c["name"].upper()
                
                if "AMERIC" in c_name:
                    icon_name = "americas.png"
                elif "EUROP" in c_name:
                    # Controlla se esiste europe.png, altrimenti usa europa.png
                    if exists(join(PLUGIN_PATH, "countries", "europe.png")):
                        icon_name = "europe.png"
                    else:
                        icon_name = "europa.png"
                elif "AFRIC" in c_name:
                    icon_name = "africa.png"
                elif "ASI" in c_name:
                    icon_name = "asia.png"
                elif "OCEAN" in c_name:
                    icon_name = "oceania.png"
                else:
                    icon_name = "continents.png"
                    
                items.append({"name": c["name"], "icon": icon_name})
                
            if items:
                showlist(items, self["list"])
                self["list"].setCurrentIndex(0)
        except Exception as e:
            self.logger.error("Error loading continents: " + str(e))

    def on_item_selected(self):
        index = self["list"].getCurrentIndex()
        if index is None or index < 0 or index >= len(self.continents): return
        self.session.open(WorldCamContinentCountryScreen, self.continents[index], lang=self.lang)


class WorldCamContinentCountryScreen(WebcamBaseScreen):
    def __init__(self, session, continent, lang=None):
        super().__init__(session, lang)
        disable_summary(self)
        self.continent = continent
        self["title"] = Label(continent["name"])
        self["flag_icon"] = Pixmap()
        self["language_label"] = Label(self.lang.upper())
        self["paypal"] = Label(paypal())
        self["key_red"] = Button(_("Exit"))
        self["key_green"] = Button()
        self["key_yellow"] = Button()
        self["key_blue"] = Button()
        self["actions"] = HelpableActionMap(self, "WorldCamActions", {"ok": self.on_item_selected, "cancel": self.close})
        self.countries = []
        self.onLayoutFinish.append(self.load_countries)
        self.onLayoutFinish.append(self.set_flag_icon)

    def load_countries(self):
        try:
            self.countries = sorted(self.continent["countries"], key=lambda c: c["name"].lower())
            country_names = [country["name"] for country in self.countries]
            if country_names:
                showlist(country_names, self["list"])
                self["list"].setCurrentIndex(0)
        except Exception as e: self.logger.error(f"Error loading countries: {str(e)}")

    def on_item_selected(self):
        index = self["list"].getCurrentIndex()
        if index is None or index < 0 or index >= len(self.countries): return
        self.session.open(WorldCamLocationScreen, self.countries[index], lang=self.lang)


class WorldCamCountryScreen(WebcamBaseScreen):
    def __init__(self, session, category=None, lang=None):
        super().__init__(session, lang)
        disable_summary(self)
        self.scraper = SkylineScraper(self.lang)
        self["title"] = Label(_("Country"))
        self["flag_icon"] = Pixmap()
        self["language_label"] = Label(self.lang.upper())
        self["paypal"] = Label(paypal())
        self["key_red"] = Button(_("Exit"))
        self["key_green"] = Button()
        self["key_yellow"] = Button()
        self["key_blue"] = Button()
        self["actions"] = HelpableActionMap(self, "WorldCamActions", {"ok": self.on_item_selected, "cancel": self.close})
        self.countries = []
        self.onLayoutFinish.append(self.load_countries)
        self.onLayoutFinish.append(self.set_flag_icon)

    def load_countries(self): self.run_async(self.scraper.get_countries, self._countries_loaded, _("Country"))

    def _countries_loaded(self, countries):
        try:
            if countries is None: raise ValueError("no data")
            self.countries = sorted(countries, key=lambda c: c["name"].lower())
            country_names = [country["name"] for country in self.countries]
            if country_names:
                showlist(country_names, self["list"])
                self["list"].setCurrentIndex(0)
        except Exception as e: self.logger.error("Error loading countries: %s" % str(e))

    def on_item_selected(self):
        index = self["list"].getCurrentIndex()
        if index is None or index < 0 or index >= len(self.countries): return
        self.session.open(WorldCamLocationScreen, self.countries[index], lang=self.lang)


class WorldCamCategoryScreen(WebcamBaseScreen):
    def __init__(self, session, lang=None):
        super().__init__(session, lang)
        disable_summary(self)
        self.scraper = SkylineScraper(self.lang)
        self["title"] = Label(_("Categories"))
        self["flag_icon"] = Pixmap()
        self["language_label"] = Label(self.lang.upper())
        self["paypal"] = Label(paypal())
        self["key_red"] = Button(_("Exit"))
        self["key_green"] = Button()
        self["key_yellow"] = Button()
        self["key_blue"] = Button()
        self["actions"] = HelpableActionMap(self, "WorldCamActions", {"ok": self.on_item_selected, "cancel": self.close})
        self.categories = []
        self.onLayoutFinish.append(self.load_categories)
        self.onLayoutFinish.append(self.set_flag_icon)

    def load_categories(self): self.run_async(self.scraper.get_categories, self._categories_loaded, _("Categories"))

    def _categories_loaded(self, categories):
        try:
            if categories is None: 
                raise ValueError("no data")
            
            import unicodedata
            
            self.categories = sorted(categories, key=lambda c: c["name"].lower())
            items = []
            
            for c in self.categories:
                c_name = c["name"]
                
                # Crea uno "slug" dal nome: minuscolo, senza accenti, senza spazi
                # Es. "Piste da Sci" -> "pistedasci", "Città" -> "citta"
                slug = unicodedata.normalize('NFKD', c_name).encode('ASCII', 'ignore').decode('utf-8')
                slug = slug.lower().replace(" ", "").replace("'", "").replace("-", "")
                
                # 1. Cerca prima il file esatto (es. paesaggi.png, vulcani.png, pistedasci.png)
                exact_path = join(PLUGIN_PATH, "countries", f"{slug}.png")
                if exists(exact_path):
                    icon_name = f"{slug}.png"
                    
                # 2. Altrimenti usa le parole chiave di fallback
                elif "animal" in slug: icon_name = "animali.png"
                elif "citt" in slug or "city" in slug: icon_name = "citta.png"
                elif "web" in slug or "internet" in slug: icon_name = "web.png"
                elif "lagh" in slug or "lake" in slug: icon_name = "laghi.png"
                elif "mar" in slug or "sea" in slug or "ocean" in slug: icon_name = "mare.png"
                elif "nuov" in slug or "new" in slug: icon_name = "nuove.png"
                elif "mont" in slug or "mountain" in slug or "sci" in slug: icon_name = "montagna.png"
                elif "spiagg" in slug or "beach" in slug: icon_name = "spiaggia.png"
                elif "aeroport" in slug or "airport" in slug: icon_name = "aeroporto.png"
                elif "unesco" in slug: icon_name = "unesco.png"
                elif "vulcan" in slug: icon_name = "vulcani.png"
                else:
                    # Fallback finale
                    icon_name = "categories.png"
                    
                items.append({"name": c_name, "icon": icon_name})
                
            if items:
                showlist(items, self["list"])
                self["list"].setCurrentIndex(0)
        except Exception as e: 
            self.logger.error("Error loading categories: %s" % str(e))

    def on_item_selected(self):
        index = self["list"].getCurrentIndex()
        if index is None or index < 0 or index >= len(self.categories): return
        self.session.open(WorldCamWebcamScreen, self.categories[index], lang=self.lang)


class WorldCamTopScreen(WebcamBaseScreen):
    def __init__(self, session, lang=None):
        super().__init__(session, lang)
        disable_summary(self)
        self.scraper = SkylineScraper(self.lang)
        self["title"] = Label(_("Top Webcams"))
        self["flag_icon"] = Pixmap()
        self["language_label"] = Label(self.lang.upper())
        self["paypal"] = Label(paypal())
        self["key_red"] = Button(_("Exit"))
        self["key_green"] = Button()
        self["key_yellow"] = Button()
        self["key_blue"] = Button()
        self["actions"] = HelpableActionMap(self, "WorldCamActions", {"ok": self.on_item_selected, "cancel": self.close})
        self.top_webcams = []
        self.onLayoutFinish.append(self.load_top_webcams)
        self.onLayoutFinish.append(self.set_flag_icon)

    def load_top_webcams(self): self.run_async(self.scraper.get_top_webcams, self._top_loaded, _("Top Webcams"))

    def _top_loaded(self, top_webcams):
        try:
            if top_webcams is None: raise ValueError("no data")
            self.top_webcams = sorted([w for w in top_webcams if w["name"].strip().lower() != "top live cams"], key=lambda c: c["name"].lower())
            if self.top_webcams:
                showlist(self.top_webcams, self["list"])
                self["list"].setCurrentIndex(0)
        except Exception as e: self.logger.error("Error loading top webcams: %s" % str(e))

    def on_item_selected(self):
        index = self["list"].getCurrentIndex()
        if index is None or index < 0 or index >= len(self.top_webcams): return
        self.session.open(WorldCamPlayer, webcams=self.top_webcams, current_index=index)


class WorldCamLocationScreen(WebcamBaseScreen):
    def __init__(self, session, country, lang=None):
        super().__init__(session, lang)
        disable_summary(self)
        self.country = country
        self.scraper = SkylineScraper(self.lang)
        self["title"] = Label(country["name"])
        self["flag_icon"] = Pixmap()
        self["language_label"] = Label(self.lang.upper())
        self["paypal"] = Label(paypal())
        self["key_red"] = Button(_("Exit"))
        self["key_green"] = Button()
        self["key_yellow"] = Button()
        self["key_blue"] = Button()
        self["actions"] = HelpableActionMap(self, "WorldCamActions", {"ok": self.on_item_selected, "cancel": self.close})
        self.locations = []
        self.onLayoutFinish.append(self.load_locations)
        self.onLayoutFinish.append(self.set_flag_icon)

    def load_locations(self): self.run_async(lambda: self.scraper.get_locations(self.country["url"]), self._locations_loaded, self.country["name"])

    def _locations_loaded(self, locations):
        try:
            if locations is None: raise ValueError("no data")
            self.locations = sorted(locations, key=lambda loc: loc["name"].lower())
            location_names = [loc["name"] for loc in self.locations]
            if location_names:
                showlist(location_names, self["list"])
                self["list"].setCurrentIndex(0)
        except Exception as e: self.logger.error("Error loading locations: %s" % str(e))

    def on_item_selected(self):
        index = self["list"].getCurrentIndex()
        if index is None or index < 0 or index >= len(self.locations): return
        self.session.open(WorldCamWebcamScreen, self.locations[index], lang=self.lang)


class WorldCamWebcamScreen(WebcamBaseScreen):
    def __init__(self, session, location, lang=None):
        super().__init__(session, lang)
        self.location = location
        self.scraper = SkylineScraper(self.lang)
        self["title"] = Label(location["name"])
        self["flag_icon"] = Pixmap()
        self["language_label"] = Label(self.lang.upper())
        self["paypal"] = Label(paypal())
        self["key_red"] = Button(_("Exit"))
        self["key_green"] = Button(_("Add/Remove"))
        self["key_yellow"] = Button(_("Export"))
        self["key_blue"] = Button(_("Menu"))
        self["actions"] = HelpableActionMap(self, "WorldCamActions", {
            "ok": self.on_item_selected, "cancel": self.close, "blue": self.open_context_menu,
            "green": self.toggle_favorite, "yellow": self.export_bouquet_direct,
        })
        self.webcams = []
        self.onLayoutFinish.append(self.load_webcams)
        self.onLayoutFinish.append(self.set_flag_icon)

    def open_context_menu(self):
        index = self["list"].getCurrentIndex()
        if index is None or index < 0 or index >= len(self.webcams): return
        webcam = self.webcams[index]
        is_fav = FavoritesManager.is_favorite(webcam["url"])
        menu_items = [(_("Add to favorites"), "add_fav") if not is_fav else (_("Remove from favorites"), "remove_fav"), (_("Play"), "play"), (_("Export All to Bouquet"), "export_bouquet")]
        self.session.openWithCallback(lambda choice: self.context_menu_callback(choice, webcam), ChoiceBox, title=webcam["name"], list=menu_items)

    def toggle_favorite(self):
        index = self["list"].getCurrentIndex()
        if index is None or index < 0 or index >= len(self.webcams): return
        webcam = self.webcams[index]
        if FavoritesManager.is_favorite(webcam["url"]):
            FavoritesManager.remove_favorite(webcam["url"])
            self.session.open(MessageBox, _("Removed from favorites"), MessageBox.TYPE_INFO, timeout=3)
        else:
            FavoritesManager.add_favorite(webcam["name"], webcam["url"], webcam.get("thumbnail"))
            self.session.open(MessageBox, _("Added to favorites!"), MessageBox.TYPE_INFO, timeout=3)

    def context_menu_callback(self, choice, webcam):
        if choice is None: return
        if choice[1] == "add_fav": FavoritesManager.add_favorite(webcam["name"], webcam["url"], webcam.get("thumbnail"))
        elif choice[1] == "remove_fav": FavoritesManager.remove_favorite(webcam["url"])
        elif choice[1] == "export_bouquet": self.export_bouquet_direct()
        elif choice[1] == "play":
            index = self["list"].getCurrentIndex()
            self.session.open(WorldCamPlayer, webcams=self.webcams, current_index=index)

    def export_bouquet_direct(self):
        success, message = FavoritesManager.export_to_bouquet(self.webcams, self.location["name"])
        self.session.open(MessageBox, message, MessageBox.TYPE_INFO if success else MessageBox.TYPE_ERROR)

    def load_webcams(self): self.run_async(lambda: self.scraper.get_webcams(self.location["url"]), self._webcams_loaded, self.location["name"])

    def _webcams_loaded(self, webcams):
        try:
            if webcams is None: raise ValueError("no data")
            self.webcams = sorted(webcams, key=lambda w: w["name"].lower())
            if self.webcams:
                showlist(self.webcams, self["list"])
                self["list"].setCurrentIndex(0)
        except Exception as e: self.logger.error("Error loading webcams: %s" % str(e))

    def on_item_selected(self):
        index = self["list"].getCurrentIndex()
        if index is None or index < 0 or index >= len(self.webcams): return
        self.session.open(WorldCamPlayer, webcams=self.webcams, current_index=index)


def main(session, **kwargs):
    from .checkdependencies import check_requirements
    logger = Logger()
    check_requirements(logger=logger)
    session.open(WorldCamMainScreen)

def Plugins(**kwargs):
    from Plugins.Plugin import PluginDescriptor
    return PluginDescriptor(
        name=f"WorldCam {PLUGIN_VERSION}",
        description=_("Live webcams from around the world"),
        where=PluginDescriptor.WHERE_PLUGINMENU,
        icon=join(PLUGIN_PATH, "plugin.png"),
        fnc=main
    )