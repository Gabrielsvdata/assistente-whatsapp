import hashlib
import hmac
import os

import pytest
from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WHATSAPP_VERIFY_TOKEN"] = "segredo-teste"
os.environ.pop("GROQ_API_KEY", None)

from app import assistente, banco, conhecimento, whatsapp  # noqa: E402
from app.main import app, cliente_whatsapp  # noqa: E402


@pytest.fixture(autouse=True)
def tabelas():
    banco.Base.metadata.drop_all(banco.engine)
    banco.criar_tabelas()
    yield


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def enviados(monkeypatch):
    caixa = []
    monkeypatch.setattr(cliente_whatsapp, "enviar_texto", lambda para, texto: caixa.append((para, texto)))
    monkeypatch.setattr(cliente_whatsapp, "marcar_lida", lambda _id: None)
    return caixa


def payload_meta(texto, de="5511999990000", id_msg="wamid.1", nome="Ana Recrutadora", tipo="text"):
    msg = {"from": de, "id": id_msg, "type": tipo}
    if tipo == "text":
        msg["text"] = {"body": texto}
    return {"entry": [{"changes": [{"value": {
        "contacts": [{"wa_id": de, "profile": {"name": nome}}], "messages": [msg]}}]}]}


# ─── Decisão de resposta (sem IA) ───────────────────────────

def test_saudacao_devolve_menu():
    assert assistente.responder("oi").fonte == "menu"
    assert "1️⃣" in assistente.responder("Bom dia").texto


def test_atalhos_por_numero_e_palavra():
    assert assistente.responder("1").fonte == "atalho"
    assert "sispar" in assistente.responder("projetos").texto.lower()
    assert conhecimento.CURRICULO in assistente.responder("me manda o currículo").texto
    assert assistente.responder("quero falar com o Gabriel").avisar_gabriel is True


def test_mensagem_de_vaga_sem_ia_registra_lead_e_avisa():
    r = assistente.responder("Temos uma vaga de dev pleno na Acme, tem interesse?")
    assert r.fonte == "vaga"
    assert r.avisar_gabriel is True
    assert r.lead is not None


def test_pergunta_livre_sem_ia_cai_no_menu():
    assert assistente.responder("qual a cor favorita dele?").fonte == "fallback"


# ─── IA (simulada) ──────────────────────────────────────────

def test_ia_responde_e_extrai_lead(monkeypatch):
    monkeypatch.setattr(assistente, "responder_com_ia", lambda h, m: assistente.Resposta(
        texto="Que legal! Vou avisar o Gabriel.", fonte="ia",
        lead={"nome": "Ana", "empresa": "Acme", "cargo": "Dev Pleno"}, avisar_gabriel=True))
    r = assistente.responder("Sou a Ana da Acme, temos uma vaga de dev pleno")
    assert r.fonte == "ia" and r.lead["empresa"] == "Acme" and r.avisar_gabriel


# ─── Webhook ────────────────────────────────────────────────

def test_verificacao_do_webhook(client):
    ok = client.get("/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "segredo-teste", "hub.challenge": "123"})
    assert ok.status_code == 200 and ok.text == "123"
    assert client.get("/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "errado", "hub.challenge": "1"}).status_code == 403


def test_webhook_responde_e_registra(client, enviados):
    assert client.post("/webhook", json=payload_meta("oi")).status_code == 200
    assert enviados and enviados[0][0] == "5511999990000" and "assistente" in enviados[0][1]
    # A mesma mensagem reenviada pela Meta não gera resposta duplicada
    client.post("/webhook", json=payload_meta("oi"))
    assert len(enviados) == 1


def test_webhook_vaga_avisa_gabriel(client, enviados, monkeypatch):
    monkeypatch.setattr("app.main.NUMERO_GABRIEL", "5511974019394")
    client.post("/webhook", json=payload_meta("Olá, sou recrutadora e tenho uma vaga de React", id_msg="wamid.2"))
    destinos = [d for d, _ in enviados]
    assert "5511974019394" in destinos and "5511999990000" in destinos
    with client:  # leads exige token
        assert client.get("/leads").status_code == 401
        monkeypatch.setenv("ADMIN_TOKEN", "adm")
        leads = client.get("/leads", headers={"Authorization": "Bearer adm"}).json()
        assert leads and leads[0]["nome"] == "Ana Recrutadora"


def test_webhook_ignora_status_e_trata_audio(client, enviados):
    assert client.post("/webhook", json={"entry": [{"changes": [{"value": {"statuses": [{"id": "x"}]}}]}]}).status_code == 200
    assert enviados == []
    client.post("/webhook", json=payload_meta("", id_msg="wamid.3", tipo="audio"))
    assert "texto" in enviados[0][1]


def test_assinatura_invalida_e_recusada(client, monkeypatch):
    monkeypatch.setenv("WHATSAPP_APP_SECRET", "app-secret")
    corpo = b'{"entry": []}'
    assert client.post("/webhook", content=corpo, headers={"Content-Type": "application/json", "X-Hub-Signature-256": "sha256=errada"}).status_code == 403
    certa = "sha256=" + hmac.new(b"app-secret", corpo, hashlib.sha256).hexdigest()
    assert client.post("/webhook", content=corpo, headers={"Content-Type": "application/json", "X-Hub-Signature-256": certa}).status_code == 200


def test_extrai_mensagens_interativas():
    payload = {"entry": [{"changes": [{"value": {"messages": [
        {"from": "1", "id": "a", "type": "interactive", "interactive": {"button_reply": {"id": "b1", "title": "Projetos"}}}]}}]}]}
    assert whatsapp.extrair_mensagens(payload)[0].texto == "Projetos"


# ─── Chat do portfólio ──────────────────────────────────────

def test_chat_web_mantem_historico_e_limita(client):
    r = client.post("/chat", json={"mensagem": "oi", "sessao": "abcd-1234"})
    assert r.status_code == 200 and r.json()["fonte"] == "menu"
    for _ in range(12):
        ultimo = client.post("/chat", json={"mensagem": "3", "sessao": "abcd-1234"})
    assert ultimo.status_code == 429


def test_pergunta_longa_com_palavra_chave_vai_para_a_ia(monkeypatch):
    chamadas = []
    monkeypatch.setattr(assistente, "responder_com_ia", lambda h, m: chamadas.append(m) or assistente.Resposta(texto="ok", fonte="ia"))
    assert assistente.responder("Ele tem experiência com React?").fonte == "ia"
    assert assistente.responder("manda o currículo").fonte == "atalho"
    assert chamadas == ["Ele tem experiência com React?"]
