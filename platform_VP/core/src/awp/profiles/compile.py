"""Turn a profile into what AgentScope runs: a prompt, a tool list, a template."""
from __future__ import annotations

from ..config import Settings
from .models import AgentProfile

# Tools every role gets. Anything else must be listed in `tools_allow`.
LEADER_TOOLS = ["Case*", "TeamCreate", "AgentCreate", "AgentInvite", "TeamSay", "TeamDelete"]
WORKER_TOOLS = ["CaseFact", "CaseGap", "CaseAsk", "CaseAnswer", "CaseChallenge", "CaseRead", "TeamSay"]
# Tools kept when a case runs out of budget: only what is needed to wrap up.
WRAP_UP_TOOLS = ["CaseFinalize", "CaseRead", "CaseGap", "CaseAnswer", "TeamSay"]


def tool_patterns(profile: AgentProfile) -> list[str]:
    base = LEADER_TOOLS if profile.role == "leader" else WORKER_TOOLS
    return [*base, *profile.tools_allow]


def _esc(text: str) -> str:
    """Escape braces so the text survives str.format in SubAgentTemplate."""
    return text.replace("{", "{{").replace("}", "}}")


def _lines(label: str, items: list[str]) -> str:
    return f"{label}: " + "; ".join(items) + "." if items else ""


def _identity(profile: AgentProfile, name: str) -> str:
    parts = [
        f"You are {name}, {profile.mission}",
        _lines("You handle", profile.handles),
        _lines("You do not handle (say so and tell the leader)", profile.refuses),
    ]
    return "\n".join(p for p in parts if p)


def _escalation(profile: AgentProfile) -> str:
    if not profile.escalate_when:
        return ""
    return "Stop and hand over to a person when: " + "; ".join(profile.escalate_when) + "."


def _memory_note(profile: AgentProfile) -> str:
    if not profile.memory.enabled:
        return ""
    return ("Your memory notes are hints, not evidence: verify them with a tool "
            "before you state them as fact.")


def _domain(profile: AgentProfile) -> str:
    return f"Domain instructions:\n{profile.instructions}" if profile.instructions.strip() else ""


def specialist_prompt(profile: AgentProfile, version: int, settings: Settings) -> str:
    """Prompt template for a specialist; AgentScope fills the {placeholders}."""
    body = "\n".join(filter(None, [
        f'<awp-profile key="{profile.key}" v="{version}"/>',
        _esc(_identity(profile, "{member_name}")).replace("{{member_name}}", "{member_name}"),
        "You work in team '{team_name}' led by {leader_name}. Case goal: {team_description}. "
        "Your assignment: {member_description}.",
        "How you work in the room:",
        "1. Get facts from your tools. Each tool result carries an evidence id (E..). "
        "Never state a number, date, code or status that did not come from a tool result or the case file.",
        "2. Record each finding with CaseFact(text, evidence=[E..]). If you cannot find something, "
        "record CaseGap(topic, tried): saying you do not know is a valid result.",
        "3. Read the room digest. If a peer asks you something, answer with CaseAnswer. If a peer "
        "challenges your fact, defend it with evidence or retract it with CaseAnswer(retract=true).",
        "4. Ask a peer (CaseAsk) only when you need data they hold. Dispute a peer's fact with "
        "CaseChallenge(fact, reason, evidence) only when you have evidence; "
        f"at most {settings.max_challenge_rounds} rounds per fact, then the leader decides.",
        "5. Finish with TeamSay(to={leader_name}): a short report naming your fact ids (F..) and gaps (G..). "
        "If you are waiting for a peer, send a one-line TeamSay to the leader saying whom you wait for.",
        "You never decide for the case; the leader decides.",
        _esc(_escalation(profile)),
        _esc(_memory_note(profile)),
        _esc(_domain(profile)),
    ]))
    return body


def leader_prompt(profile: AgentProfile, version: int, settings: Settings) -> str:
    """Concrete system prompt for a leader (no template placeholders)."""
    team = ", ".join(profile.team) if profile.team else "none"
    return "\n".join(filter(None, [
        f'<awp-profile key="{profile.key}" v="{version}"/>',
        _identity(profile, profile.name),
        f"You lead each case. Specialists you may bring in (AgentCreate subagent_type): {team}.",
        "How you work:",
        "1. Decide whether the case needs a team. A simple case needs none: use your own tools. "
        "Otherwise TeamCreate, then AgentCreate only the specialists the case needs, each with a concrete task "
        "and the facts you want back.",
        "2. Do not poll. Members report by TeamSay. Read the room digest; it shows who said what and what is open.",
        f"3. If two members disagree (an open challenge), settle it with CaseDecide(text, keep=[F..], retract=[F..]); "
        f"challenge rounds are limited to {settings.max_challenge_rounds} per fact.",
        "4. Finish only with CaseFinalize(answer, outcome, cites=[F../E..], unknowns). The answer may only "
        "contain numbers, dates and codes that appear in the cited items. If something is unknown or needs a "
        "person, use outcome needs_human and list it in unknowns. Saying what you do not know is correct.",
        "5. You are the only one who decides.",
        _escalation(profile),
        _memory_note(profile),
        _domain(profile),
    ]))


def system_prompt(profile: AgentProfile, version: int, settings: Settings) -> str:
    if profile.role == "leader":
        return leader_prompt(profile, version, settings)
    return specialist_prompt(profile, version, settings)


def to_template(profile: AgentProfile, version: int, settings: Settings):
    """SubAgentTemplate for a specialist profile."""
    from agentscope.agent import ReActConfig
    from agentscope.app import SubAgentTemplate

    return SubAgentTemplate(
        type=profile.key,
        description=profile.invite_description or profile.mission,
        system_prompt_template=specialist_prompt(profile, version, settings),
        react_config=ReActConfig(max_iters=profile.max_iters),
    )
