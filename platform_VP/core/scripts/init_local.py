"""Generate ignored credentials for the isolated Workforce stack; never print secrets."""
import hashlib
import json
import secrets
from pathlib import Path

from cryptography.fernet import Fernet

root = Path(__file__).resolve().parents[1]
target = root / ".env"
if not target.exists():
    target.write_text("\n".join([
    "AWP_POSTGRES_PASSWORD=" + secrets.token_urlsafe(32),
    "AWP_MINIO_ACCESS_KEY=awp-local",
    "AWP_MINIO_SECRET_KEY=" + secrets.token_urlsafe(32),
    "AWP_SECRET_KEY=" + Fernet.generate_key().decode(),
    "AWP_ADMIN_KEYS=" + secrets.token_urlsafe(40) + ":local",
    ]) + "\n", encoding="utf-8")
existing = target.read_text(encoding="utf-8")
additions = []
if "AWP_CONSOLE_USERS=" not in existing:
    password = secrets.token_urlsafe(24)
    salt = secrets.token_bytes(16)
    hashed = "pbkdf2:600000:" + salt.hex() + ":" + hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 600000).hex()
    additions.extend(["AWP_CONSOLE_USERS='" + json.dumps({"admin": {"password_hash": hashed, "tenant": "local", "role": "admin"}}) + "'",
                      "AWP_CONSOLE_SECURE_COOKIE=0"])
    local = root / ".local"
    local.mkdir(exist_ok=True)
    account_file = local / "accounts.txt"
    with account_file.open("a", encoding="utf-8") as account:
        account.write("\nWorkforce http://localhost:8089/console\nUsername: admin\nPassword: " + password + "\n")
if "AWP_MINIO_UPLOAD_ORIGIN=" not in existing:
    additions.append("AWP_MINIO_UPLOAD_ORIGIN=http://127.0.0.1:9090")
if additions:
    with target.open("a", encoding="utf-8") as env:
        env.write("\n" + "\n".join(additions) + "\n")
models = root / "models.yaml"
if not models.exists():
    models.write_text("models: []\n", encoding="utf-8")
print("Preserved existing secrets; local console account is in ignored .local/accounts.txt. Configure models before model execution.")
