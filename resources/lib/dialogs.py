from __future__ import (
    division, absolute_import, print_function, unicode_literals
)

import xbmcgui
import xbmc
import xbmcaddon


from .jsonrpc import JsonRpc
from .lazylogger import LazyLogger
from .utils import seconds_to_ticks, ticks_to_seconds, translate_string, send_event_notification, get_art_url

log = LazyLogger(__name__)


class BitrateDialog(xbmcgui.WindowXMLDialog):

    slider_control = None
    bitrate_label = None
    initial_bitrate_value = 0
    selected_transcode_value = 0

    def __init__(self, *args, **kwargs):
        log.debug("BitrateDialog: __init__")
        xbmcgui.WindowXML.__init__(self, *args, **kwargs)

    def onInit(self):
        log.debug("ActionMenu: onInit")
        self.action_exitkeys_id = [10, 13]

        self.slider_control = self.getControl(3000)
        self.slider_control.setInt(self.initial_bitrate_value, 400, 100, 15000)

        self.bitrate_label = self.getControl(3030)
        bitrate_label_string = str(self.slider_control.getInt()) + " Kbs"
        self.bitrate_label.setLabel(bitrate_label_string)
        self.getControl(3011).setLabel(translate_string(30314))

    def onFocus(self, control_id):
        pass

    def doAction(self, action_id):
        pass

    def onMessage(self, message):
        log.debug("ActionMenu: onMessage: {0}".format(message))

    def onAction(self, action):

        bitrate_label_string = str(self.slider_control.getInt()) + " Kbs"
        self.bitrate_label.setLabel(bitrate_label_string)

        if action.getId() == 10:  # ACTION_PREVIOUS_MENU
            self.close()
        elif action.getId() == 92:  # ACTION_NAV_BACK
            self.close()
        elif action.getId() == 7:  # ENTER
            self.selected_transcode_value = self.slider_control.getInt()
            self.close()

    def onClick(self, control_id):
        if control_id == 3000:
            log.debug("ActionMenu: Selected Item: {0}".format(control_id))


class ResumeDialog(xbmcgui.WindowXMLDialog):
    resumePlay = -1
    resumeTimeStamp = ""
    action_exitkeys_id = None

    def __init__(self, *args, **kwargs):
        xbmcgui.WindowXMLDialog.__init__(self, *args, **kwargs)
        log.debug("ResumeDialog INITIALISED")

    def onInit(self):
        self.action_exitkeys_id = [10, 13]
        self.getControl(3010).setLabel(self.resumeTimeStamp)
        self.getControl(3011).setLabel(translate_string(30237))

    def onFocus(self, controlId):
        pass

    def doAction(self, actionID):
        pass

    def onClick(self, controlID):

        if controlID == 3010:
            self.resumePlay = 0
            self.close()
        if controlID == 3011:
            self.resumePlay = 1
            self.close()

    def setResumeTime(self, timeStamp):
        self.resumeTimeStamp = timeStamp

    def getResumeAction(self):
        return self.resumePlay


class SafeDeleteDialog(xbmcgui.WindowXMLDialog):

    confirm = False
    message = "Demo Message"
    heading = "Demo Heading"
    action_exitkeys_id = None

    def __init__(self, *args, **kwargs):
        log.debug("SafeDeleteDialog: __init__")
        xbmcgui.WindowXML.__init__(self, *args, **kwargs)

    def onInit(self):
        log.debug("SafeDeleteDialog: onInit")
        self.action_exitkeys_id = [10, 13]

        message_control = self.getControl(3)
        message_control.setText(self.message)

        message_control = self.getControl(4)
        message_control.setLabel(self.heading)

    def onFocus(self, controlId):
        pass

    def doAction(self, actionID):
        pass

    def onMessage(self, message):
        log.debug("SafeDeleteDialog: onMessage: {0}".format(message))

    def onAction(self, action):

        if action.getId() == 10:  # ACTION_PREVIOUS_MENU
            self.close()
        elif action.getId() == 92:  # ACTION_NAV_BACK
            self.close()
        else:
            log.debug("SafeDeleteDialog: onAction: {0}".format(action.getId()))

    def onClick(self, controlID):
        if controlID == 1:
            self.confirm = True
            self.close()
        elif controlID == 2:
            self.confirm = False
            self.close()


