# SPDX-FileCopyrightText: Fabio Forni <development@redaril.me>
# SPDX-License-Identifier: GPL-3.0-or-later

from itertools import count
from typing import Any, override

from picard.plugin3.api import (
    CoverArtImage,
    CoverArtProvider,
    PluginApi,
    ProviderOptions,
)
from picard.util.astrcmp import astrcmp

from . import deezer
from .deezer import Client, obj
from .options import Ui_Form

DEFAULT_SIMILARITY_THRESHOLD = 0.6


def is_similar(
    str1: str, str2: str, min_similarity: float = DEFAULT_SIMILARITY_THRESHOLD
) -> bool:
    if str1 in str2:
        return True
    return astrcmp(str1.lower(), str2.lower()) >= min_similarity


class OptionsPage(ProviderOptions):
    NAME = "Deezer"
    TITLE = "Deezer"
    _options_ui = Ui_Form

    def load(self):
        for s in obj.CoverSize:
            self.ui.size.addItem(str(s.name).title(), userData=s.value)
        settings = self.api.global_config.setting
        self.ui.size.setCurrentIndex(self.ui.size.findData(settings["deezerart_size"]))
        self.ui.min_similarity.setValue(int(settings["deezerart_min_similarity"] * 100))

    def save(self):
        settings = self.api.global_config.setting
        settings["deezerart_size"] = self.ui.size.currentData()
        settings["deezerart_min_similarity"] = (
            float(self.ui.min_similarity.value()) / 100.0
        )


class Provider(CoverArtProvider):
    NAME = "Deezer"
    OPTIONS = OptionsPage
    _log_prefix = "Deezerart: "

    def __init__(self, coverart):
        super().__init__(coverart)
        self.client = Client(self.api.web_service)
        self._retry_search = False
        self._request_ids = count()
        self._pending_requests = 0
        self._waiting_for_requests = False

    @override
    def queue_images(self):
        urls = []

        def append_deezer_url(url):
            if deezer.is_deezer_url(url):
                urls.append(url)

        self.match_url_relations(["free streaming"], append_deezer_url)
        self._pending_requests = 0
        self._waiting_for_requests = True
        if urls:
            for url in urls:
                self._start_request(
                    "Fetching Deezer album from URL relation",
                    lambda callback, url=url: self.client.obj_from_url(url, callback),
                    self._queue_from_url,
                )
        else:
            self._start_search()
        return self.QueueState.WAIT

    def _start_search(self):
        if not self._retry_search:
            search_opts = self._artist() + ", " + self.metadata["album"]
        else:
            try:
                track = self.release["media"][0]["tracks"][1]["title"]
            except (IndexError, KeyError):
                self.error("cannot find a track name to retry a search. No cover found")
                self._finish_waiting()
                return
            search_opts = self._artist() + ", " + track
        self._start_request(
            "Searching Deezer for album cover",
            lambda callback: self.client.search(search_opts, callback),
            self._queue_from_search,
        )

    def _start_request(self, description, request_factory, callback):
        task_id = f"deezer-{next(self._request_ids)}"
        self._pending_requests += 1

        def on_response(*args):
            try:
                callback(*args)
            finally:
                self.api.complete_album_task(self.album, task_id)
                self._pending_requests -= 1
                if self._pending_requests == 0:
                    self._finish_waiting()

        self.api.add_album_task(
            self.album,
            task_id,
            description,
            request_factory=lambda: request_factory(on_response),
            blocking=True,
        )

    def _finish_waiting(self):
        if self._waiting_for_requests:
            self._waiting_for_requests = False
            self.next_in_queue()

    @override
    def error(self, msg):
        super().error(self._log_prefix + msg)

    def log_debug(self, msg: Any, *args):
        self.api.logger.debug(self._log_prefix + msg, *args)

    def _queue_from_url(self, album: obj.APIObject | None, error):
        if error:
            self.error(f"could not get Deezer API object: {error}")
            return
        if not isinstance(album, obj.Album):
            self.error("API object is not an album")
            return
        cover_url = album.cover_url(
            obj.CoverSize(self.api.global_config.setting["deezerart_size"])
        )
        self.queue_put(CoverArtImage(cover_url))
        self.log_debug("queued cover using a URL relation")

    def _queue_from_search(self, results: list[obj.APIObject], error):
        if error:
            self.error(f"could not fetch search results: {error}")
            return
        if len(results) == 0:
            if self._retry_search:
                self.error("no results found")
                return
            self._retry_search = True
            self._start_search()
            return
        artist = self._artist()
        album = self.metadata["album"]
        settings = self.api.global_config.setting
        min_similarity = settings["deezerart_min_similarity"]
        for result in results:
            if not isinstance(result, obj.Track):
                continue
            if not is_similar(artist, result.artist.name, min_similarity):
                self.log_debug(
                    "artist similarity below threshold: %r ~ %r",
                    artist,
                    result.artist.name,
                )
                continue
            if not is_similar(album, result.album.title, min_similarity):
                self.log_debug(
                    "album similarity below threshold: %r ~ %r",
                    album,
                    result.album.title,
                )
                continue
            cover_url = result.album.cover_url(
                obj.CoverSize(settings["deezerart_size"])
            )
            self.queue_put(CoverArtImage(cover_url))
            self.log_debug("queued cover using a Deezer search")
            return
        self.error("no result matched the criteria")

    def _artist(self) -> str:
        # If there are many artists, we want to search
        # the album in Deezer with just one as keyword.
        # Deezerart may not specify all the artists
        # MusicBrainz does, or it may use different separators.
        return self.metadata.getraw("~albumartists")[0]


def enable(api: PluginApi):
    """Called when plugin is enabled."""
    api.global_config.setting.register_option("deezerart_size", obj.CoverSize.BIG.value)
    api.global_config.setting.register_option(
        "deezerart_min_similarity", DEFAULT_SIMILARITY_THRESHOLD
    )
    api.register_cover_art_provider(Provider)
