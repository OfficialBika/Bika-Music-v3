from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from music_api.service import (
    AUDIO_EXTENSIONS,
    normalise_query,
    scan_audio_files,
    sign_source,
    track_id_for,
    verify_source_signature,
)


class MusicAPISafetyTests(unittest.TestCase):
    def test_query_normalisation_keeps_unicode_letters(self) -> None:
        self.assertEqual(normalise_query("  Shape   Of the World  "), "shape of the world")
        self.assertEqual(normalise_query("  မြန်မာ   သီချင်း "), "မြန်မာ သီချင်း")

    def test_signature_accepts_valid_unexpired_url(self) -> None:
        secret = "s" * 48
        track_id = "a" * 24
        now = 1_800_000_000
        expires = now + 3600
        signature = sign_source(track_id, expires, secret)
        self.assertTrue(
            verify_source_signature(track_id, str(expires), signature, secret, now=now)
        )

    def test_signature_rejects_expired_or_modified_url(self) -> None:
        secret = "s" * 48
        track_id = "b" * 24
        now = 1_800_000_000
        expires = now + 3600
        signature = sign_source(track_id, expires, secret)
        self.assertFalse(
            verify_source_signature(track_id, str(now), signature, secret, now=now)
        )
        self.assertFalse(
            verify_source_signature(track_id, str(expires), signature + "x", secret, now=now)
        )
        self.assertFalse(
            verify_source_signature("../etc/passwd", str(expires), signature, secret, now=now)
        )

    def test_catalog_scans_audio_only_and_generates_opaque_ids(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            song = root / "Track One.mp3"
            song.write_bytes(b"fake audio fixture")
            (root / "notes.txt").write_text("not audio", encoding="utf-8")
            nested = root / "album"
            nested.mkdir()
            second = nested / "Track Two.flac"
            second.write_bytes(b"fake audio fixture")
            files = scan_audio_files(root)
            self.assertEqual(set(files), {song, second})
            self.assertIn(song.suffix, AUDIO_EXTENSIONS)
            self.assertEqual(track_id_for(song, root), track_id_for(song, root))
            self.assertNotIn("Track One", track_id_for(song, root))


if __name__ == "__main__":
    unittest.main()
