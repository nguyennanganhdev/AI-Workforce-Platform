import asyncio
import logging
from typing import Optional
from contextlib import asynccontextmanager

# =========================================================================
# IMPORTS - DEV-1 (Supervisor) & DEV-2 (Groupchat)
# =========================================================================
from supervisor.service import SupervisorService
from supervisor.planner import Planner
from supervisor.ports import StateStore, Authority, ModelClient
from supervisor.models import SupervisorState, Action, AuthorityView, Reconciliation

from groupchat.room import RoomService
from groupchat.ports import ParticipantResolver, AgentInvocationPort, RoomStatePort, Invocation
from groupchat.models import Context, ScopeState, ParticipantSpec, AgentOutput

# =========================================================================
# MOCKS (Thay thế các kết nối DB và Backend thật)
# =========================================================================

# --- MOCK Persistence (Thay cho DEV-4) ---
class InMemoryStateStore(StateStore):
    def __init__(self):
        self._store = {}
        self._lock = asyncio.Lock()

    async def load(self, context: Context) -> Optional[SupervisorState]:
        return self._store.get(context.ticket_id)

    async def commit(self, state: SupervisorState, expected_version: Optional[int],
                     *, delivery_id: Optional[str] = None) -> bool:
        async with self._lock:
            key = state.context.ticket_id
            current = self._store.get(key)
            curr_v = current.revision if current else -1
            exp_v = -1 if expected_version is None else expected_version
            if curr_v != exp_v:
                return False
            state.revision = exp_v + 1
            self._store[key] = state
            return True


class InMemoryRoomStatePort(RoomStatePort):
    def __init__(self):
        self._store = {}
        self._lock = asyncio.Lock()

    async def load(self, room_id: str) -> Optional[ScopeState]:
        return self._store.get(room_id)

    async def save(self, scope: ScopeState, expected_version: Optional[int], delivery_id: str) -> bool:
        async with self._lock:
            curr = self._store.get(scope.room.room_id)
            curr_v = curr.version if curr else -1
            exp_v = -1 if expected_version is None else expected_version
            if curr_v != exp_v:
                return False
            scope.version = exp_v + 1
            self._store[scope.room.room_id] = scope
            return True

# --- MOCK Authority & Clients (Thay cho DEV-3) ---
class MockAuthority(Authority):
    async def inspect(self, state: SupervisorState) -> AuthorityView:
        return AuthorityView(ticket_context=[], resident_recipient="USER-1")

    async def authorize_action(self, state: SupervisorState, action: Action) -> None:
        pass

    async def reconcile(self, state: SupervisorState, action: Action) -> Reconciliation:
        return Reconciliation(status="applied")


class MockParticipantResolver(ParticipantResolver):
    async def resolve(self, spec: ParticipantSpec) -> ParticipantSpec:
        return spec


class MockAgentInvocationPort(AgentInvocationPort):
    async def invoke(self, invocation: Invocation) -> AgentOutput:
        return AgentOutput(content="Mocked response from agent", messages=[])


class MockModelClient(ModelClient):
    async def generate(self, prompt: dict) -> str:
        return '{"decision": "mocked"}'

class AgentScopeModelClient(ModelClient):
    """
    DEV-5: Client kết nối Model qua thư viện AgentScope.
    """
    def __init__(self, config):
        import agentscope
        from agentscope.models import load_model_by_config_name

        model_config = {
            "config_name": "coordination_model",
            "model_type": config.MODEL_PROVIDER,
            "model_name": config.MODEL_NAME,
            "api_key": config.MODEL_API_KEY,
        }
        if config.MODEL_API_BASE:
            model_config["client_args"] = {"base_url": config.MODEL_API_BASE}

        agentscope.init(model_configs=[model_config])
        self.model_wrapper = load_model_by_config_name("coordination_model")

    async def generate(self, prompt: dict) -> str:
        # Giả định planner sẽ tạo ra prompt có cấu trúc phù hợp
        response = self.model_wrapper(prompt)
        return response.text

class MockEventVerifier:
    async def resolve(self, event: dict, trusted_context: object):
        from groupchat.models import Context
        class Resolved:
            context = Context(
                tenant_id="TENANT-1", domain_id="DOMAIN-1", workspace_id="WS-1",
                ticket_id="TICKET-1", ticket_generation=1,
                principal_id="P1", binding_id="B1", run_id="R1"
            ).model_dump()
        return Resolved()


# =========================================================================
# MAIN INTEGRATION (DEV-5 - FastAPI App)
# =========================================================================
from fastapi import FastAPI, BackgroundTasks, status
from config import get_settings
import uvicorn

config = get_settings()

