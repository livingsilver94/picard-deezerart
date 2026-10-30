<!--
SPDX-FileCopyrightText: Fabio Forni <development@redaril.me>
SPDX-License-Identifier: GPL-3.0-or-later
-->

# Deezerart

A [MusicBrainz Picard](https://picard.musicbrainz.org/) plugin that downloads
album cover art from Deezer, using the following lookup order:

1. Uses Deezer album links attached to MusicBrainz releases, if available.
1. If not, it searches Deezer using the album artist and title, checking the
similarity of artist and album names before choosing a cover.
1. If the search returns no results, it retries using the album artist and the track title.

## Installation

In Picard's plugin settings, search for "Deezerart" and simply install it.

## Configuration

To use Deezerart, enable it as a cover art provider in Picard's "Cover Art" settings.

You may customize Deezerart even further from the dedicated configuration page in Picard options. You can choose the cover art size you prefer, and the minimum similarity threshold when it searches Deezer for music releases.

## Acknowledgements

This is a port of Deezerart from old Picard's plugin API to APIv3. Thank you to all contributors that
[helped maintaining](https://github.com/metabrainz/picard-plugins/tree/2.0/plugins/deezerart) Deezerart in the past.
