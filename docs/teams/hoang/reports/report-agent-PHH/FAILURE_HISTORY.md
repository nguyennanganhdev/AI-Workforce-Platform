# Lịch sử từng test FAIL — Report Agent PHH

Trích từ JUnit XML của các lần chạy. Một case có thể xuất hiện ở nhiều mốc.

Các `KeyError: error` thường do assertion mong structured failure nhưng wrapper trả success;
không tự diễn giải chúng là crash KeyError trong sản phẩm. Xem PROGRESS_REPORT.md để đọc root cause/cách sửa.

## report-before-fixes

`{"tests": 175, "failures": 43, "errors": 0, "skipped": 0, "passed": 132}`

| Case FAIL | Message của assertion/exception | Kết quả cuối cùng |
| --- | --- | --- |
| `server.tests.reporting.tools.test_adversarial::test_unknown_operation_is_sanitized_without_http[operation1]` | TypeError: unhashable type: 'list' | passed |
| `server.tests.reporting.tools.test_adversarial::test_unknown_operation_is_sanitized_without_http[operation2]` | TypeError: unhashable type: 'dict' | passed |
| `server.tests.reporting.tools.test_adversarial::test_all_routes_reject_broken_metadata[missing_meta-get_report_filter_options-args0-/reports/filter-options-fields0]` | KeyError: 'error' | passed |
| `server.tests.reporting.tools.test_adversarial::test_all_routes_reject_broken_metadata[missing_meta-get_employee_performance_summary-args1-/reports/employee-performance-fields1]` | KeyError: 'error' | passed |
| `server.tests.reporting.tools.test_adversarial::test_all_routes_reject_broken_metadata[missing_meta-get_employee_feedback_details-args2-/reports/employee-feedback-fields2]` | KeyError: 'error' | passed |
| `server.tests.reporting.tools.test_adversarial::test_all_routes_reject_broken_metadata[missing_meta-get_repair_revenue_summary-args3-/reports/repair-revenue-fields3]` | KeyError: 'error' | passed |
| `server.tests.reporting.tools.test_adversarial::test_all_routes_reject_broken_metadata[missing_meta-get_incident_frequency_summary-args4-/reports/incident-frequency-summary-fields4]` | KeyError: 'error' | passed |
| `server.tests.reporting.tools.test_adversarial::test_all_routes_reject_broken_metadata[missing_meta-get_report_supporting_records-args5-/reports/supporting-records-fields5]` | KeyError: 'error' | passed |
| `server.tests.reporting.tools.test_adversarial::test_all_routes_reject_broken_metadata[missing_meta-create_report_export-args6-/reports/exports-fields6]` | KeyError: 'error' | passed |
| `server.tests.reporting.tools.test_adversarial::test_all_routes_reject_broken_metadata[missing_meta-get_report_export_status-args7-/reports/exports/55555555-5555-4555-8555-555555555555-fields7]` | KeyError: 'error' | passed |
| `server.tests.reporting.tools.test_adversarial::test_feedback_score_must_be_within_database_scale[0]` | KeyError: 'error' | passed |
| `server.tests.reporting.tools.test_adversarial::test_feedback_score_must_be_within_database_scale[6]` | KeyError: 'error' | passed |
| `server.tests.reporting.tools.test_adversarial::test_employee_average_rating_must_be_within_database_scale[0]` | KeyError: 'error' | passed |
| `server.tests.reporting.tools.test_adversarial::test_employee_average_rating_must_be_within_database_scale[5.1]` | KeyError: 'error' | passed |
| `server.tests.reporting.tools.test_adversarial::test_employee_average_rating_must_be_within_database_scale[999]` | KeyError: 'error' | passed |
| `server.tests.reporting.tools.test_adversarial::test_employee_average_rating_must_be_within_database_scale[6]` | KeyError: 'error' | passed |
| `server.tests.reporting.tools.test_adversarial::test_employee_huge_numeric_does_not_crash_boundary` | OverflowError: int too large to convert to float | passed |
| `server.tests.reporting.tools.test_adversarial::test_employee_identity_is_required[]` | KeyError: 'error' | passed |
| `server.tests.reporting.tools.test_adversarial::test_employee_identity_is_required[not-a-uuid]` | KeyError: 'error' | passed |
| `server.tests.reporting.tools.test_adversarial::test_employee_identity_is_required[ ]` | KeyError: 'error' | passed |
| `server.tests.reporting.tools.test_adversarial::test_bad_money_is_not_reported_as_valid[1e10000]` | KeyError: 'error' | passed |
| `server.tests.reporting.tools.test_adversarial::test_revenue_internal_invariants[change0]` | KeyError: 'error' | passed |
| `server.tests.reporting.tools.test_adversarial::test_revenue_internal_invariants[change1]` | KeyError: 'error' | passed |
| `server.tests.reporting.tools.test_adversarial::test_revenue_internal_invariants[change2]` | KeyError: 'error' | passed |
| `server.tests.reporting.tools.test_adversarial::test_revenue_internal_invariants[change3]` | KeyError: 'error' | passed |
| `server.tests.reporting.tools.test_adversarial::test_pagination_cannot_loop_or_advance_short_page[0-0-0]` | KeyError: 'error' | passed |
| `server.tests.reporting.tools.test_adversarial::test_pagination_cannot_loop_or_advance_short_page[0-50-50]` | KeyError: 'error' | passed |
| `server.tests.reporting.tools.test_adversarial::test_pagination_cannot_loop_or_advance_short_page[1-0-1_0]` | KeyError: 'error' | passed |
| `server.tests.reporting.tools.test_adversarial::test_filter_options_do_not_advertise_invalid_records[categories-value0]` | KeyError: 'error' | passed |
| `server.tests.reporting.tools.test_adversarial::test_filter_options_do_not_advertise_invalid_records[employees-value1]` | KeyError: 'error' | passed |
| `server.tests.reporting.tools.test_adversarial::test_filter_options_do_not_advertise_invalid_records[exportFormats-value2]` | KeyError: 'error' | passed |
| `server.tests.reporting.tools.test_adversarial::test_filter_options_do_not_advertise_invalid_records[buildings-value3]` | KeyError: 'error' | passed |
| `server.tests.reporting.tools.test_adversarial::test_metadata_shape_or_fact_contradiction_is_rejected[facts-value0]` | KeyError: 'error' | passed |
| `server.tests.reporting.tools.test_adversarial::test_metadata_shape_or_fact_contradiction_is_rejected[missingFields-private]` | KeyError: 'error' | passed |
| `server.tests.reporting.tools.test_adversarial::test_metadata_shape_or_fact_contradiction_is_rejected[facts-value2]` | KeyError: 'error' | passed |
| `server.tests.reporting.tools.test_adversarial::test_export_requires_complete_status_fields[downloadUrl]` | KeyError: 'error' | passed |
| `server.tests.reporting.tools.test_adversarial::test_export_requires_complete_status_fields[kind]` | KeyError: 'error' | passed |
| `server.tests.reporting.tools.test_adversarial::test_export_requires_complete_status_fields[execution]` | KeyError: 'error' | passed |
| `server.tests.reporting.tools.test_adversarial::test_total_deadline_covers_slow_transport_and_keeps_write_unknown` | TypeError: ReportBackend.__init__() got an unexpected keyword argument 'operation_timeout_seconds' | passed |
| `server.tests.reporting.tools.test_adversarial::test_invalid_timeout_configuration_fails_cleanly[True]` | Failed: DID NOT RAISE ValueError | passed |
| `server.tests.reporting.tools.test_adversarial::test_invalid_timeout_configuration_fails_cleanly[10]` | TypeError: '<' not supported between instances of 'int' and 'str' | passed |
| `server.tests.reporting.tools.test_adversarial::test_invalid_timeout_configuration_fails_cleanly[None]` | TypeError: '<' not supported between instances of 'int' and 'NoneType' | passed |
| `server.tests.reporting.tools.test_adversarial::test_operation_deadline_cannot_exceed_descriptor_budget` | TypeError: ReportBackend.__init__() got an unexpected keyword argument 'operation_timeout_seconds' | passed |

