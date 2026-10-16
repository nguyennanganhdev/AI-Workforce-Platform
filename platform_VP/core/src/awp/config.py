"""Settings read from the environment. Nothing here reads secrets from disk."""
from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Settings:
    db_url: str = "sqlite+aiosqlite:///./awp.db"
    agentscope_db_url: str = "sqlite+aiosqlite:///./agentscope.db"
    workspace_dir: str = "./awp_workspaces"
    # AWP_AUTO_CREATE: build missing tables with create_all at start-up (development, SQLite, tests). In production set it
    # to 0: the tables come from `python -m awp migrate`, and a database that is not at the latest revision stops the start.
    auto_create: bool = True
    # PostgreSQL pool of each of the two engines (awp's tables, AgentScope's storage): connections kept, extra connections
    # allowed under load, seconds a request waits for one, seconds after which a connection is replaced. No effect on SQLite.
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_timeout: float = 30.0
    db_pool_recycle: float = 1800.0
    # AWP_ADMIN_KEYS="key1:tenant;key2:tenant": the only callers of /platform/v1 (profiles, cost, the partner admin
    # API) and of the AgentScope API. Partners use their own keys, created through that admin API.
    admin_keys: dict[str, str] = field(default_factory=dict)
    # AWP_DEV_OPEN=1 lets requests without a key act as tenant "dev". Never in production.
    dev_open: bool = False
    models_file: str | None = None
    # Jev is an optional cheap gate; everything works with it off.
    jev_enabled: bool = False
    jev_model: str = "jev-latest"
    jev_min_support: float = 0.6
    # Cost ceiling per case in USD; 0 disables the ceiling.
    case_budget_usd: float = 0.0
    # Token ceiling per case as a fallback when prices are unknown; 0 disables.
    case_budget_tokens: int = 0
    # A workflow that is `accepted`/`active` with nothing running for this long needs attention (0 = never).
    case_stall_seconds: int = 900
    # A workflow waiting for an outside event with no news for this long needs attention (workforce/expiry.py).
    request_timeout_hours: float = 72.0
    max_challenge_rounds: int = 2
    digest_max_chars: int = 1800
    # ---- Workforce v1 (partner API) ----
    # How long a POST waits for the agent turn before answering 202.
    wf_wait_seconds: float = 25.0
    wf_body_limit: int = 256 * 1024  # bytes, enforced while the body is read
    wf_text_limit: int = 20000  # characters in one message
    wf_rate_per_minute: int = 600  # per API key; 0 disables
    wf_heartbeat_seconds: float = 15.0  # SSE ": heartbeat" comment (contract 9.6)
    wf_revalidate_seconds: float = 30.0  # SSE re-checks key and grant; the contract caps it at 60
    wf_sse_poll_seconds: float = 1.0  # SSE reads the log this often when no wake-up signal arrives
    wf_max_streams: int = 20  # open event streams per API key in one process; 0 disables
    # Fernet key that seals provider signing secrets and MCP headers. Required unless AWP_DEV_OPEN.
    secret_key: str = ""
    approval_ttl_seconds: int = 24 * 3600
    # The engine (slice S3): how long a sent message may go without a turn before it is sent again,
    # how many times a job may fail before the workflow needs attention, and the longest a turn may run.
    wf_ack_seconds: float = 10.0
    wf_job_attempts: int = 3
    wf_turn_timeout_seconds: float = 900.0
    # Retention (contract 12), run by one process of the fleet every `retention_every_seconds` (0: never): events are kept this
    # many days after the workflow closed, provider dedupe rows this many days, the finished jobs and turns of a closed workflow
    # this many days. 0 keeps that kind for ever. The contract's minimums are 90 and 180 days unless agreed otherwise.
    event_retention_days: int = 90
    inbox_retention_days: int = 180
    closed_retention_days: int = 90
    retention_every_seconds: float = 3600.0
    # Partner tools over MCP (slice T1). `mcp_allow_private` lets a route point at a private address
    # (tests, closed networks); the tool list of a server is kept `mcp_list_ttl_seconds`; an answer
    # larger than `mcp_max_response_bytes` is refused; an operation left half done by a crash is
    # picked up after `wf_op_grace_seconds` and one with a status tool is asked every `wf_status_poll_seconds`.
    mcp_allow_private: bool = False
    mcp_list_ttl_seconds: float = 300.0
    mcp_max_response_bytes: int = 256 * 1024
    wf_op_grace_seconds: float = 30.0
    wf_status_poll_seconds: float = 30.0
    # Provider events (slice T2): the signed timestamp may differ from our clock by this much (contract 5.2); an event
    # that matches no operation is kept `wf_quarantine_seconds` before it needs attention; a delta event waiting for
    # its missing predecessor is kept `wf_delta_hold_seconds`; the first delta event of an operation that is not version 1
    # waits `wf_delta_first_seconds` for the earlier ones before it is taken as the start; one integration may have at
    # most `wf_quarantine_max` events waiting for an operation (more are refused with 429).
    wf_provider_skew_seconds: float = 300.0
    wf_quarantine_seconds: float = 3600.0
    wf_delta_hold_seconds: float = 3600.0
    wf_delta_first_seconds: float = 5.0
    wf_quarantine_max: int = 200
    # ---- building and releasing agents (M2, M3) ----
    # AWP_EVAL_GATE: a version is published only after the latest evaluation of that version passed (or with a recorded
    # override). On unless explicitly turned off; turning it off is for a development machine without a model.
    eval_gate: bool = True
    # One evaluation case: the longest it may take, and its budget (as for any case; 0 = no ceiling). A few runs of one
    # tenant at once (each tenant has its own slots: one tenant's runs never queue behind another's).
    eval_case_timeout_seconds: float = 180.0
    eval_case_budget_usd: float = 0.5
    eval_case_budget_tokens: int = 400000
    eval_parallel: int = 2
    # The builder: a `create` whose handles, or handles and mission, overlap an existing agent at or above this (0..1,
    # overlap.py) becomes `reuse`; and how long one answer of the model may take.
    builder_overlap_threshold: float = 0.5
    builder_timeout_seconds: float = 90.0

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "Settings":
        e = os.environ if env is None else env
        admin: dict[str, str] = {}
        for part in filter(None, (e.get("AWP_ADMIN_KEYS") or "").split(";")):
            key, _, tenant = part.partition(":")
            if key and tenant:
                admin[key] = tenant
        return cls(
            db_url=e.get("AWP_DB_URL", cls.db_url),
            agentscope_db_url=e.get("AWP_AGENTSCOPE_DB_URL", cls.agentscope_db_url),
            workspace_dir=e.get("AWP_WORKSPACE_DIR", cls.workspace_dir),
            auto_create=(e.get("AWP_AUTO_CREATE", "1").lower() in {"1", "true", "yes"}),
            db_pool_size=int(e.get("AWP_DB_POOL_SIZE") or cls.db_pool_size),
            db_max_overflow=int(e.get("AWP_DB_MAX_OVERFLOW") or cls.db_max_overflow),
            db_pool_timeout=float(e.get("AWP_DB_POOL_TIMEOUT") or cls.db_pool_timeout),
            db_pool_recycle=float(e.get("AWP_DB_POOL_RECYCLE") or cls.db_pool_recycle),
            admin_keys=admin,
            dev_open=(e.get("AWP_DEV_OPEN", "").lower() in {"1", "true", "yes"}),
            models_file=e.get("AWP_MODELS_FILE") or None,
            jev_enabled=(e.get("AWP_JEV_ENABLED", "").lower() in {"1", "true", "yes"}),
            jev_model=e.get("AWP_JEV_MODEL", cls.jev_model),
            jev_min_support=float(e.get("AWP_JEV_MIN_SUPPORT", cls.jev_min_support)),
            case_budget_usd=float(e.get("AWP_CASE_BUDGET_USD", 0) or 0),
            case_budget_tokens=int(e.get("AWP_CASE_BUDGET_TOKENS", 0) or 0),
            case_stall_seconds=int(e.get("AWP_CASE_STALL_SECONDS", 900) or 0),
            request_timeout_hours=float(e.get("AWP_REQUEST_TIMEOUT_HOURS", 72) or 72),
            max_challenge_rounds=int(e.get("AWP_MAX_CHALLENGE_ROUNDS", 2) or 2),
            digest_max_chars=int(e.get("AWP_DIGEST_MAX_CHARS", 1800) or 1800),
            wf_wait_seconds=float(e.get("AWP_WF_WAIT_SECONDS") or cls.wf_wait_seconds),
            wf_body_limit=int(e.get("AWP_WF_BODY_LIMIT") or cls.wf_body_limit),
            wf_text_limit=int(e.get("AWP_WF_TEXT_LIMIT") or cls.wf_text_limit),
            wf_rate_per_minute=int(e.get("AWP_WF_RATE_PER_MINUTE") or cls.wf_rate_per_minute),
            wf_heartbeat_seconds=float(e.get("AWP_WF_HEARTBEAT_SECONDS") or cls.wf_heartbeat_seconds),
            wf_revalidate_seconds=float(e.get("AWP_WF_REVALIDATE_SECONDS") or cls.wf_revalidate_seconds),
            wf_sse_poll_seconds=float(e.get("AWP_WF_SSE_POLL_SECONDS") or cls.wf_sse_poll_seconds),
            wf_max_streams=int(e.get("AWP_WF_MAX_STREAMS") or cls.wf_max_streams),
            secret_key=e.get("AWP_SECRET_KEY", ""),
            approval_ttl_seconds=int(e.get("AWP_APPROVAL_TTL_SECONDS") or cls.approval_ttl_seconds),
            wf_ack_seconds=float(e.get("AWP_WF_ACK_SECONDS") or cls.wf_ack_seconds),
            wf_job_attempts=int(e.get("AWP_WF_JOB_ATTEMPTS") or cls.wf_job_attempts),
            wf_turn_timeout_seconds=float(e.get("AWP_WF_TURN_TIMEOUT_SECONDS") or cls.wf_turn_timeout_seconds),
            event_retention_days=int(e.get("AWP_EVENT_RETENTION_DAYS") or cls.event_retention_days),
            inbox_retention_days=int(e.get("AWP_INBOX_RETENTION_DAYS") or cls.inbox_retention_days),
            closed_retention_days=int(e.get("AWP_CLOSED_RETENTION_DAYS") or cls.closed_retention_days),
            retention_every_seconds=float(e.get("AWP_RETENTION_EVERY_SECONDS") or cls.retention_every_seconds),
            mcp_allow_private=(e.get("AWP_MCP_ALLOW_PRIVATE", "").lower() in {"1", "true", "yes"}),
            mcp_list_ttl_seconds=float(e.get("AWP_MCP_LIST_TTL_SECONDS") or cls.mcp_list_ttl_seconds),
            mcp_max_response_bytes=int(e.get("AWP_MCP_MAX_RESPONSE_BYTES") or cls.mcp_max_response_bytes),
            wf_op_grace_seconds=float(e.get("AWP_WF_OP_GRACE_SECONDS") or cls.wf_op_grace_seconds),
            wf_status_poll_seconds=float(e.get("AWP_WF_STATUS_POLL_SECONDS") or cls.wf_status_poll_seconds),
            wf_provider_skew_seconds=float(e.get("AWP_WF_PROVIDER_SKEW_SECONDS") or cls.wf_provider_skew_seconds),
            wf_quarantine_seconds=float(e.get("AWP_WF_QUARANTINE_SECONDS") or cls.wf_quarantine_seconds),
            wf_delta_hold_seconds=float(e.get("AWP_WF_DELTA_HOLD_SECONDS") or cls.wf_delta_hold_seconds),
            wf_delta_first_seconds=float(e.get("AWP_WF_DELTA_FIRST_SECONDS") or cls.wf_delta_first_seconds),
            wf_quarantine_max=int(e.get("AWP_WF_QUARANTINE_MAX") or cls.wf_quarantine_max),
            eval_gate=(e.get("AWP_EVAL_GATE", "1").lower() in {"1", "true", "yes"}),
            eval_case_timeout_seconds=float(e.get("AWP_EVAL_CASE_TIMEOUT_SECONDS") or cls.eval_case_timeout_seconds),
            eval_case_budget_usd=float(e.get("AWP_EVAL_CASE_BUDGET_USD") or cls.eval_case_budget_usd),
            eval_case_budget_tokens=int(e.get("AWP_EVAL_CASE_BUDGET_TOKENS") or cls.eval_case_budget_tokens),
            eval_parallel=int(e.get("AWP_EVAL_PARALLEL") or cls.eval_parallel),
            builder_overlap_threshold=float(e.get("AWP_BUILDER_OVERLAP_THRESHOLD") or cls.builder_overlap_threshold),
            builder_timeout_seconds=float(e.get("AWP_BUILDER_TIMEOUT_SECONDS") or cls.builder_timeout_seconds),
        )
