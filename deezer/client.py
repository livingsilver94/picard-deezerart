# SPDX-FileCopyrightText: Fabio Forni <development@redaril.me>
# SPDX-License-Identifier: GPL-3.0-or-later

import json
from collections.abc import Callable
from pathlib import PurePosixPath
from typing import NamedTuple
from urllib.parse import urlsplit, urlunsplit

from picard.webservice import PendingRequest, WebService
from PyQt6.QtNetwork import QNetworkReply

from . import obj

HOSTNAME = "api.deezer.com"

RequestError = QNetworkReply.NetworkError | Exception | str | None
SearchCallback = Callable[[list[obj.APIObject], RequestError], None]
APIURLCallback = Callable[[obj.APIObject | None, RequestError], None]


class SearchOptions(NamedTuple):
    """
    Options for the advanced search.
    """

    artist: str = ""
    album: str = ""
    track: str = ""
    label: str = ""

    def __str__(self):
        options = (f'{k}:"{v}"' for k, v in self._asdict().items() if v)
        return " ".join(options)


class Client:
    def __init__(self, webservice: WebService):
        self.webservice = webservice

    def search(
        self, options: str | SearchOptions, callback: SearchCallback
    ) -> PendingRequest:
        def handler(document: bytes, _: QNetworkReply, error: RequestError):
            if error:
                callback([], error)
                return
            try:
                parsed_doc = json.loads(document.decode("utf-8"))
            except json.JSONDecodeError:
                callback([], "Deezer returned invalid JSON")
            else:
                result = []
                if "data" in parsed_doc:
                    result = [
                        item
                        for dct in parsed_doc["data"]
                        if (item := obj.parse_json(dct)) is not None
                    ]
                elif "error" in parsed_doc:
                    error = parsed_doc["error"].get(
                        "message", "Deezer responded with an unknown error"
                    )
                else:
                    error = "Deezer returned an unexpected response"
                callback(result, error)

        return self.webservice.get_url(
            url=f"https://{HOSTNAME}/search",
            queryargs={"q": str(options)},
            parse_response_type=None,
            handler=handler,
        )

    def obj_from_url(self, url: str, callback: APIURLCallback) -> PendingRequest:
        def handler(document: bytes, _: QNetworkReply, error: RequestError):
            if error:
                callback(None, error)
                return
            try:
                deezer_obj = obj.parse_json(document.decode("utf-8"))
            except json.JSONDecodeError:
                deezer_obj = None
            callback(deezer_obj, None)

        return self.webservice.get_url(
            url=_api_url(url),
            parse_response_type=None,
            handler=handler,
        )


def _api_url(url: str) -> str:
    """
    Converts the "user-facing" URL of a Deezer resource
    into its API URL.
    """

    parsed = urlsplit(url)
    return urlunsplit(
        (parsed.scheme, HOSTNAME, _remove_language_path(parsed.path), "", "")
    )


def _remove_language_path(path: str) -> str:
    """
    Removes the trailing language code in a Deezer URL.
    """

    # Deezer uses 2-letter country codes, like /fr/artist/123.
    COUNTRY_CODE_LENGTH = 2

    split = path.split("/", maxsplit=2)
    if len(split) > 1 and len(split[1]) == COUNTRY_CODE_LENGTH:
        return path[COUNTRY_CODE_LENGTH + 1 :]
    return path