## report-baseline-corrected

`{"tests": 180, "failures": 40, "errors": 0, "skipped": 0, "passed": 140}`

| Case FAIL | Message của assertion/exception | Kết quả cuối cùng |
| --- | --- | --- |
| `server.tests.reporting.tools.test_adversarial::test_unknown_operation_is_sanitized_without_http[operation1]` | TypeError: unhashable type: 'list' | passed |
| `server.tests.reporting.tools.test_adversarial::test_unknown_operation_is_sanitized_without_http[operation2]` | TypeError: unhashable type: 'dict' | passed |
| `server.tests.reporting.tools.test_adversarial::test_feedback_score_must_be_within_database_scale[0]` | KeyError: 'error' | passed |
| `server.tests.reporting.tools.test_adversarial::test_feedback_score_must_be_within_database_scale[6]` | KeyError: 'error' | passed |
| `server.tests.reporting.tools.test_adversarial::test_employee_average_rating_must_be_within_database_scale[0]` | KeyError: 'error' | passed |
| `server.tests.reporting.tools.test_adversarial::test_employee_average_rating_must_be_within_database_scale[5.1]` | KeyError: 'error' | passed |
| `server.tests.reporting.tools.test_adversarial::test_employee_average_rating_must_be_within_database_scale[999]` | KeyError: 'error' | passed |
| `server.tests.reporting.tools.test_adversarial::test_employee_average_rating_must_be_within_database_scale[6]` | KeyError: 'error' | passed |
| `server.tests.reporting.tools.test_adversarial::test_employee_huge_numeric_does_not_crash_boundary` | OverflowError: int too large to convert to float | passed |
| `server.tests.reporting.tools.test_adversarial::test_employee_identity_is_required[]` | KeyError: 'error' | passed |
| `server.tests.reporting.tools.test_adversarial::test_employee_identity_is_required[not-a-uuid]` | KeyError: 'error' | passed |
| `server.tests.reporting.tools.test_adversarial::test_employee_identity_is_required[ ]` | KeyError: 'error' | passed |
| `server.tests.reporting.tools.test_adversarial::test_bad_money_is_not_reported_as_valid[1e10000]` | KeyError: 'error' | passed |
| `server.tests.reporting.tools.test_adversarial::test_revenue_internal_invariants[change0]` | KeyError: 'error' | passed |
| `server.tests.reporting.tools.test_adversarial::test_revenue_internal_invariants[change1]` | KeyError: 'error' | passed |
| `server.tests.reporting.tools.test_adversarial::test_revenue_internal_invariants[change2]` | KeyError: 'error' | passed |
| `server.tests.reporting.tools.test_adversarial::test_revenue_internal_invariants[change3]` | KeyError: 'error' | passed |
| `server.tests.reporting.tools.test_adversarial::test_pagination_cannot_loop_or_advance_short_page[0-0-0]` | KeyError: 'error' | passed |
| `server.tests.reporting.tools.test_adversarial::test_pagination_cannot_loop_or_advance_short_page[0-50-50]` | KeyError: 'error' | passed |
| `server.tests.reporting.tools.test_adversarial::test_pagination_cannot_loop_or_advance_short_page[1-0-1_0]` | KeyError: 'error' | passed |
| `server.tests.reporting.tools.test_adversarial::test_filter_options_do_not_advertise_invalid_records[categories-value0]` | KeyError: 'error' | passed |
| `server.tests.reporting.tools.test_adversarial::test_filter_options_do_not_advertise_invalid_records[employees-value1]` | KeyError: 'error' | passed |
| `server.tests.reporting.tools.test_adversarial::test_filter_options_do_not_advertise_invalid_records[exportFormats-value2]` | KeyError: 'error' | passed |
| `server.tests.reporting.tools.test_adversarial::test_filter_options_do_not_advertise_invalid_records[buildings-value3]` | KeyError: 'error' | passed |
| `server.tests.reporting.tools.test_adversarial::test_metadata_shape_or_fact_contradiction_is_rejected[facts-value0]` | KeyError: 'error' | passed |
| `server.tests.reporting.tools.test_adversarial::test_metadata_shape_or_fact_contradiction_is_rejected[missingFields-private]` | KeyError: 'error' | passed |
| `server.tests.reporting.tools.test_adversarial::test_metadata_shape_or_fact_contradiction_is_rejected[facts-value2]` | KeyError: 'error' | passed |
| `server.tests.reporting.tools.test_adversarial::test_export_requires_complete_status_fields[downloadUrl]` | KeyError: 'error' | passed |
| `server.tests.reporting.tools.test_adversarial::test_export_requires_complete_status_fields[kind]` | KeyError: 'error' | passed |
| `server.tests.reporting.tools.test_adversarial::test_export_requires_complete_status_fields[execution]` | KeyError: 'error' | passed |
| `server.tests.reporting.tools.test_adversarial::test_total_deadline_covers_slow_transport_and_keeps_write_unknown` | TypeError: ReportBackend.__init__() got an unexpected keyword argument 'operation_timeout_seconds' | passed |
| `server.tests.reporting.tools.test_adversarial::test_invalid_timeout_configuration_fails_cleanly[True]` | Failed: DID NOT RAISE ValueError | passed |
| `server.tests.reporting.tools.test_adversarial::test_invalid_timeout_configuration_fails_cleanly[10]` | TypeError: '<' not supported between instances of 'int' and 'str' | passed |
| `server.tests.reporting.tools.test_adversarial::test_invalid_timeout_configuration_fails_cleanly[None]` | TypeError: '<' not supported between instances of 'int' and 'NoneType' | passed |
| `server.tests.reporting.tools.test_adversarial::test_operation_deadline_cannot_exceed_descriptor_budget` | TypeError: ReportBackend.__init__() got an unexpected keyword argument 'operation_timeout_seconds' | passed |
| `server.tests.reporting.tools.test_adversarial::test_frequency_group_identity_is_not_optional[missing_period]` | KeyError: 'error' | passed |
| `server.tests.reporting.tools.test_adversarial::test_frequency_group_identity_is_not_optional[invalid_period]` | KeyError: 'error' | passed |
| `server.tests.reporting.tools.test_adversarial::test_frequency_group_identity_is_not_optional[missing_category]` | KeyError: 'error' | passed |
| `server.tests.reporting.tools.test_adversarial::test_frequency_group_identity_is_not_optional[duplicate_group]` | KeyError: 'error' | passed |
| `server.tests.reporting.tools.test_adversarial::test_zero_total_with_fake_groups_is_rejected` | KeyError: 'error' | passed |

