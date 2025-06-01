from fastapi.testclient import TestClient

from backend.main import app


def test_voice_commands_health():
    client = TestClient(app)
    response = client.get("/voice_commands/health")
    assert response.status_code == 200
    assert response.json() == {"service": "voice_commands", "status": "healthy"}