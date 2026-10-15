from fastapi.testclient import TestClient
from vinhomes_api.main import create_app


def test_invalid_login_does_not_reflect_password_or_input():
    with TestClient(create_app()) as client:
        response = client.post('/auth/login', json={'password': 'private-test-password'})
        assert response.status_code == 422
        assert 'private-test-password' not in response.text
        assert 'input' not in response.text
        assert response.json()['detail'][0]['loc'] == ['body', 'identifier']
