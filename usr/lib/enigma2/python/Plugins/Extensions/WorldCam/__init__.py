# -*- coding: utf-8 -*-
import gettext
from os import environ
from os.path import join, dirname
from Components.Language import language
from Tools.Directories import resolveFilename, SCOPE_PLUGINS

__author__ = "Lululla"
__email__ = "ekekaz@gmail.com"
__copyright__ = 'Copyright (c) 2024 Lululla'
__license__ = "GPL-v2"
__version__ = "7.1"

PLUGIN_VERSION = __version__
PLUGIN_PATH = dirname(__file__)
DEFAULT_ICON = join(PLUGIN_PATH, "pics/webcam.png")
BASE_URL = "https://www.skylinewebcams.com"

PluginLanguageDomain = 'WorldCam'
PluginLanguagePath = 'Extensions/WorldCam/locale'
# AgentRequest = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.3'
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
