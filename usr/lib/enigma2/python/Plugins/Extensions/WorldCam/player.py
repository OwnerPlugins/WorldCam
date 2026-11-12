#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
#########################################################
#                                                       #
#  Worldcam Player from Plugin                          #
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
import sys
from os import remove
from os.path import abspath, dirname, exists

from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.ServiceEventTracker import InfoBarBase, ServiceEventTracker
from Components.config import config
from enigma import eServiceReference, eTimer, iPlayableService, getDesktop
from Screens.InfoBarGenerics import (
    InfoBarAudioSelection,
    InfoBarMenu,
    InfoBarNotifications,
    InfoBarSeek,
    InfoBarSubtitleSupport,
)
from Screens.MessageBox import MessageBox
from Screens.Screen import Screen

from . import _
from .scraper import SkylineScraper
from .utils import (
    AspectManager,
    FavoritesManager,
    Logger,
    disable_summary,
    is_youtube_url,
    convert_youtube_embed_to_watch,
    get_service_type,
    timer_connect,
)
from .youtube_helper import resolve_youtube

__author__ = "Lululla"

PLUGIN_PATH = dirname(__file__)
screen_width = getDesktop(0).size().width()

plugin_dir = dirname(abspath(__file__))
if plugin_dir not in sys.path:
    sys.path.append(plugin_dir)

HELP_TEXT = _("OK = Info | CH-/CH+ = Prev/Next | BLUE = Fav | PLAY/PAUSE = Toggle | STOP = Stop | EXIT = Exit | by Lululla")

class WorldCamOverlay(Screen):
    def __init__(self, session):
        if screen_width >= 1920:
            width, height, font = screen_width, 70, 34
        else:
            width, height, font = screen_width, 50, 26
        self.skin = (
            '<screen name="WorldCamOverlay" position="0,0" size="%d,%d" '
            'flags="wfNoBorder" backgroundColor="#50000000" zPosition="10">'
            '<widget name="text" position="0,0" size="%d,%d" '
            'font="Regular;%d" halign="center" valign="center" '
            'foregroundColor="#ffffff" backgroundColor="#50000000" '
            'transparent="1" /></screen>' % (width, height, width, height, font))
        Screen.__init__(self, session)
        self["text"] = Label("")

    def setText(self, text):
        self["text"].setText(text)

class TvInfoBarShowHide():
    STATE_HIDDEN = 0
    STATE_HIDING = 1
    STATE_SHOWING = 2
    STATE_SHOWN = 3
    skipToggleShow = False

    def __init__(self):
        self["ShowHideActions"] = ActionMap(["InfobarShowHideActions"], {"toggleShow": self.OkPressed, "hide": self.hide}, 0)
        self.__event_tracker = ServiceEventTracker(screen=self, eventmap={iPlayableService.evStart: self.serviceStarted})
        self.__state = self.STATE_SHOWN
        self.__locked = 0

        self.overlay = self.session.instantiateDialog(WorldCamOverlay)
        self.overlay_timer = eTimer()
        self.overlay_timer_conn = timer_connect(self.overlay_timer, self.hide_overlay)

        self.hideTimer = eTimer()
        self.hideTimer_conn = timer_connect(self.hideTimer, self.doTimerHide)
        self.hideTimer.start(5000, True)
        self.onShow.append(self.__onShow)
        self.onHide.append(self.__onHide)

    def show_overlay_text(self, text, timeout=0):
        self.overlay_timer.stop()
        if self.overlay is None: return
        self.overlay.setText(text)
        self.overlay.show()
        if timeout: self.overlay_timer.start(timeout, True)

    def hide_overlay(self):
        self.overlay_timer.stop()
        if self.overlay is not None: self.overlay.hide()

    def show_help_overlay(self):
        self.show_overlay_text(HELP_TEXT, 5000)

    def OkPressed(self):
        self.toggleShow()

    def __onShow(self):
        self.__state = self.STATE_SHOWN
        self.startHideTimer()

    def __onHide(self):
        self.__state = self.STATE_HIDDEN

    def doShow(self):
        self.hideTimer.stop()
        self.show()
        self.startHideTimer()

    def doHide(self):
        self.hideTimer.stop()
        self.hide()
        self.startHideTimer()

    def serviceStarted(self):
        if self.execing and config.usage.show_infobar_on_zap.value: self.doShow()

    def startHideTimer(self):
        if self.__state == self.STATE_SHOWN and not self.__locked:
            self.hideTimer.stop()
            self.hideTimer.start(5000, True)

    def doTimerHide(self):
        self.hideTimer.stop()
        if self.__state == self.STATE_SHOWN: self.hide()

    def toggleShow(self):
        if not self.skipToggleShow:
            if self.__state == self.STATE_HIDDEN:
                self.doShow()
                self.show_help_overlay()
            else:
                self.doHide()
                self.hide_overlay()
        else:
            self.skipToggleShow = False

    def lockShow(self):
        try: self.__locked += 1
        except BaseException: self.__locked = 0
        if self.execing:
            self.show()
            self.hideTimer.stop()
            self.skipToggleShow = False

    def unlockShow(self):
        try: self.__locked -= 1
        except BaseException: self.__locked = 0
        if self.__locked < 0: self.__locked = 0
        if self.execing: self.startHideTimer()

