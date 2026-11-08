from __future__ import (
    division, absolute_import, print_function, unicode_literals
)

import os
import threading

import xbmc
import xbmcaddon

from .lazylogger import LazyLogger
from .dialogs import PlayNextDialog
from .kodi_utils import HomeWindow
from .utils import translate_path, ticks_to_seconds

log = LazyLogger(__name__)

# Ignore the first seconds of playback, Kodi reports a zero duration until the stream is opened
MIN_PLAY_POSITION = 5
# Content longer than this after the credits is an epilogue (e.g. anime), the next episode must not start at the credits end
EPILOGUE_MIN_SECONDS = 10


def get_outro_segment(item_id):
    from .play_utils import get_media_segments
    try:
        segments = get_media_segments(item_id) or []
    except Exception as e:
        log.error("PlayNextService: could not get media segments : {0}".format(e))
        return None
    for segment in segments:
        if segment.get("Type") == "Outro" and segment.get("StartTicks") is not None:
            return segment
    return None


def kodi_playlist_has_next():
    position = xbmc.getInfoLabel("VideoPlayer.PlaylistPosition")
    length = xbmc.getInfoLabel("VideoPlayer.PlaylistLength")
    try:
        return int(position) < int(length)
    except ValueError:
        return False


class PlayNextService(threading.Thread):

    stop_thread = False
    monitor = None

    def __init__(self, play_monitor):
        super(PlayNextService, self).__init__()
        self.monitor = play_monitor

    def run(self):

        from .play_utils import get_playing_data
        from .intro_skipper_utils import get_setting_skip_start_offset
        settings = xbmcaddon.Addon()
        play_next_trigger_time = int(settings.getSetting('play_next_trigger_time'))
        plugin_path_real = translate_path(os.path.join(settings.getAddonInfo('path')))
        home_window = HomeWindow()

        play_next_dialog = None
        credits_dialog = None
        is_playing = False

        playing_item_id = None
        outro_segment = None

        while not xbmc.Monitor().abortRequested() and not self.stop_thread:

            player = xbmc.Player()
            if player.isPlaying():

                if not is_playing:
                    settings = xbmcaddon.Addon()
                    play_next_trigger_time = int(settings.getSetting('play_next_trigger_time'))
                    log.debug("New play_next_trigger_time value: {0}".format(play_next_trigger_time))
                is_playing = True

                play_data = get_playing_data()
                item_id = play_data.get("item_id")
                next_episode = play_data.get("next_episode")

                if item_id != playing_item_id:
                    # The playing item has changed, reset the play next values
                    if play_next_dialog is not None:
                        play_next_dialog.close()
                        play_next_dialog = None
                    if credits_dialog is not None:
                        credits_dialog.close()
                        credits_dialog = None
                    home_window.clear_property("play_next_dismissed")
                    playing_item_id = item_id
                    outro_segment = None
                    if item_id is not None and next_episode is not None and play_data.get("item_type") == "Episode":
                        outro_segment = get_outro_segment(item_id)
                        log.debug("PlayNextService: outro segment : {0}".format(outro_segment))

                if play_next_trigger_time <= 0 or next_episode is None or play_data.get("item_type") != "Episode":
                    self.wait()
                    continue

                duration = player.getTotalTime()
                position = player.getTime()

                # Kodi reports a zero (or bogus) duration right after playback starts
                if duration <= 0 or position < MIN_PLAY_POSITION or duration < play_next_trigger_time * 2:
                    self.wait()
                    continue

                outro_start = None
                outro_end = None
                if outro_segment is not None:
                    outro_start = (ticks_to_seconds(outro_segment.get("StartTicks")) +
                                   get_setting_skip_start_offset("Outro"))
                    outro_end = duration
                    if outro_segment.get("EndTicks") is not None:
                        outro_end = min(duration, ticks_to_seconds(outro_segment.get("EndTicks")))
                has_epilogue = outro_end is not None and duration - outro_end > EPILOGUE_MIN_SECONDS

                if has_epilogue:
                    # During the credits offer to skip them to the epilogue, without auto playing the next episode
                    if outro_start <= position < outro_end:
                        if credits_dialog is None:
                            log.debug("PlayNextService: credits with epilogue, showing next episode without countdown")
                            home_window.set_property("play_next_handled", item_id)
                            credits_dialog = self.create_dialog(plugin_path_real, next_episode, "credits")
                            credits_dialog.show()
                        elif not credits_dialog.is_finished():
                            credits_dialog.show_again_after_osd()
                    elif credits_dialog is not None:
                        credits_dialog.close()
                        if position < outro_start:
                            # Seeked back before the credits, offer it again
                            credits_dialog = None
                            home_window.clear_property("play_next_dismissed")

                # Once the dialog is closed the skip service shows its skip credits button
                for dialog in (credits_dialog, play_next_dialog):
                    if dialog is not None and dialog.dismissed:
                        home_window.set_property("play_next_dismissed", item_id)

                if outro_segment is not None and not has_epilogue:
                    trigger_position = outro_start
                    end_position = outro_end
                else:
                    trigger_position = duration - play_next_trigger_time
                    if has_epilogue:
                        trigger_position = max(trigger_position, outro_end)
                    end_position = duration

                if position < trigger_position:
                    # Not yet at the trigger point, or the user seeked back before it
                    if play_next_dialog is not None:
                        log.debug("PlayNextService: position before trigger point, closing dialog")
                        play_next_dialog.close()
                        play_next_dialog = None
                        if not has_epilogue:
                            home_window.clear_property("play_next_dismissed")
                    self.wait()
                    continue

                if play_next_dialog is None:
                    log.debug("play_next_triggered hit at {0} seconds from end".format(duration - position))
                    # The stop prompt for this item is handled here, do not show it again when playback ends
                    home_window.set_property("play_next_handled", item_id)

                    play_next_dialog = self.create_dialog(plugin_path_real, next_episode, "countdown")
                    play_next_dialog.update_countdown(end_position - position)
                    play_next_dialog.show()

                elif not play_next_dialog.is_finished():
                    countdown = end_position - position
                    play_next_dialog.update_countdown(countdown)
                    if countdown <= 1:
                        if kodi_playlist_has_next():
                            log.debug("PlayNextService: Kodi playlist has a next item, not auto playing")
                            play_next_dialog.close()
                        else:
                            log.debug("PlayNextService: countdown finished, playing next episode")
                            play_next_dialog.play_next()

            else:
                if play_next_dialog is not None:
                    if not play_next_dialog.is_finished() and not kodi_playlist_has_next():
                        # Playback ended while the dialog was still counting down
                        log.debug("PlayNextService: playback ended, playing next episode")
                        play_next_dialog.play_next()
                    else:
                        play_next_dialog.close()
                    play_next_dialog = None
                if credits_dialog is not None:
                    credits_dialog.close()
                    credits_dialog = None

                is_playing = False
                playing_item_id = None
                outro_segment = None

            self.wait()

    @staticmethod
    def create_dialog(plugin_path_real, next_episode, mode):
        dialog = PlayNextDialog("PlayNextDialog.xml", plugin_path_real, "default", "720p")
        dialog.set_episode_info(next_episode)
        dialog.set_mode(mode)
        return dialog

    def wait(self):
        if xbmc.Monitor().waitForAbort(1):
            self.stop_thread = True

    def stop_service(self):
        log.debug("PlayNextService Stop Called")
        self.stop_thread = True
