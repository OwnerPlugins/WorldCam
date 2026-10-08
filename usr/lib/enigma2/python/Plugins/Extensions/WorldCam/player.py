#!/usr/bin/python
# -*- coding: utf-8 -*-

import sys
import subprocess
from os import remove
from os.path import abspath, dirname, exists
from re import IGNORECASE, search

from urllib.parse import unquote

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
)
from .youtube_helper import resolve_youtube


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
__author__ = "Lululla"

PLUGIN_PATH = dirname(__file__)
screen_width = getDesktop(0).size().width()

plugin_dir = dirname(abspath(__file__))
if plugin_dir not in sys.path:
    sys.path.append(plugin_dir)


class TvInfoBarShowHide():
    """InfoBar show/hide control"""
    STATE_HIDDEN = 0
    STATE_HIDING = 1
    STATE_SHOWING = 2
    STATE_SHOWN = 3
    skipToggleShow = False

    def __init__(self):
        self["ShowHideActions"] = ActionMap(
            ["InfobarShowHideActions"],
            {
                "toggleShow": self.OkPressed,
                "hide": self.hide
            },
            0
        )
        self.__event_tracker = ServiceEventTracker(
            screen=self, eventmap={
                iPlayableService.evStart: self.serviceStarted})
        self.__state = self.STATE_SHOWN
        self.__locked = 0

        self.helpOverlay = Label("")
        self.helpOverlay.skinAttributes = [
            ("position", "0,0"),
            ("size", "1280,50"),
            ("font", "Regular;28"),
            ("halign", "center"),
            ("valign", "center"),
            ("foregroundColor", "#FFFFFF"),
            ("backgroundColor", "#666666"),
            ("transparent", "0"),
            ("zPosition", "100")
        ]

        self["helpOverlay"] = self.helpOverlay
        self["helpOverlay"].hide()

        self.hideTimer = eTimer()
        try:
            self.hideTimer_conn = self.hideTimer.timeout.connect(
                self.doTimerHide)
        except BaseException:
            self.hideTimer.callback.append(self.doTimerHide)
        self.hideTimer.start(5000, True)
        self.onShow.append(self.__onShow)
        self.onHide.append(self.__onHide)

    def show_help_overlay(self):
        help_text = (
            "OK = Info | CH-/CH+ = Prev/Next | BLUE = Fav | PLAY/PAUSE = Toggle | STOP = Stop | EXIT = Exit | by Lululla"
        )
        self["helpOverlay"].setText(help_text)
        self["helpOverlay"].show()

        if not hasattr(self, 'help_timer'):
            self.help_timer = eTimer()
            self.help_timer.callback.append(self.hide_help_overlay)

        self.help_timer.start(5000, True)

    def hide_help_overlay(self):
        if self["helpOverlay"].visible:
            self["helpOverlay"].hide()

    def OkPressed(self):
        if self.__state == self.STATE_SHOWN:
            if self["helpOverlay"].visible:
                self.help_timer.stop()
                self.hide_help_overlay()
            else:
                self.show_help_overlay()
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
        if self["helpOverlay"].visible:
            self.help_timer.stop()
            self.hide_help_overlay()
        self.startHideTimer()

    def serviceStarted(self):
        if self.execing and config.usage.show_infobar_on_zap.value:
            self.doShow()

    def startHideTimer(self):
        if self.__state == self.STATE_SHOWN and not self.__locked:
            self.hideTimer.stop()
            self.hideTimer.start(5000, True)

    def doTimerHide(self):
        self.hideTimer.stop()
        if self.__state == self.STATE_SHOWN:
            self.hide()
            if self["helpOverlay"].visible:
                self.help_timer.stop()
                self.hide_help_overlay()

    def toggleShow(self):
        if not self.skipToggleShow:
            if self.__state == self.STATE_HIDDEN:
                self.doShow()
                self.show_help_overlay()
            else:
                self.doHide()
                if self["helpOverlay"].visible:
                    self.help_timer.stop()
                    self.hide_help_overlay()
        else:
            self.skipToggleShow = False

    def lockShow(self):
        try:
            self.__locked += 1
        except BaseException:
            self.__locked = 0
        if self.execing:
            self.show()
            self.hideTimer.stop()
            self.skipToggleShow = False

    def unlockShow(self):
        try:
            self.__locked -= 1
        except BaseException:
            self.__locked = 0
        if self.__locked < 0:
            self.__locked = 0
        if self.execing:
            self.startHideTimer()

    def debug(self, obj, text=""):
        print(text + " %s\n" % obj)


