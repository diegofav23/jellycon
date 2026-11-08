from __future__ import (
    division, absolute_import, print_function, unicode_literals
)

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin

from .jellyfin import api
from .lazylogger import LazyLogger
from .utils import image_url, ticks_to_seconds

log = LazyLogger(__name__)

# Content of the video OSD sections of skins (chapters and cast of the playing item),
# used by the Arctic Fuse 3 patch in resources/skins/skin.arctic.fuse.3/osd_jellycon.patch

CAST_TYPES = ("Actor", "GuestStar")


def format_time(seconds):
    seconds = int(seconds)
    hours, rest = divmod(seconds, 3600)
    minutes, seconds = divmod(rest, 60)
    if hours:
        return "%d:%02d:%02d" % (hours, minutes, seconds)
    return "%d:%02d" % (minutes, seconds)


def get_item(item_id, fields):
    url = "/Users/{}/Items/{}?format=json&Fields={}".format(api.user_id, item_id, fields)
    return api.get(url) or {}


def get_osd_chapters(handle, params):
    log.debug("get_osd_chapters Called: {0}".format(params))
    item_id = params.get("id")
    server = xbmcaddon.Addon().getSetting('server_address')

    list_items = []
    if item_id:
        for index, chapter in enumerate(get_item(item_id, "Chapters").get("Chapters") or []):
            start_seconds = ticks_to_seconds(chapter.get("StartPositionTicks", 0))
            list_item = xbmcgui.ListItem(label=chapter.get("Name") or str(index + 1),
                                         label2=format_time(start_seconds), offscreen=True)
            if chapter.get("ImageTag"):
                thumb = image_url(item_id, "Chapter", index, 480, 0, chapter.get("ImageTag"), server)
                list_item.setArt({"thumb": thumb, "landscape": thumb, "icon": thumb})
            list_item.setProperty("start_seconds", str(start_seconds))
            list_items.append(("", list_item, False))

    xbmcplugin.addDirectoryItems(handle, list_items)
    xbmcplugin.endOfDirectory(handle, cacheToDisc=False)


def get_osd_cast(handle, params):
    log.debug("get_osd_cast Called: {0}".format(params))
    item_id = params.get("id")
    # cast or crew, like the cast section toggle of the skin
    crew = params.get("type") == "crew"
    server = xbmcaddon.Addon().getSetting('server_address')

    list_items = []
    if item_id:
        for person in get_item(item_id, "People").get("People") or []:
            if (person.get("Type") in CAST_TYPES) == crew:
                continue
            role = person.get("Type") if crew else person.get("Role")
            list_item = xbmcgui.ListItem(label=person.get("Name", ""), label2=role or "", offscreen=True)
            thumb = "DefaultActor.png"
            if person.get("PrimaryImageTag"):
                thumb = image_url(person.get("Id"), "Primary", 0, 400, 0, person.get("PrimaryImageTag"), server)
            list_item.setArt({"thumb": thumb, "poster": thumb, "icon": thumb})
            list_item.setProperty("id", person.get("Id"))
            list_items.append(("", list_item, False))

    xbmcplugin.addDirectoryItems(handle, list_items)
    xbmcplugin.endOfDirectory(handle, cacheToDisc=False)


def osd_seek(params):
    seconds = params.get("seconds")
    log.debug("osd_seek Called: {0}".format(seconds))
    player = xbmc.Player()
    if seconds and player.isPlaying():
        player.seekTime(float(seconds))
