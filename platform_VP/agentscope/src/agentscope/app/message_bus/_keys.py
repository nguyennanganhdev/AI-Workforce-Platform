# -*- coding: utf-8 -*-
"""Centralised registry of message-bus key/namespace conventions used
by application-layer services.

:class:`~agentscope.app.message_bus.MessageBus` itself stays
domain-agnostic — it exposes only generic primitives
(``publish`` / ``subscribe`` / ``queue_*`` / ``log_*`` / ``registry_*``
/ ``acquire_lock``). All business-specific key formats live here so
they can be audited, migrated, and (eventually) ported off from the
current scattered ``_BASE_…_KEY`` constants on ``MessageBus``.

Add new business keys here as needed. As legacy keys are migrated off
``MessageBus``, they should move into this class as well.
"""

from typing import Final


class MessageBusKeys:  # pylint: disable=too-many-public-methods
    """Application-layer key conventions for the message bus.

    A flat registry of key/namespace builders — it grows one method per
    business key, so the public-method count is expected to be high.
    """

    # ------------------------------------------------------------------
    # Run-trigger queue — the discriminator carried by each entry on the
    # shared trigger queue, telling the dispatcher how to spawn the run.
    # Centralised here (rather than on ``MessageBus``) so the bus stays
    # free of business vocabulary.
    # ------------------------------------------------------------------

    WAKEUP_KIND_WAKE: Final = "wake"
    """Trigger kind: wake an *idle* session to drain pending inbox
    content. The dispatcher spawns the run with ``input_msg=None`` and
    skips the session entirely while it is already running."""

    WAKEUP_KIND_RESUME: Final = "resume"
    """Trigger kind: resume a session parked on an awaiting tool call by
    feeding it a human-in-the-loop result. The dispatcher spawns the run
    with the carried ``input`` event and — unlike ``wake`` — must *not*
    drop the entry while the session is running; it re-queues until the
    parked run releases its lock."""

    WAKEUP_KIND_MESSAGE: Final = "message"
    """Trigger kind: start a new turn from a genuine user ``Msg`` (e.g. an
    inbound channel message). The dispatcher spawns the run with the
    carried message as ``input_msg`` so it is persisted and reasoned over
    as a real user turn. Like ``resume`` (and unlike ``wake``) it carries
    input, so it is re-queued rather than dropped while the session is
    running."""

    # ------------------------------------------------------------------
    # Team turn ownership. One compact value controls who may answer the
    # customer and whether background workers may be woken.
    # ------------------------------------------------------------------

    _TEAM_TURN_NS = "agentscope:team:turn:{team_id}"
    _TEAM_TURN_LOCK = "agentscope:team:turn:lock:{team_id}"
    TEAM_TURN_FIELD: Final = "state"
    TEAM_TURN_TTL_SECS: Final = 86_400
    TEAM_TURN_LOCK_TTL_SECS: Final = 10

    @classmethod
    def team_turn(cls, team_id: str) -> str:
        """Registry namespace holding one team's current turn state."""
        return cls._TEAM_TURN_NS.format(team_id=team_id)

    @classmethod
    def team_turn_lock(cls, team_id: str) -> str:
        """Lock serialising question dedupe and turn transitions."""
        return cls._TEAM_TURN_LOCK.format(team_id=team_id)

    # ------------------------------------------------------------------
    # Durable shared context coordination. The data itself lives in the
    # configured StorageBase backend; the bus only serialises writers and
    # carries short-lived per-session handoff directives.
    # ------------------------------------------------------------------

    _TEAM_SHARED_CONTEXT_LOCK = "agentscope:team:shared_context:lock:{team_id}"
    _TEAM_HISTORY_BOOTSTRAP_LOCK = (
        "agentscope:team:shared_context:bootstrap:lock:{team_id}"
    )
    _TEAM_SUMMARY_LOCK = "agentscope:team:summary:lock:{team_id}:{task_id}"
    _TEAM_CONTEXT_DIRECTIVES_NS = "agentscope:team:context:{session_id}"
    _TEAM_HANDOFF_DELIVERY_NS = "agentscope:team:handoff:{handoff_id}"
    _TEAM_SESSION_CONTEXT_NS = "agentscope:team:session_context:{session_id}"
    _TEAM_HANDOFF_DELIVERY_LOCK = (
        "agentscope:team:handoff:lock:{handoff_id}:{session_id}"
    )
    TEAM_SHARED_CONTEXT_LOCK_TTL_SECS: Final = 30
    TEAM_HISTORY_BOOTSTRAP_LOCK_TTL_SECS: Final = 60
    TEAM_CONTEXT_DIRECTIVE_TTL_SECS: Final = 86_400
    TEAM_HANDOFF_DELIVERY_TTL_SECS: Final = 604_800
    TEAM_HANDOFF_DELIVERY_LOCK_TTL_SECS: Final = 30
    TEAM_SESSION_CONTEXT_TTL_SECS: Final = 86_400

    @classmethod
    def team_shared_context_lock(cls, team_id: str) -> str:
        """Lock serialising one team's shared-context revisions."""
        return cls._TEAM_SHARED_CONTEXT_LOCK.format(team_id=team_id)

    @classmethod
    def team_history_bootstrap_lock(cls, team_id: str) -> str:
        """Lock the whole one-time customer-history projection."""

        return cls._TEAM_HISTORY_BOOTSTRAP_LOCK.format(team_id=team_id)

    @classmethod
    def team_summary_lock(cls, team_id: str, task_id: str) -> str:
        """Serialise compaction without blocking shared-context appends."""
        return cls._TEAM_SUMMARY_LOCK.format(team_id=team_id, task_id=task_id)

    @classmethod
    def team_context_directives(cls, session_id: str) -> str:
        """Pending context-mode directives for one target session."""
        return cls._TEAM_CONTEXT_DIRECTIVES_NS.format(session_id=session_id)

    @classmethod
    def team_handoff_delivery(cls, handoff_id: str) -> str:
        """Recipient delivery markers for an idempotent team handoff."""
        return cls._TEAM_HANDOFF_DELIVERY_NS.format(handoff_id=handoff_id)

    @classmethod
    def team_session_context(cls, session_id: str) -> str:
        """Last context revision actually prepared for one agent session."""

        return cls._TEAM_SESSION_CONTEXT_NS.format(session_id=session_id)

    @classmethod
    def team_handoff_delivery_lock(
        cls,
        handoff_id: str,
        session_id: str,
    ) -> str:
        """Serialise retry delivery of one handoff to one recipient."""
        return cls._TEAM_HANDOFF_DELIVERY_LOCK.format(
            handoff_id=handoff_id,
            session_id=session_id,
        )

    # ------------------------------------------------------------------
    # Cross-session UI projection — a generic per-session Redis-hash
    # store onto which one session can project UI cards owned by another
    # (e.g. a team member's pending HITL request projected onto its
    # leader). The ``kind`` prefix on each field lets a single target
    # session carry several independent projection feeds without key
    # collisions, so new projection features reuse this store rather
    # than minting their own.
    # ------------------------------------------------------------------

    _PROJECTION_NS = "agentscope:session:projection:{sid}"
    """Redis-hash namespace key template (per *target* session id)."""

    @classmethod
    def projection_namespace(cls, target_session_id: str) -> str:
        """Return the registry namespace for a session's projections.

        Args:
            target_session_id (`str`):
                The session the entries are projected onto (the session
                whose UI renders them).

        Returns:
            `str`:
                The Redis-hash namespace key.
        """
        return cls._PROJECTION_NS.format(sid=target_session_id)

    @staticmethod
    def projection_field(kind: str, entry_id: str) -> str:
        """Return the hash field key for a single projected entry.

        The ``kind`` prefix namespaces the field so different projection
        feeds sharing one target session never collide, and so a feed
        can be listed/purged by scanning for its prefix.

        Args:
            kind (`str`):
                The projection feed this entry belongs to (e.g.
                ``"subagent_hitl"``).
            entry_id (`str`):
                The entry's identity within the feed, unique per
                ``kind`` (e.g. ``"{worker_session_id}:{reply_id}"``).

        Returns:
            `str`:
                The hash field key, ``"{kind}:{entry_id}"``.
        """
        return f"{kind}:{entry_id}"

    @staticmethod
    def projection_field_prefix(kind: str) -> str:
        """Return the field-key prefix that identifies one feed.

        Used to filter :meth:`MessageBus.registry_getall` down to a
        single ``kind`` when listing or purging.

        Args:
            kind (`str`):
                The projection feed.

        Returns:
            `str`:
                The field-key prefix, ``"{kind}:"``.
        """
        return f"{kind}:"

    # ------------------------------------------------------------------
    # Session event stream (replay log + live pub/sub)
    # ------------------------------------------------------------------

    _SESSION_EVENTS = "agentscope:session:events:{sid}"

    SESSION_REPLAY_MAX_LEN = 1000
    """Replay log length cap; older events are trimmed on append."""

    @classmethod
    def session_events(cls, session_id: str) -> str:
        """Replay log + live pub/sub channel key for a session."""
        return cls._SESSION_EVENTS.format(sid=session_id)

    # ------------------------------------------------------------------
    # Session run lock
    # ------------------------------------------------------------------

    _SESSION_LOCK = "agentscope:session:lock:{sid}"

    SESSION_RUN_TTL_SECS = 600
    """Default lock lease for a chat run (10 minutes)."""

    @classmethod
    def session_lock(cls, session_id: str) -> str:
        """Per-session distributed-lock key."""
        return cls._SESSION_LOCK.format(sid=session_id)

    # ------------------------------------------------------------------
    # SOP run lock
    # ------------------------------------------------------------------

    _SOP_LOCK = "agentscope:sop:lock:{sid}"

    @classmethod
    def sop_lock(cls, sop_id: str) -> str:
        """Per-procedure lock, held while a run is opened or the procedure
        deleted. Outermost of the three: procedure, run, session."""
        return cls._SOP_LOCK.format(sid=sop_id)

    _SOP_RUN_LOCK = "agentscope:sop_run:lock:{rid}"

    SOP_RUN_TTL_SECS = 600
    """Lock lease for a SOP run (10 minutes), renewed while held."""

    _SOP_DISPATCH_NS = "agentscope:sop:dispatch:{sid}"

    SOP_DISPATCH_FIELD = "step"
    """The only field a dispatch namespace holds."""

    @classmethod
    def sop_dispatch(cls, session_id: str) -> str:
        """Registry namespace holding ``"<run id>:<step index>"`` while a
        step's turn is parked in this session. Per session and unleased,
        since a park can wait on a person indefinitely."""
        return cls._SOP_DISPATCH_NS.format(sid=session_id)

    @classmethod
    def sop_run_lock(cls, sop_run_id: str) -> str:
        """Per-run lock, taken after the procedure's and before any
        session's."""
        return cls._SOP_RUN_LOCK.format(rid=sop_run_id)

    # ------------------------------------------------------------------
    # Session inbox
    # ------------------------------------------------------------------

    _INBOX = "agentscope:inbox:{sid}"
    _INBOX_LOCK = "agentscope:inbox:lock:{sid}"
    _INBOX_CONSUMER = "agentscope:inbox:consumer:{sid}"

    INBOX_LOCK_TTL_SECS = 30
    """Lease for the inbox hand-off lock. The critical sections it
    guards are a single queue op plus a single registry op, so a lease
    this short only ever matters when a process dies inside one."""

    INBOX_CONSUMER_FIELD = "running"
    """Field name inside the per-session inbox-consumer registry."""

    @classmethod
    def inbox(cls, session_id: str) -> str:
        """Per-session inbox drain-queue key."""
        return cls._INBOX.format(sid=session_id)

    @classmethod
    def inbox_lock(cls, session_id: str) -> str:
        """Per-session lock serialising inbox hand-off.

        Held only around two tiny critical sections — the producer's
        "push then read consumer flag" and the consumer's "drain then
        clear consumer flag". Making those two mutually exclusive is
        what stops an entry pushed just as a run finishes from being
        both missed by that run and skipped by the producer's wake-up
        decision.
        """
        return cls._INBOX_LOCK.format(sid=session_id)

    @classmethod
    def inbox_consumer(cls, session_id: str) -> str:
        """Per-session registry recording whether a run is currently
        consuming this inbox.

        Deliberately **not** derived from
        :meth:`session_lock` — the lock is still held while a finished
        run persists its state, and during that window no further drain
        will happen, so producers must already treat the session as
        having no consumer.
        """
        return cls._INBOX_CONSUMER.format(sid=session_id)

    # ------------------------------------------------------------------
    # Run trigger queue (wakeup / resume)
    # ------------------------------------------------------------------

    _WAKEUP_QUEUE = "agentscope:wakeups"
    _WAKEUP_SIGNAL = "agentscope:wakeup_signal"

    @classmethod
    def wakeup_queue(cls) -> str:
        """Shared run-trigger queue key."""
        return cls._WAKEUP_QUEUE

    @classmethod
    def wakeup_signal(cls) -> str:
        """Shared signal channel that nudges dispatchers to drain."""
        return cls._WAKEUP_SIGNAL

    # ------------------------------------------------------------------
    # Cross-process cancel
    # ------------------------------------------------------------------

    _SESSION_CANCEL = "agentscope:session:cancel"
    _TASK_CANCEL = "agentscope:task:cancel"
    _SESSION_INTERRUPT = "agentscope:session:interrupt"

    @classmethod
    def session_cancel_channel(cls) -> str:
        """Global session-cancel broadcast channel."""
        return cls._SESSION_CANCEL

    @classmethod
    def task_cancel_channel(cls) -> str:
        """Single-task cancel broadcast channel."""
        return cls._TASK_CANCEL

    @classmethod
    def session_interrupt_channel(cls) -> str:
        """Global session-interrupt broadcast channel.

        Used by the interrupt API endpoint to request graceful
        interruption of a running agent.  Separate from
        ``session_cancel_channel`` (which is used for hard-cancel on
        session deletion).
        """
        return cls._SESSION_INTERRUPT

    # ------------------------------------------------------------------
    # Background task registry
    # ------------------------------------------------------------------

    _BG_TASKS = "agentscope:bg_tasks:{sid}"

    BG_TASKS_TTL_SECS = 86400
    """Fallback TTL for the per-session BG task registry (24 h)."""

    @classmethod
    def bg_tasks(cls, session_id: str) -> str:
        """Per-session background task registry key."""
        return cls._BG_TASKS.format(sid=session_id)

    # ------------------------------------------------------------------
    # Knowledge-base indexing pipeline
    # ------------------------------------------------------------------

    _INDEX_TASKS_QUEUE = "agentscope:index:tasks"
    _INDEX_TASKS_SIGNAL = "agentscope:index:tasks:wake"

    @classmethod
    def index_tasks_queue(cls) -> str:
        """Shared, durable index-task queue.

        The producer-side
        :class:`~agentscope.app._service.KnowledgeBaseService`
        ``queue_push``\\ es here through
        :func:`~agentscope.app._bus_ops.enqueue_index_task`; the
        consumer-side
        :class:`~agentscope.app._service.IndexTaskConsumer`
        ``queue_drain``\\ s it on each signal — plus once eagerly on
        consumer start-up so tasks queued while every worker was down
        are picked up immediately.
        """
        return cls._INDEX_TASKS_QUEUE

    @classmethod
    def index_tasks_signal(cls) -> str:
        """Shared pub/sub channel that nudges every running index-task
        consumer to drain the queue.

        Payload is opaque — only its arrival matters. Redis pub/sub is
        fire-and-forget, so a published signal does not guarantee
        delivery; the durable queue keeps work safe in case every
        subscriber happens to be offline.
        """
        return cls._INDEX_TASKS_SIGNAL

    # ------------------------------------------------------------------
    # Schedules. Only the node that owns the timers reconciles them;
    # every node publishes here after writing a schedule to storage.
    # ------------------------------------------------------------------

    _SCHEDULE_LIFECYCLE = "agentscope:schedule:lifecycle"

    @classmethod
    def schedule_lifecycle(cls) -> str:
        """Pub/sub channel that nudges the timer-owning node to
        reconcile its schedule jobs against storage."""
        return cls._SCHEDULE_LIFECYCLE

    # ------------------------------------------------------------------
    # Channels. A reply never travels through the bus: delivery is plain
    # REST, so the node running the agent sends it directly. What does
    # cross nodes is coordination — reconcile nudges, the status
    # heartbeat that lets a connection-free replica answer, and the
    # per-chat buffers.
    # ------------------------------------------------------------------

    _CHANNEL_CREDENTIAL_BINDING = "agentscope:channel:binding"

    CREDENTIAL_BINDING_FIELD = "record"
    """Field holding the serialised binding session."""

    CREDENTIAL_BINDING_CLAIM_TTL_SECS = 300
    """How long obtained credentials stay claimable. Short on purpose —
    they sit here in the clear until the channel is created."""

    @classmethod
    def channel_credential_binding(cls, binding_id: str) -> str:
        """Registry namespace holding one credential-binding session."""
        return f"{cls._CHANNEL_CREDENTIAL_BINDING}:{binding_id}"

    _CHANNEL_LIFECYCLE = "agentscope:channel:lifecycle"
    _CHANNEL_LIVENESS = "agentscope:channel:liveness:{cid}"
    _CHANNEL_MEDIA = "agentscope:channel:media:{cid}:{chat}:{uid}"
    _CHANNEL_SEEN_CHATS = "agentscope:channel:seen_chats:{cid}"

    @classmethod
    def channel_lifecycle(cls) -> str:
        """Pub/sub channel that nudges every node to reconcile its
        running channel instances against storage."""
        return cls._CHANNEL_LIFECYCLE

    @classmethod
    def channel_liveness(cls, channel_id: str) -> str:
        """Per-channel per-node status heartbeat namespace."""
        return cls._CHANNEL_LIVENESS.format(cid=channel_id)

    @classmethod
    def channel_media_buffer(
        cls,
        channel_id: str,
        chat_id: str,
        user_id: str,
    ) -> str:
        """Queue key buffering media until the next text message."""
        return cls._CHANNEL_MEDIA.format(
            cid=channel_id,
            chat=chat_id,
            uid=user_id,
        )

    @classmethod
    def channel_seen_chats(cls, channel_id: str) -> str:
        """Registry namespace of chat_ids the bot has been messaged in."""
        return cls._CHANNEL_SEEN_CHATS.format(cid=channel_id)
