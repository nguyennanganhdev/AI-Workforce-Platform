# -*- coding: utf-8 -*-
"""Unit tests for PostgreSQL ReMe memory value objects."""

from datetime import datetime, timezone
from unittest import TestCase

from agentscope.middleware import ReMeMemory
from agentscope.middleware._longterm_memory._reme._postgres_store import (
    _vector_literal,
)


class ReMeMemoryTest(TestCase):
    """Validate data before database execution."""

    def test_vector_literal(self) -> None:
        self.assertEqual(_vector_literal([1, 0.25, -2]), "[1,0.25,-2]")

    def test_empty_vector_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            _vector_literal([])

    def test_owner_and_content_are_required(self) -> None:
        with self.assertRaises(ValueError):
            ReMeMemory(
                tenant_id="",
                user_id="user",
                content="fact",
                embedding=[0.0],
                domain_id="vinhomes",
                area_id="ocean-park-1",
                approved_by="manager",
                approved_at=datetime.now(timezone.utc),
                source_candidate_id="candidate",
            )
        with self.assertRaises(ValueError):
            ReMeMemory(
                tenant_id="tenant",
                user_id="user",
                content="   ",
                embedding=[0.0],
                domain_id="vinhomes",
                area_id="ocean-park-1",
                approved_by="manager",
                approved_at=datetime.now(timezone.utc),
                source_candidate_id="candidate",
            )

    def test_unreviewed_memory_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ReMeMemory(
                tenant_id="tenant",
                user_id="manager",
                content="approved business fact",
                embedding=[0.0],
            )

    def test_scores_are_bounded(self) -> None:
        with self.assertRaises(ValueError):
            ReMeMemory(
                tenant_id="tenant",
                user_id="user",
                content="fact",
                embedding=[0.0],
                importance=1.1,
                domain_id="vinhomes",
                area_id="ocean-park-1",
                approved_by="manager",
                approved_at=datetime.now(timezone.utc),
                source_candidate_id="candidate",
            )