class WorldCamPlayer(InfoBarBase, InfoBarMenu, InfoBarSeek, InfoBarAudioSelection, InfoBarSubtitleSupport, InfoBarNotifications, TvInfoBarShowHide, Screen):
    STATE_IDLE = 0
    STATE_PLAYING = 1
    STATE_PAUSED = 2
    ENABLE_RESUME_SUPPORT = True
    ALLOW_SUSPEND = True

    def __init__(self, session, webcams, current_index=0):
        # --- FIX CRASH SKIN AGP: Forza lo skin PRIMA di Screen.__init__ ---
        self.skin = """
            <screen name="WorldCamPlayer" position="0,0" size="1920,1080" flags="wfNoBorder" backgroundColor="transparent">
                <widget name="state" position="0,0" size="0,0" />
                <widget name="eventname" position="0,0" size="0,0" />
                <widget name="speed" position="0,0" size="0,0" />
                <widget name="statusicon" position="0,0" size="0,0" />
                <widget name="key_green" position="0,0" size="0,0" />
                <widget name="key_yellow" position="0,0" size="0,0" />
                <widget name="key_blue" position="0,0" size="0,0" />
                <widget source="session.VideoPicture" render="Pig" position="0,0" size="1920,1080" backgroundColor="transparent" transparent="1" />
            </screen>
        """
        self.skinName = "WorldCamPlayer"
        # ------------------------------------------------------------------

        Screen.__init__(self, session)
        disable_summary(self)
        self.session = session
        self.logger = Logger()

        self.webcams = webcams or []
        if not (0 <= current_index < len(self.webcams)):
            current_index = 0
        self.current_index = current_index
        self.state = self.STATE_PLAYING
        self.play_request = 0
        self.closing = False
        self._cleaned_up = False

        for base_class in (InfoBarBase, InfoBarMenu, InfoBarSeek, InfoBarAudioSelection, InfoBarSubtitleSupport, InfoBarNotifications, TvInfoBarShowHide):
            base_class.__init__(self)

        self.aspect_manager = AspectManager()
        self.aspect_manager.set_aspect("16:9")
        self.scraper = SkylineScraper()
        self["state"] = Label("")
        self["eventname"] = Label("")
        self["speed"] = Label("")
        self["statusicon"] = Label("")
        self["key_green"] = Label("")
        self["key_yellow"] = Label("")
        self["key_blue"] = Label("")
        
        self["actions"] = ActionMap(
            ["ColorActions", "OkCancelActions", "WorldCamPlayer", "MediaPlayerActions"],
            {
                "cancel": self.cancel,
                "back": self.cancel,
                "red": self.cancel,
                "prevBouquet": self.previous_webcam,
                "nextBouquet": self.next_webcam,
                "channelDown": self.previous_webcam,
                "channelUp": self.next_webcam,
                "prev": self.previous_webcam,
                "previous": self.previous_webcam,
                "next": self.next_webcam,
                "leavePlayer": self.leavePlayer,
                "leavePlayerOnExit": self.leavePlayer,
                "stop": self.leavePlayer,
                "blue": self.toggle_favorite,
                "playpauseService": self.playpauseService,
            },
            -2
        )

        self.__event_tracker = ServiceEventTracker(
            screen=self,
            eventmap={
                iPlayableService.evStart: self.__serviceStarted,
                iPlayableService.evEOF: self.__evEOF,
                iPlayableService.evStopped: self.__evStopped,
            }
        )
        self.srefInit = self.session.nav.getCurrentlyPlayingServiceReference()
        self.onClose.append(self.cleanup)
        self.onFirstExecBegin.append(self.start_playback)

    def get_current_webcam(self):
        return self.webcams[self.current_index]

    def next_webcam(self):
        if self.current_index < len(self.webcams) - 1:
            self.current_index += 1
            self.switch_webcam()

    def previous_webcam(self):
        if self.current_index > 0:
            self.current_index -= 1
            self.switch_webcam()

    def switch_webcam(self):
        try:
            self.session.nav.stopService()
            self.start_playback()
        except Exception as e:
            self.logger.error("Error switching webcam: " + str(e))
            self.show_error(_("Error switching webcam"))

    def __serviceStarted(self):
        self.state = self.STATE_PLAYING

    def toggle_favorite(self):
        if not self.webcams: return
        current_webcam = self.get_current_webcam()
        if FavoritesManager.is_favorite(current_webcam["url"]):
            success = FavoritesManager.remove_favorite(current_webcam["url"])
            message = _("Removed from favorites") if success else _("Error removing favorite")
        else:
            success = FavoritesManager.add_favorite(current_webcam["name"], current_webcam["url"], current_webcam.get("thumbnail"))
            message = _("Added to favorites!") if success else _("Error adding favorite")

        self.session.open(MessageBox, message, MessageBox.TYPE_INFO, timeout=3)

    def __evEOF(self):
        self.leavePlayer()

    def __evStopped(self):
        pass

    def leavePlayer(self, *args):
        if self.closing: return
        self.closing = True
        self.close()

    def cancel(self):
        self.leavePlayer()

    def start_playback(self):
        if self.closing or not self.webcams: return
        try:
            current_webcam = self.get_current_webcam()
            self.play_request += 1
            request_id = self.play_request

            if is_youtube_url(current_webcam["url"]):
                self.show_overlay_text(_("Resolving YouTube stream..."))
            else:
                self.show_overlay_text(_("Loading stream..."))

            from twisted.internet import threads
            d = threads.deferToThread(self._resolve_stream, current_webcam["url"])
            d.addCallback(self._stream_resolved, request_id, current_webcam["name"])
            d.addErrback(self._resolve_failed, request_id, current_webcam["name"])
        except Exception as e:
            self.logger.error("Playback error: " + str(e))
            self.show_error(_("Playback error"))

    def _resolve_stream(self, url):
        if is_youtube_url(url):
            return resolve_youtube(convert_youtube_embed_to_watch(url))

        stream_url = self.scraper.get_stream_url(url)
        if not stream_url:
            return None, _("Could not extract video stream")
        if is_youtube_url(stream_url):
            return resolve_youtube(convert_youtube_embed_to_watch(stream_url))
        return stream_url, None

    def _stream_resolved(self, result, request_id, title):
        if self.closing or request_id != self.play_request: return

        self.hide_overlay()
        resolved, error = result
        if resolved:
            self.play_stream(resolved, title)
            return

        msg = _("Stream not available")
        if error:
            msg += "\n\n%s" % error
        if error == "yt-dlp is not installed":
            msg += "\n\n" + _("Install it with:\nopkg install python3-yt-dlp")
        self.show_error(msg)

    def _resolve_failed(self, failure, request_id, title):
        self._stream_resolved((None, failure.getErrorMessage()), request_id, title)

    def start_service_playback(self, service):
        if self.session.nav.getCurrentlyPlayingServiceReference():
            self.session.nav.stopService()
        self.session.nav.playService(service)
        self.show()
        self.state = self.STATE_PLAYING
        self.show_help_overlay()

    def play_stream(self, stream_url, title=""):
        try:
            if isinstance(stream_url, (tuple, list)):
                stream_url = str(stream_url[0])
            else:
                stream_url = str(stream_url)

            service_type = get_service_type()
            service = eServiceReference(service_type, 0, stream_url)
            service.setName(title)
            self.start_service_playback(service)
        except Exception as e:
            self.logger.error("[Player] error playing stream: %s" % str(e))
            self.show_error(_("Playback failed!"))

    def playpauseService(self):
        service = self.session.nav.getCurrentService()
        if not service: return

        pauseable = service.pause()
        if pauseable is None:
            if self.state == self.STATE_PLAYING:
                current_ref = self.session.nav.getCurrentlyPlayingServiceReference()
                if current_ref:
                    self.session.nav.stopService()
                    self.state = self.STATE_PAUSED
            elif self.state == self.STATE_PAUSED:
                current_ref = self.session.nav.getCurrentlyPlayingServiceReference()
                if current_ref:
                    self.session.nav.playService(current_ref)
                    self.state = self.STATE_PLAYING
            return

        try:
            if self.state == self.STATE_PLAYING:
                if hasattr(pauseable, 'pause'):
                    pauseable.pause()
                    self.state = self.STATE_PAUSED
            elif self.state == self.STATE_PAUSED:
                if hasattr(pauseable, 'play'):
                    pauseable.play()
                    self.state = self.STATE_PLAYING
        except Exception as e:
            self.show_error(_("Play/pause not supported for this stream"))

    def show_error(self, message):
        if self.closing: return
        self.hide_overlay()
        self.session.openWithCallback(self.leavePlayer, MessageBox, message, MessageBox.TYPE_ERROR)

    def cleanup(self):
        if self._cleaned_up: return
        self._cleaned_up = True
        self.closing = True
        self.hideTimer.stop()
        self.overlay_timer.stop()
        if self.overlay is not None:
            try:
                self.overlay.hide()
                self.session.deleteDialog(self.overlay)
            except Exception: pass
            self.overlay = None

        if exists('/tmp/hls.avi'):
            try: remove('/tmp/hls.avi')
            except BaseException: pass

        self.aspect_manager.restore_aspect()
        self.session.nav.stopService()

        if self.srefInit:
            try: self.session.nav.playService(self.srefInit)
            except BaseException: pass
