"""The typed tools agents use to work on a case together.

Replaces free-form chat between members: every message is an item in the case
file with a reference, an author and (for facts) evidence. Leader-only tools
check the role themselves, in addition to the tool filter.
"""
from __future__ import annotations

from typing import Any

from pydantic import Field

from agentscope.message import TextBlock, ToolResultState
from agentscope.permission import PermissionBehavior, PermissionDecision
from agentscope.tool import ParamsBase, ToolBase, ToolChunk

from ..casefile import CaseView, build_view
from ..casefile.digest import describe
from ..guard import check_text
from ..requests import RequestError, RequestKind, figures_text, validate
from ..runtime import Binding, Runtime

MAX_FINALIZE_ATTEMPTS = 3
OUTCOMES = ("resolved", "needs_human", "cannot_resolve")


def _ok(text: str) -> ToolChunk:
    return ToolChunk(content=[TextBlock(text=text)])


def _err(text: str) -> ToolChunk:
    return ToolChunk(content=[TextBlock(text=text)], state=ToolResultState.ERROR)


class _CaseTool(ToolBase):
    is_concurrency_safe = False
    is_read_only = False

    def __init__(self, rt: Runtime, b: Binding) -> None:
        super().__init__()
        self.rt, self.b = rt, b

    async def check_permissions(self, *args: Any, **kwargs: Any) -> PermissionDecision:
        return PermissionDecision(behavior=PermissionBehavior.ALLOW,
                                  message="case-file tool")

    async def _view(self) -> CaseView:
        return build_view(await self.rt.cases.items(self.b.case_id))

    async def _pending_team(self, view: CaseView) -> list[str]:
        pending = [q.ref for q in view.open_questions()]
        reports = view.reports
        if self.b.fence:
            reports = {item.author for item in await self.rt.cases.items(self.b.case_id, kinds=("report",))
                       if (item.data.get("job_id"), item.data.get("generation")) ==
                       (self.b.fence.job_id, self.b.fence.generation)}
        pending.extend(member["agent_name"] for member in await self.rt.active_sessions(self.b.case_id)
                       if member["role"] == "worker" and member["agent_name"] not in reports)
        return pending

    def _sources(self, view: CaseView, refs: list[str]) -> tuple[list[str], list[str], list[str]]:
        """(texts of the cited items, the subset that comes from tools, refs that
        cannot be cited). A fact brings its own evidence. What the requester typed
        (tool "intake") counts as a source for figures but never as proof that a
        system confirmed something."""
        texts: list[str] = []
        trusted: list[str] = []
        bad: list[str] = []

        def add_evidence(ref: str) -> None:
            ev = view.evidence[ref]
            text = ev.data.get("text", "")
            texts.append(text)
            if ev.data.get("tool") != "intake":
                trusted.append(text)

        for ref in refs:
            if ref in view.evidence:
                add_evidence(ref)
            elif ref in view.facts:
                f = view.facts[ref]
                if f.status == "retracted":
                    bad.append(f"{ref} (retracted)")
                    continue
                texts.append(f.item.data.get("text", ""))
                for e in f.item.data.get("evidence", []):
                    if e in view.evidence:
                        add_evidence(e)
            else:
                bad.append(ref)
        return texts, trusted, bad

    async def _closed(self) -> ToolChunk | None:
        if self.b.fence is not None:
            await self.b.fence.check(self.rt.workforce)
        case = await self.rt.cases.get_case(self.b.case_id)
        if case is None or case["status"] != "open":
            return _err("The case is closed. Stop working on it.")
        return None

    def _leader_only(self) -> ToolChunk | None:
        if self.b.role != "leader":
            return _err("Only the leader can do this.")
        return None


# ---- parameters ------------------------------------------------------------
class _FactP(ParamsBase):
    text: str = Field(description="One factual statement you can back with evidence.")
    evidence: list[str] = Field(description="Evidence ids (E..) or fact ids (F..) that support it.")


class _GapP(ParamsBase):
    topic: str = Field(description="What you could not find out.")
    tried: str = Field(default="", description="What you tried.")


