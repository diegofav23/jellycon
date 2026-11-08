from __future__ import (
    division, absolute_import, print_function, unicode_literals
)

import os
import threading

import xbmc
import xbmcaddon
import xbmcgui

from .dialogs import OsdSectionsDialog
from .lazylogger import LazyLogger
from .utils import image_url, ticks_to_seconds, translate_path

log = LazyLogger(__name__)

# The OSD sections are replaced only on this skin, it is the only one with a JellyCon layout
SKIN_ID = "skin.arctic.fuse.3"
# Skin windows of the video OSD sections
CHAPTERS_WINDOW = "videobookmarks"
CAST_WINDOW = "1141"
CAST_TYPES = ("Actor", "GuestStar")


def format_time(seconds):
    seconds = int(seconds)
    hours, rest = divmod(seconds, 3600)
    minutes, seconds = divmod(rest, 60)
    if hours:
        return "%d:%02d:%02d" % (hours, minutes, seconds)
    return "%d:%02d" % (minutes, seconds)


def get_item_sections(item_id):
    from .jellyfin import api
    url = "/Users/{}/Items/{}?format=json&Fields=Chapters,People".format(api.user_id, item_id)
    item = api.get(url)
    if not item:
        return [], []
    return item.get("Chapters") or [], [person for person in item.get("People") or [] if person.get("Type") in CAST_TYPES]


def build_chapter_items(item_id, chapters, server):
    items = []
    for index, chapter in enumerate(chapters):
        start_seconds = ticks_to_seconds(chapter.get("StartPositionTicks", 0))
        list_item = xbmcgui.ListItem(label=chapter.get("Name") or str(index + 1), label2=format_time(start_seconds), offscreen=True)
        if chapter.get("ImageTag"):
            list_item.setArt({"thumb": image_url(item_id, "Chapter", index, 480, 0, chapter.get("ImageTag"), server)})
        list_item.setProperty("start_seconds", str(start_seconds))
        items.append(list_item)
    return items


def build_cast_items(people, server):
    items = []
    for person in people:
        list_item = xbmcgui.ListItem(label=person.get("Name", ""), label2=person.get("Role") or "", offscreen=True)
        thumb = "DefaultActor.png"
        if person.get("PrimaryImageTag"):
            thumb = image_url(person.get("Id"), "Primary", 0, 300, 0, person.get("PrimaryImageTag"), server)
        list_item.setArt({"thumb": thumb})
        items.append(list_item)
    return items


def get_playing_chapter(chapters, position):
    playing = 0
    for index, chapter in enumerate(chapters):
        if ticks_to_seconds(chapter.get("StartPositionTicks", 0)) <= position:
            playing = index
    return playing


class OsdSectionsService(threading.Thread):
    """
    Replaces the chapters and cast sections of the skin video OSD with the ones from Jellyfin,
    Kodi can not create chapter thumbnails for http streams and the skin loads the cast from TMDb.
    """

    stop_thread = False

    def __init__(self):
        super(OsdSectionsService, self).__init__()
        self.cached_item_id = None
        self.cached_sections = ([], [])

    def run(self):
        from .play_utils import get_playing_data

        settings = xbmcaddon.Addon()
        plugin_path_real = translate_path(os.path.join(settings.getAddonInfo('path')))
        monitor = xbmc.Monitor()

        while not monitor.abortRequested() and not self.stop_thread:
            section = self.get_open_section()
            if section is not None:
                try:
                    play_data = get_playing_data()
                    item_id = play_data.get("item_id")
                    if item_id is not None:
                        self.show_sections(plugin_path_real, item_id, section)
                except Exception as e:
                    log.error("OsdSectionsService: error showing the OSD sections : {0}".format(e))

            if monitor.waitForAbort(0.2):
                break

    @staticmethod
    def get_open_section():
        if xbmc.getSkinDir() != SKIN_ID or not xbmc.Player().isPlayingVideo():
            return None
        if xbmc.getCondVisibility("Window.IsActive({0})".format(CHAPTERS_WINDOW)):
            return "chapters"
        if xbmc.getCondVisibility("Window.IsActive({0})".format(CAST_WINDOW)):
            return "cast"
        return None

    def show_sections(self, plugin_path_real, item_id, section):
        if item_id != self.cached_item_id:
            self.cached_sections = get_item_sections(item_id)
            self.cached_item_id = item_id
        chapters, people = self.cached_sections

        if not chapters and not people:
            # Nothing from Jellyfin, keep the skin section
            return

        server = xbmcaddon.Addon().getSetting('server_address')
        position = xbmc.Player().getTime()

        # Close the skin section and the OSD, the JellyCon dialog takes their place
        xbmc.executebuiltin("Dialog.Close({0},true)".format(CHAPTERS_WINDOW if section == "chapters" else CAST_WINDOW))
        xbmc.executebuiltin("Dialog.Close(videoosd,true)")

        chapter_items = build_chapter_items(item_id, chapters, server)
        playing_chapter = get_playing_chapter(chapters, position)
        if chapter_items:
            chapter_items[playing_chapter].setProperty("playing", "true")

        dialog = OsdSectionsDialog("OsdSectionsDialog.xml", plugin_path_real, "default", "720p")
        dialog.set_sections(chapter_items, build_cast_items(people, server), section, playing_chapter)
        log.debug("OsdSectionsService: showing {0} for {1}".format(section, item_id))
        dialog.doModal()

        if dialog.open_osd:
            xbmc.executebuiltin("ActivateWindow(videoosd)")
        del dialog

    def stop_service(self):
        log.debug("OsdSectionsService Stop Called")
        self.stop_thread = True
