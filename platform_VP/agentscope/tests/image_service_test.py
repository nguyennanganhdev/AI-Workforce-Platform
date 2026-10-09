# -*- coding: utf-8 -*-
"""Unit tests for image validation and safe object-key ownership."""
from io import BytesIO
from unittest import TestCase

from agentscope.app.media._image_service import (
    ImageAssetService,
    _detect_image,
    _owner_prefix,
)


class ImageValidationTest(TestCase):
    """Pure validation tests do not require S3 or PostgreSQL."""

    def test_detects_supported_signatures(self) -> None:
        self.assertEqual(_detect_image(b"\xff\xd8\xffrest"), ("image/jpeg", "jpg"))
        self.assertEqual(
            _detect_image(b"\x89PNG\r\n\x1a\nrest"),
            ("image/png", "png"),
        )
        self.assertEqual(
            _detect_image(b"RIFF1234WEBPrest"),
            ("image/webp", "webp"),
        )

    def test_rejects_extension_spoofing(self) -> None:
        with self.assertRaises(ValueError):
            _detect_image(b"not really a picture")

    def test_measure_hash_resets_stream(self) -> None:
        stream = BytesIO(b"\x89PNG\r\n\x1a\ncontent")
        size, checksum, header = ImageAssetService._measure_and_hash(stream)
        self.assertEqual(size, len(stream.getvalue()))
        self.assertEqual(len(checksum), 64)
        self.assertTrue(header.startswith(b"\x89PNG"))
        self.assertEqual(stream.tell(), 0)

    def test_owner_prefix_is_stable_and_path_safe(self) -> None:
        prefix = _owner_prefix("../../tenant", "user/../secret")
        self.assertEqual(prefix, _owner_prefix("../../tenant", "user/../secret"))
        self.assertNotIn("..", prefix)