## report-after-initial-fixes

`{"tests": 180, "failures": 0, "errors": 0, "skipped": 0, "passed": 180}`

Không có case FAIL ở mốc này.

## report-money-before

`{"tests": 3, "failures": 3, "errors": 0, "skipped": 0, "passed": 0}`

| Case FAIL | Message của assertion/exception | Kết quả cuối cùng |
| --- | --- | --- |
| `server.tests.reporting.tools.test_adversarial::test_json_numeric_money_keeps_digits_before_float_conversion` | AssertionError: assert '9007199254740994.0' == '9007199254740993.01'<br>  <br>  - 9007199254740993.01<br>  ?                ^  -<br>  + 9007199254740994.0<br>  ?                ^ | passed |
| `server.tests.reporting.tools.test_adversarial::test_money_strings_follow_json_numeric_syntax[1_000]` | KeyError: 'error' | passed |
| `server.tests.reporting.tools.test_adversarial::test_money_strings_follow_json_numeric_syntax[ 100 ]` | KeyError: 'error' | passed |

## report-boundaries-before

`{"tests": 27, "failures": 2, "errors": 0, "skipped": 0, "passed": 25}`

| Case FAIL | Message của assertion/exception | Kết quả cuối cùng |
| --- | --- | --- |
| `server.tests.reporting.tools.test_boundaries::test_deep_json_cannot_escape_as_recursion_error[1200]` | RecursionError: maximum recursion depth exceeded | passed |
| `server.tests.reporting.tools.test_boundaries::test_numeric_budget_much_larger_than_float_does_not_escape` | OverflowError: int too large to convert to float | passed |

## report-final-tests

`{"tests": 256, "failures": 0, "errors": 0, "skipped": 0, "passed": 256}`

Không có case FAIL ở mốc này.

## report-pre-push-tests

`{"tests": 256, "failures": 0, "errors": 0, "skipped": 0, "passed": 256}`

Không có case FAIL ở mốc này.
