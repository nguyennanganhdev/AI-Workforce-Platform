# -*- coding: utf-8 -*-
"""Execution-owned additive metadata. Foundation owns actual migrations."""

from typing import Any

from sqlalchemy import (
    JSON,
    Column,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    UniqueConstraint,
)

metadata = MetaData()


def _table(
    name: Any, extra: Any = (), constraints: Any = (), scoped: Any = True
) -> Any:
    cols = [Column("id", String(255), primary_key=True)]
    if scoped:
        cols += [
            Column(k, String(255), nullable=False)
            for k in (
                "tenant_id",
                "domain_id",
                "area_id",
                "manager_account_id",
            )
        ]
    cols += list(extra) + [
        Column("revision", Integer, nullable=False, default=1),
        Column("payload", JSON, nullable=False),
    ]
    table = Table(name, metadata, *cols, *constraints)
    if scoped:
        Index(
            name + "_owner",
            table.c.tenant_id,
            table.c.domain_id,
            table.c.area_id,
            table.c.manager_account_id,
        )
    return table


tool_calls = _table(
    "wf_tool_calls",
    [
        Column("run_id", String(255), nullable=False),
        Column("idempotency_key", String(255), nullable=False),
    ],
    [
        UniqueConstraint(
            "tenant_id",
            "domain_id",
            "area_id",
            "manager_account_id",
            "run_id",
            "idempotency_key",
            name="uq_wf_call_key",
        )
    ],
)
approvals = _table(
    "wf_approvals",
    [Column("call_id", String(255), nullable=False)],
    [UniqueConstraint("call_id", name="uq_wf_approval_call")],
)
booking_operations = _table(
    "wf_booking_operations",
    [
        Column("call_id", String(255), nullable=False),
    ],
    [UniqueConstraint("call_id", name="uq_wf_booking_call")],
)
execution_events = _table(
    "wf_execution_events",
    [
        Column("call_id", String(255), nullable=False),
    ],
)
