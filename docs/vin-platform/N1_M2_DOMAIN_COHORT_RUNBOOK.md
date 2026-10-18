# Domain M2 preparation — not enabled

`VINHOMES_CHATBOT_COHORT_CUTOVER_ENABLED` defaults to false; no deployment env has been changed. Operator-owned `VINHOMES_CHATBOT_PLATFORM_COHORTS` is a JSON array, for example:

```json
[{"id":"pilot-a","tenant_id":"11111111-1111-5111-a111-111111111111","resident_ids":["fixture-resident-id"],"platform_url":"https://platform.example.invalid"}]
```

These are verified Domain user IDs, not Platform IDs, emails, request headers or IDs chosen by the browser/model. Exact tenant+resident match selects one cohort. Empty/invalid/overlapping enabled config fails closed with 503; a disabled flag ignores draft config. Redirect target must be HTTPS (HTTP only for loopback tests). Do not put tokens or redirect query strings in config.

GET /resident/intake-policy authenticates the Domain resident and returns mode/cohort_id/platform_url/legacy_new_intake. It does not expose cohort membership. Selected residents receive 409 INTAKE_MOVED_TO_PLATFORM on new chat, new message, direct legacy case/ticket or draft intake. New Reception delegations and new intake operations also check the flag. Idempotent already-accepted operation receipts remain readable. Private Platform customer APIs use their verified link and are not blocked by this legacy intake guard.

History, ticket progress, confirmations and staff app/queue are retained. Flag rollback only reopens intake when explicitly disabled; no data/schema deletion. Turning this flag on does not certify Platform availability or emergency fallback. Before activation, obtain M1/M2 sign-off, verify links/eligibility/quota and the full staff→resident confirmation loop, old ticket updates and emergency support without model/quota. Change a cohort's intake once; do not enable a second chatbot route concurrently.

Domain resident UI can consume intake-policy and show the trusted Platform link; API enforcement remains authoritative even for old tabs/direct requests. This slice prepares the API/guards; deployment activation and final resident UI cutover follow business acceptance. No production flag has been enabled.