class WorldCamPlayer(InfoBarBase, InfoBarMenu, InfoBarSeek, InfoBarAudioSelection, InfoBarSubtitleSupport, InfoBarNotifications, TvInfoBarShowHide, Screen):
    STATE_IDLE = 0
    STATE_PLAYING = 1
    STATE_PAUSED = 2
    ENABLE_RESUME_SUPPORT = True
    ALLOW_SUSPEND = True

    def __init__(self, session, webcams, current_index=0):
        Screen.__init__(self, session)
        disable_summary(self)
        self.session = session
        self.skinName = "MoviePlayer"

        # xml_path = join(self.get_skin_path(), "WorldCamPlayer.xml")
        # self.skinName = xml_path
        self.logger = Logger()

        for base_class in (
            InfoBarBase,
            InfoBarMenu,
            InfoBarSeek,
            InfoBarAudioSelection,
            InfoBarSubtitleSupport,
            InfoBarNotifications,
            TvInfoBarShowHide
        ):
            base_class.__init__(self)

        self.webcams = webcams
        self.current_index = current_index
        self.state = self.STATE_PLAYING
        self.youtube_play_request = 0
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
            [
                "ColorActions",
                "OkCancelActions",
                "WorldCamPlayer",
                "MediaPlayerActions",
            ],

            {
                "cancel": self.cancel,
                "back": self.cancel,
                "red": self.cancel,

                "prevBouquet": self.previous_webcam,
                "nextBouquet": self.next_webcam,
                "prev": self.previous_webcam,
                "next": self.next_webcam,
                "leavePlayer": self.leavePlayer,
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
            self.session.open(
                MessageBox,
                _("Error switching webcam"),
                MessageBox.TYPE_ERROR
            )

    def __serviceStarted(self):
        """Service started playing"""
        self.logger.info("Playback started successfully")
        self.state = self.STATE_PLAYING

    def toggle_favorite(self):
        """Add or remove from favorites"""
        current_webcam = self.get_current_webcam()
        if FavoritesManager.is_favorite(current_webcam["url"]):
            success = FavoritesManager.remove_favorite(current_webcam["url"])
            message = _("Removed from favorites") if success else _(
                "Error removing favorite")
        else:
            success = FavoritesManager.add_favorite(
                current_webcam["name"], current_webcam["url"])
            message = _("Added to favorites!") if success else _(
                "Error adding favorite")

        self.session.open(
            MessageBox,
            message,
            MessageBox.TYPE_INFO,
            timeout=3
        )

    def __evEOF(self):
        self.logger.info("Playback completed")
        self.close()

    def __evStopped(self):
        self.logger.info("Playback stopped")
        self.close()

    def leavePlayer(self):
        self.close()

    def cancel(self):
        self.close()

    def start_playback(self):
        try:
            current_webcam = self.get_current_webcam()
            self.logger.info(
                "Starting playback for: {0}".format(current_webcam["name"])
            )
            self.logger.info(
                "URL: {0}".format(current_webcam["url"])
            )

            # Check if it's YouTube
            stream_url = self.scraper.get_stream_url(current_webcam["url"])
            if not stream_url:
                self.logger.error("Could not extract stream URL")
                self.show_error(_("Could not extract video stream"))
                return

            self.logger.info("Stream URL: {0}".format(stream_url))

            if is_youtube_url(stream_url):
                self.logger.info("Detected YouTube stream")
                self.play_youtube(stream_url, current_webcam["name"])
            else:
                self.logger.info("Detected regular stream")
                self.play_stream(stream_url, current_webcam["name"])

        except Exception as e:
            self.logger.error("Playback error: " + str(e))
            self.show_error(_("Playback error"))

    def play_youtube(self, url, title):
        """
        Main YouTube playback method - non-blocking.

        yt-dlp can take 20-60s on slow receivers, so we run it in a
        worker thread via twisted.deferToThread to keep the GUI alive
        and avoid the Enigma2 watchdog killing the player.
        """
        try:
            self.logger.info("[YouTube] Starting for: %s" % title)

            # Normalize URL (embed / nocookie / shorts / live → watch?v=)
            normalized = convert_youtube_embed_to_watch(url)
            self.logger.info("[YouTube] Normalized: %s" % normalized)

            self.youtube_play_request += 1
            request_id = self.youtube_play_request

            # Feedback in the state label (infobar keeps working)
            if "state" in self:
                self["state"].setText(_("Resolving YouTube stream..."))

            from twisted.internet import threads
            d = threads.deferToThread(resolve_youtube, normalized)
            d.addCallback(self._youtube_resolved, request_id, title)
            d.addErrback(self._youtube_failed, request_id)
            return True
        except Exception as e:
            self.logger.error("[YouTube] playback error: %s" % str(e))
            self.show_error(_("YouTube playback error"))
            return False

    def _youtube_resolved(self, result, request_id, title):
        """Runs on the GUI thread once yt-dlp has finished."""
        if request_id != self.youtube_play_request:
            # A newer request superseded this one — drop stale answer
            self.logger.info("[YouTube] stale answer ignored")
            return

        resolved, error = result
        if resolved:
            self.logger.info("[YouTube] resolved: %s..." % resolved[:80])
            if "state" in self:
                self["state"].setText("")
            self.play_stream(resolved, title)
        else:
            self.logger.error("[YouTube] resolve failed: %s" % error)
            if "state" in self:
                self["state"].setText("")
            msg = _("YouTube stream not available")
            if error:
                msg += "\n\n%s" % error
            if error == "yt-dlp is not installed":
                msg += "\n\n" + _(
                    "Install it with:\nopkg install python3-yt-dlp")
            self.show_error(msg)

    def _youtube_failed(self, failure, request_id):
        msg = "[YouTube] resolver error: %s" % failure
        try:
            self.logger.error(msg)
        except AttributeError:
            print(msg)
        self._youtube_resolved(
            (None, failure.getErrorMessage()), request_id, "")

    def start_service_playback(self, service):
        """Start playback with special handling"""
        if self.session.nav.getCurrentlyPlayingServiceReference():
            self.session.nav.stopService()

        self.session.nav.playService(service)
        self.show()
        self.state = self.STATE_PLAYING
        if self.state == self.STATE_PLAYING:
            self.show_help_overlay()

    def play_stream(self, stream_url, title=""):
        """
        Play a media stream using the best available service type.
        """
        try:
            if isinstance(stream_url, (tuple, list)):
                stream_url = str(stream_url[0])
            else:
                stream_url = str(stream_url)

            self.logger.info("[Player] Final URL: %s..." % stream_url[:200])

            service_type = get_service_type()
            self.logger.info("[Player] service_type=%d" % service_type)

            service = eServiceReference(service_type, 0, stream_url)
            service.setName(title)
            self.start_service_playback(service)
            self.logger.info("[Player] playback started")
        except Exception as e:
            self.logger.error("[Player] error playing stream: %s" % str(e))
            self.show_error(_("Playback failed!"))

    def playpauseService(self):
        """Toggle play/pause"""
        service = self.session.nav.getCurrentService()
        if not service:
            self.logger.warning("No current service")
            return

        pauseable = service.pause()
        if pauseable is None:
            self.logger.warning("Service is not pauseable")
            # Instead of failing, just stop and restart the service
            if self.state == self.STATE_PLAYING:
                current_ref = self.session.nav.getCurrentlyPlayingServiceReference()
                if current_ref:
                    self.session.nav.stopService()
                    self.state = self.STATE_PAUSED
                    self.logger.info("Playback stopped (pause not supported)")
            elif self.state == self.STATE_PAUSED:
                current_ref = self.session.nav.getCurrentlyPlayingServiceReference()
                if current_ref:
                    self.session.nav.playService(current_ref)
                    self.state = self.STATE_PLAYING
                    self.logger.info("Playback resumed (pause not supported)")
            return

        try:
            if self.state == self.STATE_PLAYING:
                if hasattr(pauseable, 'pause'):
                    pauseable.pause()
                    self.state = self.STATE_PAUSED
                    self.logger.info("Playback paused")
            elif self.state == self.STATE_PAUSED:
                if hasattr(pauseable, 'play'):
                    pauseable.play()
                    self.state = self.STATE_PLAYING
                    self.logger.info("Playback resumed")
        except Exception as e:
            self.logger.error("Play/pause error: " + str(e))
            self.show_error(_("Play/pause not supported for this stream"))

    def show_error(self, message):
        """Show error message and close player"""
        self.session.openWithCallback(
            self.close,
            MessageBox,
            message,
            MessageBox.TYPE_ERROR
        )

    def cleanup(self):
        """Cleanup resources on close"""
        if exists('/tmp/hls.avi'):
            try:
                remove('/tmp/hls.avi')
            except BaseException:
                pass

        self.aspect_manager.restore_aspect()
        self.session.nav.stopService()

        if self.srefInit:
            try:
                self.session.nav.playService(self.srefInit)
            except BaseException:
                pass
