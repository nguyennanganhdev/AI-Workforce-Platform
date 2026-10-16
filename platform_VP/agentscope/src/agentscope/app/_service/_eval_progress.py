"""Owner-scoped, persisted progress for an evaluation already requested by a user."""
import asyncio
import copy
from datetime import UTC, datetime
from uuid import uuid4

from ..storage import SessionConfig, StorageBase

PROGRESS_KEY = "evaluation_progress"
EVAL_AGENT = "workforce-evaluation"


def _now():
    return datetime.now(UTC).isoformat()


def progress_view(session):
    value = copy.deepcopy(session.state.middle_context.get(PROGRESS_KEY)) if session else None
    if value and value.get("status") == "running":
        updated = datetime.fromisoformat(value["updated_at"])
        if (datetime.now(UTC) - updated).total_seconds() > 300:
            value.update(status="interrupted", error="Đã mất cập nhật từ lượt eval. Kiểm tra kết quả lưu trước khi chạy lại.")
    return value


class EvalProgress:
    def __init__(self, storage: StorageBase, user_id: str, session):
        self.storage, self.user_id, self.session = storage, user_id, session
        self.lock = asyncio.Lock()
        self.value = {"run_id": uuid4().hex, "stage": "preparing", "status": "running",
            "started_at": _now(), "updated_at": _now(), "agents": []}
        self.active = None

    @classmethod
    async def for_agent(cls, storage, user_id, agent_id, config):
        session = await storage.upsert_session(user_id=user_id, agent_id=EVAL_AGENT,
            session_id="eval-" + agent_id, config=SessionConfig(workspace_id=agent_id, name="Evaluation", chat_model_config=config))
        return cls(storage, user_id, session)

    async def _save(self):
        self.value["updated_at"] = _now()
        self.session.state.middle_context[PROGRESS_KEY] = copy.deepcopy(self.value)
        await self.storage.update_session_state(self.user_id, self.session.agent_id, self.session.id, self.session.state)

    async def stage(self, stage, **values):
        async with self.lock:
            self.value.update(stage=stage, **values)
            await self._save()

    async def event(self, event):
        async with self.lock:
            stage = event["stage"]
            self.value["stage"] = stage
            if stage == "tests_ready":
                self.active = {"name": event["agent_name"], "tests": [{**test, "status": "pending"} for test in event["tests"]]}
                self.value["agents"].append(self.active)
            elif self.active is not None:
                test = next((test for test in self.active["tests"] if test["id"] == event.get("test_id")), None)
                if test is not None:
                    test.update(status=stage, step=event.get("step", test.get("step")))
                    if stage == "case_completed":
                        result = event["result"]
                        test.update(status=result["status"], result={key: value for key, value in result.items()
                            if key in {"passed", "status", "error", "error_kind", "judge", "latency_ms"}})
            await self._save()

    async def report(self, report):
        async with self.lock:
            if self.active is not None:
                self.active["report"] = {key: value for key, value in report.items() if key in {"total", "passed", "errors", "publishable"}}
            await self._save()

    async def finish(self):
        await self.stage("completed", status="completed", completed_at=_now())

    async def fail(self):
        await self.stage("error", status="error", error="Lượt tạo/kiểm thử chưa hoàn tất. Kiểm tra kết nối, quyền MCP và cấu hình rồi thử lại.")
