"""
API do assistente.

- GET  /health            : verificação do Cloud Run
- GET  /webhook           : verificação do webhook pela Meta
- POST /webhook           : mensagens recebidas no WhatsApp
- POST /chat              : o mesmo assistente, para o widget do portfólio (sem WhatsApp)
- GET  /leads             : contatos interessados (exige ADMIN_TOKEN)
"""

import logging
import os
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import assistente, banco, conhecimento, whatsapp

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)



@asynccontextmanager
async def ciclo_de_vida(_app: FastAPI):
    banco.criar_tabelas()
    yield


app = FastAPI(title="Assistente do Gabriel", version="1.0.0", docs_url="/docs", lifespan=ciclo_de_vida)

origens = [o.strip().rstrip("/") for o in os.getenv("CORS_ALLOW_ORIGINS", "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origens or ["https://gabrielsilvano.pages.dev", "http://localhost:3000", "http://localhost:5173"],
    allow_methods=["GET", "POST", "OPTIONS"], allow_headers=["Content-Type", "Authorization"],
)

cliente_whatsapp = whatsapp.ClienteWhatsApp()
NUMERO_GABRIEL = os.getenv("NOTIFY_NUMBER", "").strip()  # ex.: 5511974019394

# Limite simples por contato: evita gastar IA com rajadas (10 mensagens por minuto)
_janelas: dict[str, deque] = defaultdict(deque)


def dentro_do_limite(contato: str, maximo: int = 10, segundos: int = 60) -> bool:
    fila = _janelas[contato]
    agora = time.time()
    while fila and agora - fila[0] > segundos:
        fila.popleft()
    if len(fila) >= maximo:
        return False
    fila.append(agora)
    return True


def sessao_db():
    with Session(banco.engine) as sessao:
        yield sessao


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "whatsapp": cliente_whatsapp.configurado, "ia": bool(os.getenv("GROQ_API_KEY"))}


# ───────────────────────── WhatsApp ─────────────────────────

@app.get("/webhook")
def verificar_webhook(
    modo: str | None = Query(None, alias="hub.mode"),
    token: str | None = Query(None, alias="hub.verify_token"),
    desafio: str | None = Query(None, alias="hub.challenge"),
):
    """A Meta chama esta rota uma vez, ao cadastrar o webhook, e espera o `hub.challenge` de volta."""
    esperado = os.getenv("WHATSAPP_VERIFY_TOKEN", "").strip()
    if modo == "subscribe" and esperado and token == esperado:
        return PlainTextResponse(desafio or "")
    raise HTTPException(status_code=403, detail="Token de verificação inválido")


def avisar_gabriel(texto: str) -> None:
    if NUMERO_GABRIEL:
        cliente_whatsapp.enviar_texto(NUMERO_GABRIEL, texto)


def tratar_mensagem(m: whatsapp.MensagemRecebida) -> None:
    with Session(banco.engine) as sessao:
        if banco.ja_processada(sessao, m.id):
            return
        cliente_whatsapp.marcar_lida(m.id)
        if m.tipo != "text" and not m.texto:
            texto = "Por enquanto só leio mensagens de texto 🙂 Me manda por escrito que eu respondo."
            banco.registrar(sessao, m.de, "user", f"[{m.tipo}]", id_whatsapp=m.id)
            banco.registrar(sessao, m.de, "assistant", texto, fonte="fallback")
            sessao.commit()
            cliente_whatsapp.enviar_texto(m.de, texto)
            return
        if not dentro_do_limite(m.de):
            banco.registrar(sessao, m.de, "user", m.texto, id_whatsapp=m.id)
            sessao.commit()
            return

        resposta = assistente.responder(m.texto, banco.historico(sessao, m.de))
        banco.registrar(sessao, m.de, "user", m.texto, id_whatsapp=m.id)
        banco.registrar(sessao, m.de, "assistant", resposta.texto, fonte=resposta.fonte)
        if resposta.lead is not None:
            lead = banco.salvar_lead(sessao, m.de, {**resposta.lead, "nome": resposta.lead.get("nome") or m.nome}, m.texto)
            if resposta.avisar_gabriel:
                avisar_gabriel(
                    f"📣 Contato pelo assistente\n"
                    f"Quem: {lead.nome or m.nome or 'não informado'} (+{m.de})\n"
                    f"Empresa: {lead.empresa or '—'} | Cargo: {lead.cargo or '—'}\n"
                    f"Mensagem: {m.texto[:400]}"
                )
        elif resposta.avisar_gabriel:
            avisar_gabriel(f"📣 {m.nome or m.de} (+{m.de}) quer falar com você: {m.texto[:400]}")
        sessao.commit()
    cliente_whatsapp.enviar_texto(m.de, resposta.texto)


@app.post("/webhook")
async def receber_webhook(request: Request, tarefas: BackgroundTasks,
                          assinatura: str | None = Header(None, alias="X-Hub-Signature-256")) -> dict:
    corpo = await request.body()
    if not whatsapp.assinatura_valida(corpo, assinatura):
        raise HTTPException(status_code=403, detail="Assinatura inválida")
    payload = await request.json()
    for m in whatsapp.extrair_mensagens(payload):
        tarefas.add_task(tratar_mensagem, m)
    # A Meta exige 200 rápido; o processamento segue em segundo plano
    return {"status": "recebido"}


# ───────────────────────── Widget do portfólio ─────────────────────────

class EntradaChat(BaseModel):
    mensagem: str = Field(min_length=1, max_length=1500)
    sessao: str = Field(min_length=4, max_length=80, description="ID gerado pelo navegador")


@app.post("/chat")
def chat(entrada: EntradaChat, sessao: Session = Depends(sessao_db)) -> dict:
    contato = f"web:{entrada.sessao}"
    if not dentro_do_limite(contato):
        raise HTTPException(status_code=429, detail="Muitas mensagens; espere um minuto.")
    resposta = assistente.responder(entrada.mensagem, banco.historico(sessao, contato))
    banco.registrar(sessao, contato, "user", entrada.mensagem, canal="web")
    banco.registrar(sessao, contato, "assistant", resposta.texto, canal="web", fonte=resposta.fonte)
    if resposta.lead is not None:
        banco.salvar_lead(sessao, contato, resposta.lead, entrada.mensagem)
        if resposta.avisar_gabriel:
            avisar_gabriel(f"📣 Contato pelo chat do portfólio ({contato}): {entrada.mensagem[:400]}")
    sessao.commit()
    return {"resposta": resposta.texto, "fonte": resposta.fonte, "whatsapp": conhecimento.WHATSAPP_LINK}


# ───────────────────────── Admin ─────────────────────────

def exigir_admin(authorization: str | None = Header(None)) -> None:
    esperado = os.getenv("ADMIN_TOKEN", "").strip()
    if not esperado or authorization != f"Bearer {esperado}":
        raise HTTPException(status_code=401, detail="Não autorizado")


@app.get("/leads", dependencies=[Depends(exigir_admin)])
def listar_leads(sessao: Session = Depends(sessao_db)) -> list[dict]:
    leads = sessao.scalars(select(banco.Lead).order_by(banco.Lead.atualizado_em.desc()).limit(200)).all()
    return [{"contato": lead.contato, "nome": lead.nome, "empresa": lead.empresa, "cargo": lead.cargo,
             "ultima_mensagem": lead.ultima_mensagem, "atualizado_em": lead.atualizado_em.isoformat()} for lead in leads]