class _AskP(ParamsBase):
    to: str = Field(description="Name of the teammate to ask.")
    question: str = Field(description="A specific question that needs data they hold.")


class _AnswerP(ParamsBase):
    ref: str = Field(description="The question (Q..) or challenge (C..) you answer.")
    text: str = Field(description="Your answer.")
    evidence: list[str] = Field(default_factory=list, description="Evidence ids backing it.")
    retract: bool = Field(default=False, description="For a challenge: withdraw your fact.")


class _ChallengeP(ParamsBase):
    fact: str = Field(description="The fact id (F..) you dispute.")
    reason: str = Field(description="What is wrong or missing.")
    evidence: list[str] = Field(description="Evidence ids that show it. Opinions are not accepted.")


class _RequestP(ParamsBase):
    kind: str = Field(description="Which kind of request to send.")
    fields: dict = Field(description="The fields of that kind.")
    evidence: list[str] = Field(default_factory=list, description="Evidence ids that back every figure in fields.")


class _ReadP(ParamsBase):
    ref: str | None = Field(default=None, description="One item to read in full; empty for an overview.")


class _DecideP(ParamsBase):
    text: str = Field(description="Your decision and the reason.")
    keep: list[str] = Field(default_factory=list, description="Fact ids you keep.")
    retract: list[str] = Field(default_factory=list, description="Fact ids you drop.")


class _FinalizeP(ParamsBase):
    answer: str = Field(description="The final answer. Figures and codes must come from cited items.")
    outcome: str = Field(description="resolved | needs_human | cannot_resolve")
    cites: list[str] = Field(default_factory=list, description="Fact/evidence ids the answer rests on.")
    unknowns: list[str] = Field(default_factory=list, description="What is still unknown or needs a person.")


# ---- tools -----------------------------------------------------------------
class CaseFact(_CaseTool):
    name = "CaseFact"
    description = ("Record a fact in the case file. Every fact must cite evidence ids; figures, dates "
                   "and codes in it must appear in the cited evidence.")
    input_schema = _FactP.model_json_schema()

    async def call(self, text: str, evidence: list[str]) -> ToolChunk:
        if (closed := await self._closed()):
            return closed
        view = await self._view()
        if not evidence:
            return _err("Cite at least one evidence id, or record a CaseGap if you cannot find it.")
        sources, trusted, bad = self._sources(view, evidence)
        if bad:
            return _err(f"Cannot cite: {', '.join(bad)}. Known evidence: {', '.join(list(view.evidence)[-8:])}.")
        problems = check_text(text, sources, await self.rt.case_rules(self.b.case_id), trusted)
        if problems:
            return _err("Not recorded: " + "; ".join(problems))
        item = await self.rt.cases.add(self.b.case_id, "fact", self.b.agent_name,
                                       {"text": text, "evidence": evidence})
        return _ok(f"{item.ref} recorded.")


class CaseGap(_CaseTool):
    name = "CaseGap"
    description = "Record that you could not find or verify something. Saying you do not know is a valid result."
    input_schema = _GapP.model_json_schema()

    async def call(self, topic: str, tried: str = "") -> ToolChunk:
        if (closed := await self._closed()):
            return closed
        item = await self.rt.cases.add(self.b.case_id, "gap", self.b.agent_name,
                                       {"topic": topic, "tried": tried})
        return _ok(f"{item.ref} recorded.")


class CaseAsk(_CaseTool):
    name = "CaseAsk"
    description = ("Ask a teammate a specific question that needs data they hold. They answer with CaseAnswer. "
                   "Do not use it for opinions.")
    input_schema = _AskP.model_json_schema()

    async def call(self, to: str, question: str) -> ToolChunk:
        if (closed := await self._closed()):
            return closed
        members = {s["agent_name"] for s in await self.rt.active_sessions(self.b.case_id)}
        if to == self.b.agent_name or to not in members:
            return _err(f"No such teammate. Members: {sorted(members - {self.b.agent_name})}.")
        item = await self.rt.cases.add(self.b.case_id, "question", self.b.agent_name,
                                       {"text": question}, addressee=to)
        await self.rt.deliver(self.b.case_id, to, f'ref="{item.ref}"', self.b.agent_name,
                              f"{item.ref} asks you: {question}\nAnswer with CaseAnswer(ref=\"{item.ref}\").")
        return _ok(f"{item.ref} sent to {to}.")


