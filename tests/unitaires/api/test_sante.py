from fastapi.testclient import TestClient

from leypilot.api.main import app


def test_sante_repond_ok():
    reponse = TestClient(app).get("/sante")
    assert reponse.status_code == 200
    assert reponse.json() == {"statut": "ok"}
