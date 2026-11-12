"""Stdlib-only integrity tests for the public W10 browser handover."""
from __future__ import annotations

import re
import unittest
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PAGE = ROOT / "index.html"


class Scan(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids = []
        self.links = []
        self.copy_buttons = []
        self.external_scripts = []
        self.tags = []

    def handle_starttag(self, tag, attrs):
        data = dict(attrs)
        self.tags.append(tag)
        if "id" in data:
            self.ids.append(data["id"])
        if tag == "a":
            self.links.append(data.get("href", ""))
        if tag == "button" and "data-copy" in data:
            self.copy_buttons.append(data["data-copy"])
        if tag == "script" and data.get("src"):
            self.external_scripts.append(data["src"])


class HandoverPortalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.page = PAGE.read_text(encoding="utf-8")
        cls.parsed = Scan()
        cls.parsed.feed(cls.page)

    def test_basic_html_and_landmarks(self):
        self.assertTrue(self.page.startswith("<!doctype html>"))
        self.assertIn('<html lang="en">', self.page)
        for tag in ("header", "main", "nav", "section", "footer"):
            self.assertIn(tag, self.parsed.tags)
        self.assertIn("viewport", self.page)

    def test_ids_unique(self):
        self.assertEqual(len(self.parsed.ids), len(set(self.parsed.ids)))

    def test_every_copy_button_points_to_existing_code(self):
        self.assertGreaterEqual(len(self.parsed.copy_buttons), 3)
        for target in self.parsed.copy_buttons:
            with self.subTest(target=target):
                self.assertIn(target, self.parsed.ids)

    def test_every_link_has_a_real_destination(self):
        self.assertGreaterEqual(len(self.parsed.links), 12)
        for href in self.parsed.links:
            with self.subTest(href=href):
                self.assertTrue(
                    href.startswith("https://") or href.startswith("#"),
                    f"Invalid link target: {href!r}"
                )
                self.assertNotIn("example.com", href)
        for anchor in (x[1:] for x in self.parsed.links if x.startswith("#")):
            self.assertIn(anchor, self.parsed.ids)

    def test_canonical_handover_and_archive_links(self):
        self.assertIn("GBOGEB/orchestration-sandbox/pull/2", self.page)
        self.assertIn("gg_engine_contract/HANDOVER.md", self.page)
        self.assertIn("/dist/gg_engine_w10_source.zip", self.page)
        self.assertIn("/dist/SHA256SUMS.txt", self.page)
        self.assertIn("8af69a99d60ca4fd131cb5827e134099a3e70c34", self.page)

    def test_public_only_no_undisclosed_private_references(self):
        for prohibited in ("GBOGEB/cryoplant-project", "GBOGEB/MINERVA_PID",
                           "private-user-images", "ghp_", "sk-proj-"):
            with self.subTest(prohibited=prohibited):
                self.assertNotIn(prohibited, self.page)

    def test_no_third_party_scripts_or_tracking(self):
        self.assertEqual(self.parsed.external_scripts, [])
        self.assertNotIn("google-analytics.com", self.page)
        self.assertNotIn("gtag(", self.page)

    def test_source_status_not_engineering_authority(self):
        for required in ("SYNTHETIC", "NO OWNER ACCEPTANCE",
                         "DRAFT / CI NOT GREEN", "Copy commands",
                         "W11", "W12", "W13"):
            with self.subTest(required=required):
                self.assertIn(required, self.page)

    def test_copy_fallback_accessibility(self):
        self.assertIn("role=\"status\"", self.page)
        self.assertIn("aria-live=\"polite\"", self.page)
        self.assertIn("navigator.clipboard", self.page)
        self.assertIn("execCommand('copy')", self.page)

    def test_windows_no_cd_demo(self):
        self.assertIn("Join-Path $env:USERPROFILE", self.page)
        self.assertIn("Invoke-WebRequest", self.page)
        self.assertIn("Expand-Archive", self.page)
        self.assertIn("Push-Location", self.page)
        self.assertIn("Pop-Location", self.page)


if __name__ == "__main__":
    unittest.main()