class CaseAnswer(_CaseTool):
    name = "CaseAnswer"
    description = "Answer a question (Q..) or a challenge (C..) addressed to you. To concede a challenge set retract=true."
    input_schema = _AnswerP.model_json_schema()

    async def call(self, ref: str, text: str, evidence: list[str] | None = None,
                   retract: bool = False) -> ToolChunk:
        if (closed := await self._closed()):
            return closed
        evidence = evidence or []
        view = await self._view()
        target = view.questions.get(ref) or view.challenges.get(ref)
        if target is None or target.addressee != self.b.agent_name:
            return _err("That item is not addressed to you.")
        if ref in view.answers_to:
            return _err("Already answered.")
        is_challenge = ref in view.challenges
        if retract and not is_challenge:
            return _err("retract applies to challenges only.")
        sources, trusted, bad = self._sources(view, evidence)
        if bad:
            return _err(f"Cannot cite: {', '.join(bad)}.")
        if is_challenge and not retract and not evidence:
            return _err("Defend with evidence, or retract the fact.")
        problems = check_text(text, sources, await self.rt.case_rules(self.b.case_id), trusted)
        if problems:
            return _err("Not recorded: " + "; ".join(problems))
        item = await self.rt.cases.add(self.b.case_id, "answer", self.b.agent_name,
                                       {"to_ref": ref, "text": text, "evidence": evidence,
                                        "retract": retract}, addressee=target.author)
        await self.rt.deliver(self.b.case_id, target.author, f'ref="{item.ref}"', self.b.agent_name,
                              f"{item.ref} answers {ref}{' (RETRACTED)' if retract else ''}: {text}")
        return _ok(f"{item.ref} sent to {target.author}.")


class CaseChallenge(_CaseTool):
    name = "CaseChallenge"
    description = ("Dispute a teammate's fact with evidence. Limited rounds per fact; after that the leader decides. "
                   "Use it for facts, not opinions.")
    input_schema = _ChallengeP.model_json_schema()

    async def call(self, fact: str, reason: str, evidence: list[str]) -> ToolChunk:
        if (closed := await self._closed()):
            return closed
        view = await self._view()
        f = view.facts.get(fact)
        if f is None or f.status == "retracted":
            return _err("No such live fact.")
        if f.item.author == self.b.agent_name:
            return _err("You cannot challenge your own fact; retract it by answering a challenge.")
        if not evidence:
            return _err("Cite evidence that shows the problem; opinions are not accepted.")
        _src, _trusted, bad = self._sources(view, evidence)
        if bad:
            return _err(f"Cannot cite: {', '.join(bad)}.")
        if view.challenge_rounds.get(fact, 0) >= self.rt.settings.max_challenge_rounds:
            return _err("Round limit reached. Tell the leader (TeamSay) and let them decide.")
        item = await self.rt.cases.add(self.b.case_id, "challenge", self.b.agent_name,
                                       {"fact": fact, "reason": reason, "evidence": evidence},
                                       addressee=f.item.author)
        await self.rt.deliver(self.b.case_id, f.item.author, f'ref="{item.ref}"', self.b.agent_name,
                              f"{item.ref} challenges your {fact}: {reason}\n"
                              f"Answer with CaseAnswer(ref=\"{item.ref}\"): defend with evidence or retract=true.")
        return _ok(f"{item.ref} sent to {f.item.author}.")


