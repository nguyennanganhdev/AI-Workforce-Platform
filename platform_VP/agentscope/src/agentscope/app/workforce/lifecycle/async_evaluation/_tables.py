"""Additive Lifecycle metadata. DDL is applied by the C7 migration owner."""

from typing import List

from sqlalchemy import (
    Boolean,
    Column,
    Index,
    Integer,
    JSON,
    MetaData,
    String,
    Table,
    false,
)

metadata = MetaData()


def scope_columns() -> List[Column]:
    return [
        Column(name, String(200), primary_key=True)
        for name in ("tenant_id", "domain_id", "area_id", "manager_account_id")
    ]


evaluations = Table(
    "wf_evaluations",
    metadata,
    *scope_columns(),
    Column("evaluation_id", String(200), primary_key=True),
    Column("snapshot_id", String(200), nullable=False),
    Column("content_hash", String(64), nullable=False),
    Column("frozen", JSON, nullable=False),
    Column("record", JSON),
    Column("record_hash", String(64)),
)
case_runs = Table(
    "wf_evaluation_cases",
    metadata,
    *scope_columns(),
    Column("snapshot_id", String(200), primary_key=True),
    Column("case_id", String(200), primary_key=True),
    Column("workflow_id", String(200), nullable=False),
    Column("input_hash", String(64), nullable=False),
    Column("cancelled", Boolean, nullable=False, server_default=false()),
    Column("result", JSON),
    Column("result_hash", String(64)),
)
Index(
    "uq_wf_eval_case_workflow",
    *[
        case_runs.c[name]
        for name in (
            "tenant_id",
            "domain_id",
            "area_id",
            "manager_account_id",
            "workflow_id",
        )
    ],
    unique=True,
)
turn_evidence = Table(
    "wf_evaluation_turn_evidence",
    metadata,
    *scope_columns(),
    Column("workflow_id", String(200), primary_key=True),
    Column("trigger_id", String(200), primary_key=True),
    Column("after_revision", Integer, nullable=False),
    Column("payload", JSON, nullable=False),
    Column("content_hash", String(64), nullable=False),
)
Index(
    "ix_wf_eval_evidence_revision",
    *[
        turn_evidence.c[name]
        for name in (
            "tenant_id",
            "domain_id",
            "area_id",
            "manager_account_id",
            "workflow_id",
            "after_revision",
        )
    ],
)
steps = Table(
    "wf_evaluation_steps",
    metadata,
    *scope_columns(),
    Column("snapshot_id", String(200), primary_key=True),
    Column("case_id", String(200), primary_key=True),
    Column("step_index", Integer, primary_key=True),
    Column("observation", JSON, nullable=False),
    Column("content_hash", String(64), nullable=False),
)


def get_metadata() -> MetaData:
    return metadata
