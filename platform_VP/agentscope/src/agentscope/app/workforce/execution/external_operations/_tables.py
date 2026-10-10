# -*- coding: utf-8 -*-
"""Operation correlation constraints; migration exported to Foundation."""

from sqlalchemy import Column, String, UniqueConstraint
from .._tables import _table

external_operations = _table(
    "wf_external_operations",
    [
        Column("call_id", String(255), nullable=False),
        Column("workflow_id", String(255), nullable=False),
        Column("provider_integration_id", String(255), nullable=False),
        Column("correlation_id", String(255), nullable=False),
        Column("external_job_id", String(255), nullable=True),
    ],
    [
        UniqueConstraint("call_id", name="uq_wf_operation_call"),
        UniqueConstraint("correlation_id", name="uq_wf_correlation"),
        UniqueConstraint(
            "tenant_id",
            "provider_integration_id",
            "external_job_id",
            name="uq_wf_provider_job",
        ),
    ],
)