class CaseRequest(_CaseTool):
    """Reach someone outside the platform with a form the domain defined."""

    name = "CaseRequest"
    input_schema = _RequestP.model_json_schema()

    def __init__(self, rt: Runtime, b: Binding, kinds: dict[str, RequestKind]) -> None:
        super().__init__(rt, b)
        self.kinds = kinds
        listing = "\n".join(
            f"- {k.key}: {k.description} Fields: {', '.join((k.fields.get('properties') or {}).keys())}. "
            + ("A reply comes back and wakes you; end your turn and wait." if k.expects_reply
               else "No reply is expected.")
            for k in kinds.values())
        self.description = ("Send a request outside the platform (field staff, the requester). Every figure in "
                            "the fields must come from cited evidence.\nKinds:\n" + listing)

    async def call(self, kind: str, fields: dict, evidence: list[str] | None = None) -> ToolChunk:
        if (closed := await self._closed()):
            return closed
        spec = self.kinds.get(kind)
        if spec is None:
            return _err(f"Unknown kind. Use one of: {', '.join(self.kinds)}.")
        try:
            validate(spec.fields, fields, "fields")
        except RequestError as e:
            return _err(f"Not sent: {e}")
        view = await self._view()
        sources, trusted, bad = self._sources(view, evidence or [])
        if bad:
            return _err(f"Cannot cite: {', '.join(bad)}.")
        problems = check_text(figures_text(fields), sources, await self.rt.case_rules(self.b.case_id), trusted)
        if problems:
            return _err("Not sent: " + "; ".join(problems))
        case = await self.rt.cases.get_case(self.b.case_id)
        item = await self.rt.cases.add(self.b.case_id, "request", self.b.agent_name,
                                       {"kind": kind, "fields": fields, "expects_reply": spec.expects_reply})
        await self.rt.cases.queue_outbox(self.b.case_id, "request", {
            "case_id": self.b.case_id, "external_ref": case["external_ref"], "request_ref": item.ref,
            "kind": kind, "fields": fields, "expects_reply": spec.expects_reply})
        return _ok(f"{item.ref} sent." + (" Wait for the reply." if spec.expects_reply else ""))


class CaseRead(_CaseTool):
    name = "CaseRead"
    description = "Read the case file: an overview, or one item in full by its id."
    input_schema = _ReadP.model_json_schema()
    is_read_only = True
    is_concurrency_safe = True

    async def call(self, ref: str | None = None) -> ToolChunk:
        if ref:
            item = await self.rt.cases.get(self.b.case_id, ref)
            if item is None:
                return _err("No such item.")
            return _ok(f"{describe(item, 2000)}")
        view = await self._view()
        lines = [f"{r} [{f.status}] " + describe(f.item, 220).split(" ", 1)[1]
                 for r, f in view.live_facts().items()]
        lines += [describe(q) for q in view.open_questions()]
        lines += [describe(c) for c in view.open_challenges()]
        lines += [describe(g) for g in view.gaps]
        lines += [describe(d) for d in view.decisions]
        return _ok("\n".join(lines) or "The case file is empty.")


class CaseDecide(_CaseTool):
    name = "CaseDecide"
    description = "Leader only. Settle a disagreement: say which facts you keep and which you drop, and why."
    input_schema = _DecideP.model_json_schema()

    async def call(self, text: str, keep: list[str] | None = None,
                   retract: list[str] | None = None) -> ToolChunk:
        if (closed := await self._closed()):
            return closed
        denied = self._leader_only()
        if denied:
            return denied
        keep, retract = keep or [], retract or []
        view = await self._view()
        unknown = [r for r in keep + retract if r not in view.facts]
        if unknown:
            return _err(f"Unknown facts: {unknown}.")
        item = await self.rt.cases.add(self.b.case_id, "decision", self.b.agent_name,
                                       {"text": text, "keep": keep, "retract": retract})
        for ref in keep + retract:
            author = view.facts[ref].item.author
            if author != self.b.agent_name:
                verb = "dropped" if ref in retract else "kept"
                await self.rt.deliver(self.b.case_id, author, f'ref="{item.ref}"',
                                      self.b.agent_name, f"{item.ref}: {ref} {verb}. {text}")
        return _ok(f"{item.ref} recorded.")


