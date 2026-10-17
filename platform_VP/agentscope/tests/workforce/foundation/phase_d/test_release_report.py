"""D7 evidence aggregation must never hide failures or skipped gates."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

SCRIPT = (
    Path(__file__).resolve().parents[4]
    / "scripts/workforce/write_phase_d_report.py"
)
SPEC = spec_from_file_location("write_phase_d_report", SCRIPT)
assert SPEC and SPEC.loader
MODULE = module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _write(path: Path, *, failures=0, errors=0, skipped=0):
    path.write_text(
        f'<testsuite tests="2" failures="{failures}" errors="{errors}" '
        f'skipped="{skipped}" time="1.5"></testsuite>',
        encoding="utf-8",
    )


def test_report_passes_only_without_failure_error_or_skip(tmp_path):
    _write(tmp_path / "foundation.xml")
    report, passed = MODULE.build_report(
        tmp_path, commit="abc123", sandbox_evidence=None
    )
    assert passed
    assert "Automated gate: **PASS**" in report
    assert "NOT_VERIFIED" in report


def test_report_rejects_skipped_gate(tmp_path):
    _write(tmp_path / "e2e.xml", skipped=1)
    report, passed = MODULE.build_report(
        tmp_path, commit="abc123", sandbox_evidence="sandbox ticket TEST-1"
    )
    assert not passed
    assert "Automated gate: **FAIL**" in report
    assert "sandbox ticket TEST-1" in report


def test_report_rejects_missing_required_gate(tmp_path):
    _write(tmp_path / "foundation.xml")
    try:
        MODULE.build_report(
            tmp_path,
            commit="abc123",
            sandbox_evidence=None,
            required_reports=("foundation.xml", "e2e.xml"),
        )
    except ValueError as error:
        assert str(error) == "missing required JUnit reports: e2e.xml"
    else:
        raise AssertionError("missing required D7 evidence must fail")


def test_report_rejects_empty_junit_gate(tmp_path):
    (tmp_path / "builder.xml").write_text(
        '<testsuite tests="0" failures="0" errors="0" skipped="0" />',
        encoding="utf-8",
    )
    report, passed = MODULE.build_report(
        tmp_path,
        commit="abc123",
        sandbox_evidence=None,
        required_reports=("builder.xml",),
    )
    assert not passed
    assert "Empty JUnit reports: **`builder.xml`**" in report
