# SPDX-FileCopyrightText: Fabio Forni <development@redaril.me>
# SPDX-License-Identifier: GPL-3.0-or-later

from urllib.parse import urlsplit

from .client import Client, SearchOptions

__all__ = ["Client", "SearchOptions"]


def is_deezer_url(url: str) -> bool:
    return urlsplit(url).hostname in ("deezer.com", "www.deezer.com")