# Kodi action ids
ACTION_MOVE_LEFT = 1
ACTION_MOVE_RIGHT = 2
ACTION_MOVE_UP = 3
ACTION_MOVE_DOWN = 4
ACTION_SELECT_ITEM = 7
ACTION_PREVIOUS_MENU = 10
ACTION_SHOW_INFO = 11
ACTION_PAUSE = 12
ACTION_STOP = 13
ACTION_STEP_FORWARD = 20
ACTION_STEP_BACK = 21
ACTION_BIG_STEP_FORWARD = 22
ACTION_BIG_STEP_BACK = 23
ACTION_SHOW_OSD = 24
ACTION_FORWARD = 77
ACTION_REWIND = 78
ACTION_PLAYER_PLAY = 79
ACTION_NAV_BACK = 92
ACTION_SHOW_OSD_SETTINGS = 107
ACTION_PLAYER_PLAYPAUSE = 229

VIDEO_PLAYER_ID = 1

# Seek steps of the Player.Seek json rpc call, the navigation keys are translated
# like the FullscreenVideo section of the default keymap
PLAYER_SEEK_STEPS = {
    ACTION_MOVE_LEFT: "smallbackward",
    ACTION_MOVE_RIGHT: "smallforward",
    ACTION_MOVE_UP: "bigforward",
    ACTION_MOVE_DOWN: "bigbackward",
    ACTION_STEP_FORWARD: "smallforward",
    ACTION_STEP_BACK: "smallbackward",
    ACTION_BIG_STEP_FORWARD: "bigforward",
    ACTION_BIG_STEP_BACK: "bigbackward",
    ACTION_FORWARD: "smallforward",
    ACTION_REWIND: "smallbackward",
}

OSD_ACTIONS = (ACTION_SHOW_INFO, ACTION_SHOW_OSD, ACTION_SHOW_OSD_SETTINGS)


class PlayerOverlayDialog(xbmcgui.WindowXMLDialog):
    """
    Non modal dialog shown on top of the playing video.
    The dialog gets the input focus, so the player actions are forwarded to the player,
    otherwise the playback can not be controlled while the dialog is shown.
    """

    hidden_for_osd = False
    is_visible = False
    # Actions the dialog keeps for its own navigation instead of forwarding them
    navigation_actions = ()
    # Actions that open the OSD instead of being forwarded
    osd_actions = OSD_ACTIONS

    def show(self):
        # Showing an already visible dialog plays its open animation again and makes it flash
        if not self.is_visible:
            self.is_visible = True
            xbmcgui.WindowXMLDialog.show(self)

    def close(self):
        if self.is_visible:
            self.is_visible = False
            xbmcgui.WindowXMLDialog.close(self)

    def doModal(self):
        self.is_visible = True
        xbmcgui.WindowXMLDialog.doModal(self)
        self.is_visible = False

    def forward_player_action(self, action_id):
        player = xbmc.Player()
        if not player.isPlaying() or action_id in self.navigation_actions:
            return False
        if action_id in (ACTION_PAUSE, ACTION_PLAYER_PLAY, ACTION_PLAYER_PLAYPAUSE):
            player.pause()
        elif action_id == ACTION_STOP:
            self.close()
            player.stop()
        elif action_id in self.osd_actions:
            # Hide the dialog so the OSD can take the focus, it is shown again when the OSD closes
            self.hidden_for_osd = True
            self.close()
            xbmc.executebuiltin("ActivateWindow(videoosd)")
        elif action_id in PLAYER_SEEK_STEPS:
            result = JsonRpc("Player.Seek").execute({"playerid": VIDEO_PLAYER_ID, "value": {"step": PLAYER_SEEK_STEPS[action_id]}})
            log.debug("PlayerOverlayDialog: seek {0} : {1}".format(PLAYER_SEEK_STEPS[action_id], result))
        else:
            return False
        return True

    def show_again_after_osd(self):
        if self.hidden_for_osd and not xbmc.getCondVisibility("Window.IsVisible(videoosd)"):
            self.hidden_for_osd = False
            self.show()


