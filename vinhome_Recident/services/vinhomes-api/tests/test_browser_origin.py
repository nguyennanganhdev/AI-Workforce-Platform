from fastapi.testclient import TestClient
from vinhomes_api.main import create_app
from vinhomes_api.v3_config import V3Settings


def test_cross_site_mutations_are_refused_before_database_access():
    settings = V3Settings("127.0.0.1",8000,None,None,None)
    with TestClient(create_app(settings)) as client:
        response = client.post("/resident/chats", json={"title":"attack"},
                               headers={"origin":"https://untrusted.invalid","sec-fetch-site":"cross-site"})
        assert response.status_code == 403
        assert response.json()["detail"] == "Untrusted browser origin"