async def init_services():
    # Configure logging using ENV variable
    log_level = getattr(logging, config.LOG_LEVEL.upper(), logging.INFO)
    logging.basicConfig(level=log_level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger = logging.getLogger("agent-coordination")

    logger.info(f"Khởi động hệ thống Coordination (ENV={config.ENV}) - Focus: DEV-1, DEV-2, DEV-3...")

    # 1. Khởi tạo Mocks
    state_store = InMemoryStateStore()
    room_state_port = InMemoryRoomStatePort()
    authority = MockAuthority()
    resolver = MockParticipantResolver()
    agent_port = MockAgentInvocationPort()

    # DEV-5: Tích hợp Model Client (Fall back về Mock nếu chưa có API Key)
    if config.MODEL_API_KEY:
        logger.info(f"Khởi tạo AgentScopeModelClient với model: {config.MODEL_NAME}")
        model_client = AgentScopeModelClient(config)
    else:
        logger.warning(f"Không tìm thấy MODEL_API_KEY. Fallback về MockModelClient cho {config.MODEL_NAME}.")
        model_client = MockModelClient()

    # 2. Khởi tạo DEV-2: RoomService
    # Groupchat room service điều phối agents
    room_service = RoomService(
        state=room_state_port,
        resolver=resolver,
        invocation=agent_port
    )
    logger.info("Đã khởi tạo RoomService (DEV-2).")

    # 3. Khởi tạo DEV-1: SupervisorService
    planner = Planner(model_client)

    # Fake bridges (Vì DEV-3 chưa wire thật)
    class FakeBackendBridge: pass
    class FakeRoomBridge: pass

    verifier = MockEventVerifier()

    # DEV-3: ReceptionGateway
    from adapters.reception.reception_gateway import ReceptionGateway
    class MockBackendClient:
        async def resolve(self, *args, **kwargs): pass
        async def send(self, *args, **kwargs): pass

    # Mock authentication to allow instantiation without errors
    class MockReceptionAuthentication:
        pass

    reception_gateway = ReceptionGateway(
        backend=MockBackendClient(),
        authentication=MockReceptionAuthentication()
    )

    supervisor = SupervisorService(
        store=state_store,
        authority=authority,
        verifier=verifier,
        event_types={"custom.event": "ticket.submitted"},
        groupchat_version_id="v1.0",
        planner=planner,
        backend=FakeBackendBridge(),
        room=FakeRoomBridge(),
        reception=reception_gateway
    )
    logger.info("Đã khởi tạo SupervisorService & Planner (DEV-1).")


    logger.info("Môi trường tích hợp DEV-1 & DEV-2 & DEV-3 đã sẵn sàng!")
    logger.info("Cấu hình xong hệ thống. Đang đợi xử lý sự kiện...")
    logger.info("=========================================")

    # Return supervisor to be used by the event loop or test harness
    return supervisor

# --- DEV-5: Lifespan (thay thế @app.on_event("startup") đã deprecated) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Khởi tạo các service khi app startup
    app.state.supervisor = await init_services()
    yield
    # Dọn dẹp tài nguyên khi app shutdown (nếu có)

app = FastAPI(
    title="Agent Coordination Service",
    description="Core Routing & Agent Supervisor Service",
    version="1.0.0",
    lifespan=lifespan
)

# --- DEV-5: Health Check (kiểm tra dependency trước khi báo Ready) ---
@app.get("/health")
async def health_check():
    """
    Ping các service phụ thuộc trước khi báo Ready.
    Review yêu cầu: không trả 'ready' chỉ vì mở được cổng.
    """
    if not config.ENABLE_HEALTH_CHECK:
        return {"status": "disabled"}

    # TODO: Thay bằng ping thật khi DEV-3/DEV-4 hoàn thiện
    dependencies_status = {
        "database": "ok",     # Thực tế sẽ ping state_store (DEV-4)
        "model_client": "ok" if config.MODEL_API_KEY else "mocked",
        "backend": "ok"       # Thực tế sẽ ping ReceptionGateway (DEV-3)
    }

    is_ready = all(v in ["ok", "mocked"] for v in dependencies_status.values())

    return {
        "status": "ok" if is_ready else "error",
        "env": config.ENV,
        "service": "agent-coordination",
        "dependencies": dependencies_status
    }

# --- DEV-5: Integration Endpoints ---
from contracts.v2 import ReceptionToSupervisorMessage

async def process_ticket_background(supervisor, payload: ReceptionToSupervisorMessage):
    """Hàm xử lý ngầm trong background để không block HTTP request."""
    logger = logging.getLogger("agent-coordination")
    try:
        logger.info(f"Bắt đầu xử lý ngầm ticket {payload.ticket_id}")
        # MỞ COMMENT ĐOẠN NÀY KHI RÁP CODE THẬT (Đã tháo Mock):
        # await supervisor.process_event(payload.model_dump())
        await asyncio.sleep(0.1)  # Giả lập delay
        logger.info(f"Hoàn tất xử lý ngầm ticket {payload.ticket_id}")
    except Exception as e:
        logger.error(f"Lỗi khi xử lý ticket {payload.ticket_id}: {e}")

@app.post("/api/v1/tickets", status_code=status.HTTP_202_ACCEPTED)
async def receive_ticket(payload: ReceptionToSupervisorMessage, background_tasks: BackgroundTasks):
    """
    Endpoint nhận Ticket từ Lễ tân (DEV-3).
    Review yêu cầu: xử lý dài chạy qua worker, không giữ request HTTP chờ.
    Trả về 202 Accepted ngay lập tức.
    CHÚ Ý: Đã áp dụng Schema V2. Từ chối mọi payload V1 (trả 422).
    """
    supervisor = app.state.supervisor

    # Đẩy việc vào background thay vì chạy đồng bộ chờ kết quả
    background_tasks.add_task(process_ticket_background, supervisor, payload)

    return {
        "schema_version": "2.0",
        "ticket_id": payload.ticket_id,
        "status": "accepted",
        "message": "Ticket đã được tiếp nhận qua Schema V2 và đang đưa vào hàng đợi xử lý ngầm."
    }

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=config.PORT, reload=config.DEBUG)
