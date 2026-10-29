# SPDX-FileCopyrightText: Fabio Forni <development@redaril.me>
# SPDX-License-Identifier: GPL-3.0-or-later

import enum
import json
from collections.abc import Mapping, MutableMapping
from typing import Any, ClassVar


class APIObject:
    """
    Base class from Deezer API objects.
    """

    _fields: ClassVar[tuple[str, ...]] = ()

    def __init__(self, **kwargs):
        if len(self._fields) == 0:
            raise NotImplementedError(
                type(self).__name__ + " cannot have an empty field list"
            )
        for field in self._fields:
            setattr(self, field, kwargs.get(field))

    def __eq__(self, other):
        for field in self._fields:
            if getattr(self, field) != getattr(other, field):
                return False
        return True


class Artist(APIObject):
    """
    The Artist API object.
    """

    name: str

    _fields: ClassVar[tuple[str, ...]] = ("name",)


class CoverSize(enum.StrEnum):
    """
    Cover size selector.
    """

    THUMBNAIL = "small"
    SMALL = ""
    MEDIUM = "medium"
    BIG = "big"
    LARGE = "xl"


class Album(APIObject):
    """
    The Album API object.
    """

    cover: str
    title: str

    _fields: ClassVar[tuple[str, ...]] = ("cover", "title")

    def cover_url(self, cover_size: CoverSize) -> str:
        """
        Get the album cover's URL based on the size wanted.
        """
        return f"{self.cover}?size={cover_size.value}"


class Track(APIObject):
    """
    The Track API object.
    """

    album: Album
    artist: Artist

    _fields: ClassVar[tuple[str, ...]] = ("album", "artist")


def parse_json(data: str | MutableMapping[str, Any]) -> APIObject | None:
    if isinstance(data, str):
        return json.loads(data, object_hook=_dict_to_object)

    def convert_inner(data: MutableMapping[str, Any]) -> APIObject | None:
        """
        Traverse the dictionaries with post-order
        algorithm to convert dict objects in Object instances.
        """
        for k, v in data.items():
            if isinstance(v, MutableMapping):
                data[k] = convert_inner(v)
        return _dict_to_object(data)

    return convert_inner(data)


def _dict_to_object(data: Mapping[str, Any]) -> APIObject | None:
    OBJ_CLASSES = {c.__name__.lower(): c for c in APIObject.__subclasses__()}

    try:
        obj_class_name: str = data["type"]
        obj_class = OBJ_CLASSES[obj_class_name]
    except KeyError:
        return None
    else:
        return obj_class(**data)
