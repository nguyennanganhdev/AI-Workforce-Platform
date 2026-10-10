"""Versioned deterministic business identity, separate from prompt hashing."""

from typing import Any, Dict

from ..contracts import BusinessProfile
from ._models import canonical_hash

BUSINESS_KEY_VERSION = "business-v1"


def normalized_profile(profile: BusinessProfile) -> Dict[str, Any]:
    value = profile.model_dump(mode="json")
    for key in ("objective", "business_scope"):
        value[key] = " ".join(value[key].casefold().split())
    for key in (
        "responsibilities",
        "capabilities",
        "required_constraints",
        "knowledge_requirements",
    ):
        value[key] = sorted(
            set(" ".join(item.casefold().split()) for item in value[key])
        )
    # Capability additions are revisions of one business, not a new identity.
    return value


def business_key(profile: BusinessProfile) -> str:
    value = normalized_profile(profile)
    identity = {
        key: value[key]
        for key in (
            "profile_schema_version",
            "objective",
            "business_scope",
            "input_contract",
            "output_contract",
        )
    }
    return f"{BUSINESS_KEY_VERSION}:{canonical_hash(identity)}"


def covers(existing: BusinessProfile, requirement: BusinessProfile) -> bool:
    left, right = normalized_profile(existing), normalized_profile(requirement)
    return (
        business_key(existing) == business_key(requirement)
        and all(
            set(right[key]).issubset(left[key])
            for key in (
                "capabilities",
                "responsibilities",
                "required_constraints",
                "knowledge_requirements",
            )
        )
        and left["execution_policy"] == right["execution_policy"]
    )
