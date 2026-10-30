# SPDX-FileCopyrightText: Fabio Forni <development@redaril.me>
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest

from deezer.client import _api_url, _remove_language_path


class ApiUrlTests(unittest.TestCase):
    def test_converts_resource_urls(self):
        cases = (
            ("https://api.deezer.com/album/123", "https://api.deezer.com/album/123"),
            ("https://deezer.com/artist/789", "https://api.deezer.com/artist/789"),
            ("https://www.deezer.com/fr/track/456", "https://api.deezer.com/track/456"),
            ("https://www.deezer.com/track/456", "https://api.deezer.com/track/456"),
        )
        for url, expected in cases:
            with self.subTest(url=url):
                self.assertEqual(_api_url(url), expected)

    def test_preserves_scheme(self):
        for scheme in ("http", "https"):
            with self.subTest(scheme=scheme):
                self.assertEqual(
                    _api_url(f"{scheme}://www.deezer.com/album/123"),
                    f"{scheme}://api.deezer.com/album/123",
                )

    def test_discards_query_and_fragment(self):
        for suffix in ("?query=param", "?", "#details", "#", "?query=param#details"):
            with self.subTest(suffix=suffix):
                self.assertEqual(
                    _api_url(f"https://www.deezer.com/us/album/123{suffix}"),
                    "https://api.deezer.com/album/123",
                )


class RemoveLanguagePathTests(unittest.TestCase):
    def test_removes_two_letter_language_prefix(self):
        for language in ("us", "fr"):
            with self.subTest(language=language):
                self.assertEqual(
                    _remove_language_path(f"/{language}/album/123"),
                    "/album/123",
                )

    def test_preserves_paths_without_language_prefix(self):
        for path in ("/artist/123", "/track/456", "/", ""):
            with self.subTest(path=path):
                self.assertEqual(_remove_language_path(path), path)

    def test_removes_only_the_leading_language_prefix(self):
        self.assertEqual(_remove_language_path("/us/fr/album/123"), "/fr/album/123")

    def test_preserves_trailing_slash(self):
        self.assertEqual(_remove_language_path("/us/album/123/"), "/album/123/")


if __name__ == "__main__":
    unittest.main()