class PlayNextDialog(PlayerOverlayDialog):

    action_exitkeys_id = None
    episode_info = None
    play_called = False
    dismissed = False
    countdown_total = None
    mode = "countdown"

    # left and right move between the buttons, up and down open the OSD
    navigation_actions = (ACTION_MOVE_LEFT, ACTION_MOVE_RIGHT, ACTION_SELECT_ITEM)
    osd_actions = OSD_ACTIONS + (ACTION_MOVE_UP, ACTION_MOVE_DOWN)

    def __init__(self, *args, **kwargs):
        log.debug("PlayNextDialog: __init__")
        xbmcgui.WindowXML.__init__(self, *args, **kwargs)

    def onInit(self):
        log.debug("PlayNextDialog: onInit")
        self.action_exitkeys_id = [10, 13]

        index = self.episode_info.get("IndexNumber", -1)
        season = self.episode_info.get("ParentIndexNumber", -1)
        series_name = self.episode_info.get("SeriesName")
        episode_name = self.episode_info.get("Name", "n/a")
        next_epp_name = "S%02dE%02d - %s" % (season, index, episode_name)

        self.setProperty("title", series_name or "")
        self.setProperty("subtitle", next_epp_name)
        self.setProperty("thumb", self.get_thumb())

        series_label = self.getControl(3011)
        series_label.setLabel(series_name)

        series_label = self.getControl(3012)
        series_label.setLabel(next_epp_name)

    def get_thumb(self):
        server = xbmcaddon.Addon().getSetting('server_address')
        thumb = get_art_url(self.episode_info, "Primary", server=server)
        if not thumb:
            thumb = get_art_url(self.episode_info, "Thumb", parent=True, server=server)
        return thumb

    def onFocus(self, control_id):
        pass

    def doAction(self, action_id):
        pass

    def onMessage(self, message):
        log.debug("PlayNextDialog: onMessage: {0}".format(message))

    def onAction(self, action):
        action_id = action.getId()
        if action_id in (ACTION_PREVIOUS_MENU, ACTION_NAV_BACK):
            self.dismiss()
        elif not self.forward_player_action(action_id):
            log.debug("PlayNextDialog: onAction: {0}".format(action_id))

    def onClick(self, control_id):
        if control_id == 3013:
            log.debug("PlayNextDialog: Play Next Episode")
            self.play_next()
        elif control_id == 3014:
            self.dismiss()

    def dismiss(self):
        self.dismissed = True
        self.close()

    def play_next(self):
        if self.play_called:
            return
        self.play_called = True
        self.close()
        next_item_id = self.episode_info.get("Id")
        log.debug("Playing Next Episode: {0}".format(next_item_id))
        play_info = {}
        play_info["item_id"] = next_item_id
        play_info["auto_resume"] = "-1"
        play_info["force_transcode"] = False
        send_event_notification("jellycon_play_action", play_info)

    def is_finished(self):
        return self.play_called or self.dismissed

    def update_countdown(self, seconds):
        seconds = max(0, int(seconds))
        if self.countdown_total is None:
            self.countdown_total = max(1, seconds)
        self.setProperty("countdown", str(seconds))
        try:
            # Countdown progress bar, only some skin layouts have it
            self.getControl(3015).setPercent(100.0 * seconds / self.countdown_total)
        except Exception:
            pass
        self.show_again_after_osd()

    def set_episode_info(self, info):
        self.episode_info = info

    def set_mode(self, mode):
        # "countdown" plays the next episode when it ends, "credits" only offers it during the credits before an epilogue
        self.mode = mode
        self.setProperty("mode", mode)

    def get_play_called(self):
        return self.play_called


class SkipDialog(PlayerOverlayDialog):

    # Only select (skip) and back (dismiss) are kept, the arrows seek like in fullscreen video
    navigation_actions = (ACTION_SELECT_ITEM,)

    action_exitkeys_id = None
    media_id = None
    start = None
    end = None
    segment_type = None

    has_been_dismissed_or_skipped = False

    def __init__(self, *args, **kwargs):
        log.debug("SkipDialog: __init__")
        xbmcgui.WindowXML.__init__(self, *args, **kwargs)

    def onInit(self):
        log.debug("SkipDialog: onInit")
        self.action_exitkeys_id = [10, 13]

    def onFocus(self, control_id):
        pass

    def doAction(self, action_id):
        pass

    def onMessage(self, message):
        log.debug("SkipDialog: onMessage: {0}".format(message))

    def onAction(self, action):
        action_id = action.getId()
        log.debug("SkipDialog: onAction: {0}".format(action_id))
        if action_id in (ACTION_PREVIOUS_MENU, ACTION_NAV_BACK):
            log.debug("SkipDialog: dismissing dialog so it does not open again")
            self.has_been_dismissed_or_skipped = True
            self.close()
        else:
            self.forward_player_action(action_id)

    def onClick(self, control_id):
        log.debug("SkipDialog: onClick: {0}".format(control_id))
        player = xbmc.Player()
        current_ticks = seconds_to_ticks(player.getTime())
        if self.start is not None and self.end is not None and current_ticks >= self.start and current_ticks <= self.end:
            log.debug("SkipDialog: skipping segment because current ticks ({0}) is in range".format(current_ticks))
            # If click during segment, skip it
            player.seekTime(ticks_to_seconds(self.end))
            # mark dialog as skipped to avoid opening again
            self.has_been_dismissed_or_skipped = True
        self.close()

    def set_segment_type(self, segment_type):
        self.segment_type = segment_type
        self.setProperty("segment_type", segment_type)
        self.setProperty("skip_label", translate_string(SKIP_LABELS.get(segment_type, 30690)))

    def show_segment(self):
        if self.hidden_for_osd:
            self.show_again_after_osd()
        else:
            self.show()

    def is_button_shown(self):
        try:
            self.getFocus()
            return True
        except Exception:
            return False


