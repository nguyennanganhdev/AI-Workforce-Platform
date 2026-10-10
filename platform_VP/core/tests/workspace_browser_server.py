"""Isolated browser acceptance server. Uses scripted models, never paid providers."""
import contextlib
import tempfile
from pathlib import Path

import uvicorn
from cryptography.fernet import Fernet
from fake_llm import FakeServer
from support import DemoPack

from awp.app import build_app
from awp.config import Settings
from awp.providers import ModelCatalog, ModelSpec
from awp.workforce.console import password_hash

if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="awp-workspace-browser-") as directory, FakeServer() as fake:
        path = Path(directory)
        catalog = ModelCatalog([
            ModelSpec(id="scripted-strong", provider="openai_compatible", model="fake-strong", tier="strong",
                base_url=fake.base_url, api_key_env="FAKE_KEY", price_in=2, price_out=8),
            ModelSpec(id="scripted-cheap", provider="openai_compatible", model="fake-cheap", tier="cheap",
                base_url=fake.base_url, api_key_env="FAKE_KEY", price_in=.5, price_out=2),
        ], env={"FAKE_KEY": "browser-test-only"})
        settings = Settings(db_url=f"sqlite+aiosqlite:///{path.as_posix()}/core.db",
            agentscope_db_url=f"sqlite+aiosqlite:///{path.as_posix()}/sdk.db", workspace_dir=str(path / "ws"),
            workforce_secret_key=Fernet.generate_key().decode(), workforce_workers=2, workforce_wait_seconds=0,
            console_secure_cookie=False, console_users={"browser-admin": {
                "tenant": "browser-test", "role": "admin", "password_hash": password_hash("browser-test-only")}})
        app = build_app(settings, catalog=catalog)
        rt = app.state.awp.rt
        rt.tool_factories.append(lambda runtime, binding: DemoPack().tools(runtime, binding))
        inner = app.router.lifespan_context

        @contextlib.asynccontextmanager
        async def lifespan(application):
            async with inner(application):
                for profile in DemoPack().profiles():
                    rec = await rt.profiles.create_draft("browser-test", profile)
                    await rt.profiles.publish("browser-test", rec.key, rec.version)
                await rt.sync_templates()
                yield

        app.router.lifespan_context = lifespan
        uvicorn.run(app, host="127.0.0.1", port=8098, log_level="warning")
