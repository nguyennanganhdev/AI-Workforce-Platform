# -*- coding: utf-8 -*-
"""
Durable inbox in the authenticated provider namespace, before owner lookup.
"""

from sqlalchemy import Column, String, UniqueConstraint
from .._tables import _table

provider_event_inbox = _table(
    "wf_provider_event_inbox",
    [
        Column("tenant_id", String(255), nullable=False),
        Column("provider_integration_id", String(255), nullable=False),
        Column("external_event_id", String(255), nullable=False),
    ],
    [
        UniqueConstraint(
            "tenant_id",
            "provider_integration_id",
            "external_event_id",
            name="uq_wf_provider_event",
        )
    ],
    scoped=False,
)