# String ids of the skip button label for each media segment type
SKIP_LABELS = {
    "Intro": 30691,
    "Outro": 30692,
    "Recap": 30693,
    "Preview": 30694,
    "Commercial": 30695,
}


class OsdSectionsDialog(PlayerOverlayDialog):
    """
    Chapters and cast of the playing item, loaded from Jellyfin.
    Replaces the chapters (video bookmarks) and cast sections of the skin video OSD.
    """

    CHAPTERS_LIST = 100
    CAST_LIST = 200

    navigation_actions = (ACTION_MOVE_LEFT, ACTION_MOVE_RIGHT, ACTION_MOVE_UP, ACTION_MOVE_DOWN, ACTION_SELECT_ITEM)
    osd_actions = (ACTION_SHOW_OSD,)

    chapters = None
    cast = None
    focus_section = "chapters"
    playing_chapter = 0
    open_osd = False

    def __init__(self, *args, **kwargs):
        log.debug("OsdSectionsDialog: __init__")
        xbmcgui.WindowXML.__init__(self, *args, **kwargs)

    def set_sections(self, chapters, cast, focus_section, playing_chapter):
        self.chapters = chapters
        self.cast = cast
        self.focus_section = focus_section
        self.playing_chapter = playing_chapter

    def onInit(self):
        log.debug("OsdSectionsDialog: onInit")
        self.setProperty("has_chapters", "true" if self.chapters else "")
        self.setProperty("has_cast", "true" if self.cast else "")

        chapters_list = self.getControl(self.CHAPTERS_LIST)
        chapters_list.reset()
        chapters_list.addItems(self.chapters)
        cast_list = self.getControl(self.CAST_LIST)
        cast_list.reset()
        cast_list.addItems(self.cast)

        if self.chapters and (self.focus_section == "chapters" or not self.cast):
            chapters_list.selectItem(self.playing_chapter)
            self.setFocusId(self.CHAPTERS_LIST)
        elif self.cast:
            self.setFocusId(self.CAST_LIST)

    def onAction(self, action):
        action_id = action.getId()
        focus_id = self.getFocusId()
        if action_id in (ACTION_PREVIOUS_MENU, ACTION_NAV_BACK):
            self.close()
        elif action_id == ACTION_MOVE_UP and (focus_id == self.CHAPTERS_LIST or not self.chapters):
            # Back to the OSD, like moving up from the skin chapters section
            self.open_osd = True
            self.close()
        elif action_id == ACTION_MOVE_UP and focus_id == self.CAST_LIST:
            self.setFocusId(self.CHAPTERS_LIST)
        elif action_id == ACTION_MOVE_DOWN and focus_id == self.CHAPTERS_LIST and self.cast:
            self.setFocusId(self.CAST_LIST)
        elif not self.forward_player_action(action_id):
            log.debug("OsdSectionsDialog: onAction: {0}".format(action_id))

    def onClick(self, control_id):
        if control_id != self.CHAPTERS_LIST:
            return
        item = self.getControl(self.CHAPTERS_LIST).getSelectedItem()
        if item is not None:
            start_seconds = float(item.getProperty("start_seconds") or 0)
            log.debug("OsdSectionsDialog: seek to chapter at {0}".format(start_seconds))
            self.close()
            xbmc.Player().seekTime(start_seconds)
