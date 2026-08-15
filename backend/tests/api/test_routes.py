import pytest
from fastapi.testclient import TestClient

from app.llm.base import LLMResponse, ToolCall
from app.llm.fake import FakeLLM
from app.main import create_app


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("LLM_MODEL_CHAIN", "fake-model")
    monkeypatch.setenv("LLM_BASE_URL", "http://llm.invalid")
    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("BOOKING_API_KEY", "")
    monkeypatch.setenv("TRIPADVISOR_API_KEY", "")
    app = create_app()
    with TestClient(app) as c:
        yield app, c


def test_health(client):
    _app, c = client
    resp = c.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["providers"]["booking"] == "mock"


def test_criar_sessao(client):
    _app, c = client
    resp = c.post("/api/session")
    assert resp.status_code == 200
    body = resp.json()
    assert "session_id" in body
    assert body["ttl_minutes"] == 60


def test_brief_de_sessao_inexistente_retorna_404(client):
    _app, c = client
    resp = c.get("/api/session/nao-existe/brief")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "invalid_session"


def test_plano_indisponivel_antes_de_conversar(client):
    _app, c = client
    session_id = c.post("/api/session").json()["session_id"]
    resp = c.get(f"/api/session/{session_id}/plan")
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "plan_not_available"


def test_fluxo_completo_chat_ate_export(client):
    app, c = client
    app.state.llm_client = FakeLLM(
        script=[
            LLMResponse(
                content=None,
                tool_calls=[
                    ToolCall(
                        id="c1",
                        name="update_brief",
                        arguments={
                            "origin": "São Paulo",
                            "destination": "Florianópolis",
                            "reference_month": "janeiro",
                            "duration_days": 5,
                            "adults": 1,
                            "total_budget": 4000,
                        },
                    )
                ],
                finish_reason="tool_calls",
            ),
            LLMResponse(content="Vou montar seu roteiro."),
        ]
    )
    session_id = c.post("/api/session").json()["session_id"]

    with c.stream("POST", "/api/chat", json={"session_id": session_id, "message": "quero viajar"}) as resp:
        assert resp.status_code == 200
        events = list(resp.iter_lines())
    assert any("plan_ready" in line for line in events)

    resp_plan = c.get(f"/api/session/{session_id}/plan")
    assert resp_plan.status_code == 200

    resp_md = c.get(f"/api/session/{session_id}/export?format=md")
    assert resp_md.status_code == 200
    assert "Fontes e confiabilidade" in resp_md.text

    resp_pdf = c.get(f"/api/session/{session_id}/export?format=pdf")
    assert resp_pdf.status_code == 200
    assert resp_pdf.content[:4] == b"%PDF"