class CaseFinalize(_CaseTool):
    name = "CaseFinalize"
    description = ("Leader only. Give the final answer for the case. Figures, dates and codes in it must appear "
                   "in the cited items; unknowns must be listed. This ends the case.")
    input_schema = _FinalizeP.model_json_schema()

    async def call(self, answer: str, outcome: str, cites: list[str] | None = None,
                   unknowns: list[str] | None = None) -> ToolChunk:
        denied = self._leader_only()
        if denied:
            return denied
        cites, unknowns = cites or [], unknowns or []
        if outcome not in OUTCOMES:
            return _err(f"outcome must be one of {OUTCOMES}.")
        if (closed := await self._closed()):
            return closed
        view = await self._view()
        rules = await self.rt.case_rules(self.b.case_id)
        sources, trusted, bad = self._sources(view, cites)
        problems: list[str] = []
        if view.open_challenges():
            problems.append("open challenges remain: settle them with CaseDecide first")
        if bad:
            problems.append(f"cannot cite {', '.join(bad)}")
        if outcome == "resolved" and not cites:
            problems.append("a resolved answer must cite facts or evidence")
        if outcome == "resolved":
            # Waiting on someone is not a mistake to retry: refuse without counting an attempt.
            waiting = [r.ref for r in view.open_requests()]
            if waiting:
                return _err(f"Not finalized: still waiting for replies to {', '.join(waiting)}.")
            case = await self.rt.cases.get_case(self.b.case_id)
            needed = (case or {}).get("intake", {}).get("confirm_with")
            if needed and not view.confirmed(needed):
                return _err(f"Not finalized: the requester has not confirmed. Send a {needed} request and wait "
                            "for a reply with confirmed true.")
        if not problems:
            # every outcome is checked: the text reaches the domain either way
            problems += check_text(answer, sources, rules, trusted)
        if outcome == "resolved" and not problems:
            if pending := await self._pending_team(view):
                return _err("Not finalized: wait for teammate answers/reports: " + ", ".join(pending) +
                            ". End this turn; their reply will wake you. Use needs_human if they cannot answer.")
        judge = self.rt.judge
        if outcome == "resolved" and judge is not None and sources and not problems:
            p = await judge.support(answer, sources)
            if p is not None and p < self.rt.settings.jev_min_support:
                if hasattr(judge, "stats"):
                    judge.stats.blocked += 1
                problems.append(f"a second check found the answer weakly supported by the cited items (p={p:.2f})")

        if problems:
            if outcome != "resolved":
                # Not a claim of success, so no retry loop: send the safe text.
                answer, unknowns = rules.safe_reply, [*unknowns, *problems]
            else:
                attempts = 1 + sum(1 for n in await self.rt.cases.items(self.b.case_id, kinds=("note",))
                                   if n.data.get("type") == "final_attempt")
                await self.rt.cases.add(self.b.case_id, "note", self.b.agent_name,
                                        {"type": "final_attempt", "problems": problems})
                if attempts < MAX_FINALIZE_ATTEMPTS:
                    return _err(f"Not accepted ({attempts}/{MAX_FINALIZE_ATTEMPTS}): " + "; ".join(problems)
                                + ". Fix it, or use outcome needs_human and list what is unknown.")
                answer, outcome = rules.safe_reply, "needs_human"
                unknowns = [*unknowns, *problems]

        item = await self.rt.cases.add(self.b.case_id, "final", self.b.agent_name,
                                       {"answer": answer, "outcome": outcome, "cites": cites,
                                        "unknowns": unknowns})
        result = {"answer": answer, "outcome": outcome, "cites": cites, "unknowns": unknowns,
                  "ref": item.ref}
        if not await self.rt.close(self.b.case_id, "finalized", result, fence=self.b.fence):
            return _err("The case was closed meanwhile; nothing was recorded.")
        return _ok(f"{item.ref} recorded; the case is finalized as {outcome}.")


CASE_TOOLS = (CaseFact, CaseGap, CaseAsk, CaseAnswer, CaseChallenge, CaseRead, CaseDecide, CaseFinalize)
