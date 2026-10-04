from copy import deepcopy

import pytest
from helpers import B1, B2, CATALOG, OPTIONS, Z1, Z2, run


def test_list_buildings_and_whole_zone_only():
    result, requests = run("filter_report_scope")
    assert result["outcome"] == "success"
    assert [s["scope_type"] for s in result["data"]] == ["building", "building", "zone"]
    assert result["data"][-1]["building_ids"] == [B1, B2]
    assert [r.url.path for r in requests] == ["/catalogs", "/reports/filter-options"]
    assert all(
        r.method == "GET" and r.headers["Cookie"] == "session=private" for r in requests
    )


@pytest.mark.parametrize(
    "args",
    [
        {"scope_type": "zone", "name": "  sapphire "},
        {"scope_type": "zone", "scope_id": Z1},
        {"scope_type": "building", "scope_id": B1},
    ],
)
def test_select_exact_name_or_id(args):
    result, _ = run("filter_report_scope", args)
    assert len(result["data"]) == 1


@pytest.mark.parametrize("name", ["sepharin", "Zurich", "Sapp", "Sapphire'"])
def test_no_fuzzy_guess_or_hardcoded_area(name):
    result, _ = run("filter_report_scope", {"scope_type": "zone", "name": name})
    assert result["error"] == "REPORT_SCOPE_NOT_FOUND"


def test_partial_grant_lists_single_building_without_whole_zone():
    result, _ = run("filter_report_scope", grants=(B1,))
    assert [s["scope_id"] for s in result["data"]] == [B1]
    result, requests = run(
        "get_repair_bill_summary",
        {
            "scope_type": "zone",
            "scope_id": Z1,
            "from_date": "2026-09-01",
            "to_date": "2026-10-01",
        },
        grants=(B1,),
    )
    assert result["error"] == "REPORT_SCOPE_INCOMPLETE" and len(requests) == 2


def test_backend_revocation_overrides_stale_runtime_grants():
    options = deepcopy(OPTIONS)
    options["buildings"] = []
    result, _ = run("filter_report_scope", options=options)
    assert result["outcome"] == "empty" and result["data"] == []


def test_duplicate_zone_names_require_selection_and_do_not_leak_forbidden_scope():
    catalog = deepcopy(CATALOG)
    catalog["zones"].append({"id": Z2, "name": "Sapphire"})
    catalog["buildings"][1]["zone_id"] = Z2
    result, _ = run(
        "filter_report_scope",
        {"scope_type": "zone", "name": "Sapphire"},
        catalog=catalog,
    )
    assert result["error"] == "REPORT_SCOPE_AMBIGUOUS"
    assert {s["scope_id"] for s in result["candidates"]} == {Z1, Z2}
    result, _ = run(
        "filter_report_scope",
        {"scope_type": "zone", "name": "Sapphire"},
        catalog=catalog,
        grants=(B1,),
    )
    assert len(result["data"]) == 1 and result["data"][0]["scope_id"] == Z1


@pytest.mark.parametrize(
    "mutation",
    [
        "duplicate_zone",
        "duplicate_building",
        "invalid_id",
        "orphan_zone",
        "blank_name",
        "missing_buildings",
        "wrong_metadata",
        "duplicate_allowed",
    ],
)
def test_bad_catalog_or_scope_metadata_fails(mutation):
    catalog, options = deepcopy(CATALOG), deepcopy(OPTIONS)
    if mutation == "duplicate_zone":
        catalog["zones"].append(catalog["zones"][0])
    if mutation == "duplicate_building":
        catalog["buildings"].append(catalog["buildings"][0])
    if mutation == "invalid_id":
        catalog["buildings"][0]["id"] = "bad"
    if mutation == "orphan_zone":
        catalog["buildings"][0]["zone_id"] = Z2
    if mutation == "blank_name":
        catalog["buildings"][0]["name"] = " "
    if mutation == "missing_buildings":
        del catalog["buildings"]
    if mutation == "wrong_metadata":
        options["agentContext"]["operation"] = "other"
    if mutation == "duplicate_allowed":
        options["buildings"].append(options["buildings"][0])
    result, _ = run("filter_report_scope", catalog=catalog, options=options)
    assert result["error"] == "BACKEND_CONTRACT_INVALID"


def test_unzoned_building_is_supported_without_inventing_zone():
    catalog = deepcopy(CATALOG)
    catalog["buildings"][0]["zone_id"] = None
    result, _ = run("filter_report_scope", catalog=catalog)
    assert any(s["scope_id"] == B1 for s in result["data"])
    assert next(s for s in result["data"] if s["scope_id"] == Z1)["building_ids"] == [
        B2
    ]
