# -*- coding: utf-8 -*-
"""Deterministic mapping only; Execution owns ordering and state mutation."""

from datetime import datetime
import hashlib
import json

from jsonschema import Draft202012Validator
from referencing import Registry

from ...contracts import NormalizedJobEvent, ProviderEventEnvelope
from ._models import AsyncToolProtocol


def normalize_event(
    protocol: AsyncToolProtocol,
    envelope: ProviderEventEnvelope,
    *,
    provider_integration_id: str,
    inbox_event_id: str,
    received_at: datetime,
) -> NormalizedJobEvent:
    """Use verified inbox metadata, never provider-supplied identity/time."""
    envelope = ProviderEventEnvelope.model_validate(
        envelope.model_dump(warnings="error"),
        strict=True,
    )
    if protocol.provider_integration_id != provider_integration_id:
        raise PermissionError("provider namespace mismatch")
    if envelope.occurred_at.utcoffset() is None:
        raise ValueError("occurred_at must be timezone-aware")
    if received_at.utcoffset() is None:
        raise ValueError("received_at must be timezone-aware")
    if envelope.schema_version != protocol.event_schema_version:
        raise ValueError("event schema version mismatch")
    if protocol.ordering == "provider_version" and (
        envelope.provider_version is None
    ):
        raise ValueError("provider_version is required")
    # Pydantic's JSON serializer may turn non-finite floats into null.
    json.dumps(envelope.data, allow_nan=False)
    mapping = protocol.event_mappings[envelope.event_type]
    source = json.dumps(
        envelope.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    Draft202012Validator(
        mapping.data_schema,
        registry=Registry(),
    ).validate(envelope.data)
    return NormalizedJobEvent(
        inbox_event_id=inbox_event_id,
        provider_integration_id=provider_integration_id,
        external_event_id=envelope.external_event_id,
        external_job_id=envelope.external_job_id,
        client_reference=envelope.client_reference,
        normalized_status=mapping.status,
        facts={
            key: envelope.data[key]
            for key in mapping.fact_fields
            if key in envelope.data
        },
        provider_version=envelope.provider_version,
        protocol_schema_hash=protocol.snapshot_ref.schema_hash,
        source_hash=hashlib.sha256(source.encode()).hexdigest(),
        occurred_at=envelope.occurred_at,
        received_at=received_at,
    )
