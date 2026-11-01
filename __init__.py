# SPDX-FileCopyrightText: Fabio Forni <development@redaril.me>
# SPDX-License-Identifier: GPL-3.0-or-later

from enum import Enum
from functools import partial
from typing import Any, override

from picard.plugin3.api import (
    CoverArtImage,
    CoverArtProvider,
    PluginApi,
    ProviderOptions,
    t_,
)
from picard.util.astrcmp import astrcmp
from picard.webservice import PendingRequest

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
            self.ui.size.addItem(self.api.tr(s.tr()), userData=s.value)
        settings = self.api.global_config.setting
        self.ui.size.setCurrentIndex(self.ui.size.findData(settings["deezerart_size"]))
        self.ui.min_similarity.setValue(int(settings["deezerart_min_similarity"] * 100))

    def save(self):
        settings = self.api.global_config.setting
        settings["deezerart_size"] = self.ui.size.currentData()
        settings["deezerart_min_similarity"] = (
            float(self.ui.min_similarity.value()) / 100.0
        )


class Error(Enum):
    NETWORK = t_(
        "error.network",
        "could not get Deezer API object: {reason}",
    )
    WRONG_OBJECT = t_(
        "error.wrong_api_object", 'the API object received is not "{expected}"'
    )
    NO_RESULTS = t_("error.no_results", "no results found")


class Provider(CoverArtProvider):
    NAME = "Deezer"
    TITLE = "Deezer"
    OPTIONS = OptionsPage

    LOG_PREFIX = "Deezerart: "

    def __init__(self, coverart):
        super().__init__(coverart)
        self.client = Client(self.api.web_service)
        self._retry_search = False

    @override
    def queue_images(self):
        urls = []

        def append_deezer_url(url: str):
            if deezer.is_deezer_url(url):
                urls.append(url)

        self.match_url_relations(["free streaming"], append_deezer_url)
        if urls:
            for url in urls:
                self._fetch_from_url(url)
        else:
            self._fetch_by_searching()
        return self.QueueState.WAIT

    def _fetch_from_url(self, url: str):
        def on_response(album: obj.APIObject | None, error):
            try:
                if error:
                    self._error(
                        Error.NETWORK,
                        reason=error,
                    )
                    return
                if not isinstance(album, obj.Album):
                    self._error(Error.WRONG_OBJECT, expected="album")
                    return
                cover_url = album.cover_url(
                    obj.CoverSize(self.api.global_config.setting["deezerart_size"])
                )
                self.queue_put(CoverArtImage(cover_url))
                self.log_debug("queued cover using a URL relation")
            finally:
                self.next_in_queue()

        self._start_request(
            "Fetching Deezer album from URL relation",
            partial(self.client.obj_from_url, url),
            on_response,
        )

    def _fetch_by_searching(self):
        def on_response(results: list[obj.APIObject], error):
            if error:
                self._error(
                    Error.NETWORK,
                    reason=error,
                )
                self.next_in_queue()
                return
            if len(results) == 0:
                if self._retry_search:
                    self._error(Error.NO_RESULTS)
                    self.next_in_queue()
                    return
                self._retry_search = True
                self._fetch_by_searching()
                return
            album = self.metadata["album"]
            min_similarity = self.api.global_config.setting["deezerart_min_similarity"]
            for result in results:
                if not isinstance(result, obj.Track):
                    continue
                if not is_similar(self._artist(), result.artist.name, min_similarity):
                    self.log_debug(
                        "artist similarity below threshold: %r ~ %r",
                        self._artist(),
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
                    obj.CoverSize(self.api.global_config.setting["deezerart_size"])
                )
                self.queue_put(CoverArtImage(cover_url))
                self.log_debug("queued cover using a Deezer search")
                self.next_in_queue()
                return
            self._error(Error.NO_RESULTS)
            self.next_in_queue()

        if not self._retry_search:
            search_opts = self._artist() + ", " + self.metadata["album"]
        else:
            try:
                track = self.release["media"][0]["tracks"][1]["title"]
            except (IndexError, KeyError):
                self.log_debug(
                    "cannot find a track name to retry a search. No cover found"
                )
                self._error(Error.NO_RESULTS)
                self.next_in_queue()
                return
            search_opts = self._artist() + ", " + track

        self._start_request(
            "Searching Deezer for album cover",
            partial(self.client.search, str(search_opts)),
            on_response,
        )

    def _start_request(
        self,
        description: str,
        factory,
        callback,
    ) -> None:
        task_id = self.metadata["musicbrainz_releasegroupid"]

        def on_response(*args: Any, **kwargs: Any):
            try:
                callback(*args, **kwargs)
            finally:
                self.api.complete_album_task(self.album, task_id)

        def create_request() -> PendingRequest:
            return factory(on_response)

        self.api.add_album_task(
            self.album,
            task_id,
            description,
            request_factory=create_request,
        )

    def log_debug(self, msg: Any, *args):
        self.api.logger.debug(self.LOG_PREFIX + msg, *args)

    def _error(self, err: Error, **kwargs: Any) -> None:
        self.error(self.LOG_PREFIX + self.api.tr(err.value, **kwargs))

    def _artist(self) -> str:
        # If there are many artists, we want to search
        # the album in Deezer with just one as keyword.
        # Deezer may not list all the artists
        # MusicBrainz does, or it may use different separators.
        return self.metadata.getraw("~albumartists")[0]


def enable(api: PluginApi):
    """Called when plugin is enabled."""
    api.global_config.setting.register_option("deezerart_size", obj.CoverSize.BIG.value)
    api.global_config.setting.register_option(
        "deezerart_min_similarity", DEFAULT_SIMILARITY_THRESHOLD
    )
    api.register_cover_art_provider(Provider)
