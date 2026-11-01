"""
Cérebro do assistente: decide a resposta para cada mensagem.

Ordem:
1. Atalhos determinísticos (menu, números e palavras-chave): não dependem da IA.
2. Detecção de recrutador/vaga: registra o contato e avisa o Gabriel.
3. Pergunta livre: a IA responde só com o que está em conhecimento.py.
   Se a IA falhar, cai no menu.
"""

import json
import logging
import os
import re
import unicodedata
from dataclasses import dataclass, field

from app import conhecimento

logger = logging.getLogger(__name__)

MODELOS_PREFERIDOS = [
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "qwen/qwen3.8-27b",
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
]
_modelos_disponiveis: set[str] | None = None

PALAVRAS_VAGA = ("vaga", "oportunidade", "recrut", "entrevista", "processo seletivo", "contrat", "proposta", "head hunter", "headhunter", "talent")

ATALHOS = {
    "projetos": ("1", "projeto", "portfolio", "portfólio", "testar", "demo", "sispar", "petmind"),
    "experiencia": ("2", "experiencia", "experiência", "stack", "tecnologia", "curriculo resumido", "trabalha"),
    "contato": ("3", "curriculo", "currículo", "cv", "contato", "linkedin", "github", "email", "e-mail"),
    "humano": ("4", "falar com", "gabriel", "humano", "pessoa", "atendente", "ligar"),
}


@dataclass
class Resposta:
    texto: str
    fonte: str  # menu | atalho | vaga | ia | fallback
    lead: dict | None = None
    avisar_gabriel: bool = False
    extras: dict = field(default_factory=dict)


def normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", texto.lower()).strip()


def eh_saudacao(texto: str) -> bool:
    t = normalizar(texto)
    return t in {"oi", "ola", "bom dia", "boa tarde", "boa noite", "menu", "inicio", "start", "hey", "e ai", "eai", ""}


def atalho(texto: str) -> str | None:
    t = normalizar(texto)
    for nome, gatilhos in ATALHOS.items():
        if t in gatilhos:
            return nome
    if len(t.split()) <= 6:
        for nome, gatilhos in ATALHOS.items():
            if any(g in t for g in gatilhos if len(g) > 2):
                return nome
    return None


def parece_vaga(texto: str) -> bool:
    t = normalizar(texto)
    return any(p in t for p in PALAVRAS_VAGA)


def _cliente_groq():
    chave = os.getenv("GROQ_API_KEY", "").strip()
    if not chave:
        return None
    from groq import Groq

    return Groq(api_key=chave, max_retries=1, timeout=25.0)


def escolher_modelo(cliente) -> str:
    global _modelos_disponiveis
    forcado = os.getenv("GROQ_MODEL", "").strip()
    if forcado:
        return forcado
    if _modelos_disponiveis is None:
        try:
            _modelos_disponiveis = {m.id for m in cliente.models.list().data}
        except Exception:
            return MODELOS_PREFERIDOS[0]
    return next((m for m in MODELOS_PREFERIDOS if m in _modelos_disponiveis), MODELOS_PREFERIDOS[0])


PROMPT_SISTEMA = f"""Você é o assistente de WhatsApp do {conhecimento.NOME}, desenvolvedor Full Stack.
Quem fala com você costuma ser recrutador(a), tech lead ou alguém que viu o portfólio.

REGRAS
- Responda em português do Brasil, em tom simpático e direto, como mensagem de WhatsApp: no máximo 600 caracteres,
  sem Markdown (nada de **, # ou tabelas). Pode usar quebras de linha e no máximo 1 emoji.
- Use SOMENTE as informações abaixo. Se não souber, diga que não tem essa informação e ofereça falar com o Gabriel
  no WhatsApp {conhecimento.TELEFONE_HUMANO}.
- Nunca invente salário, pretensão, disponibilidade de datas, empresas ou tecnologias que não estão na lista.
- Inclua links só quando forem úteis para a pergunta, e sempre completos.
- Se a pessoa falar de vaga, proposta ou entrevista, demonstre interesse, peça nome, empresa e cargo (se faltarem)
  e diga que vai avisar o Gabriel.

Responda em JSON com as chaves:
{{"resposta": "<texto para enviar>", "eh_vaga": true|false, "nome": "<nome da pessoa ou null>",
  "empresa": "<empresa ou null>", "cargo": "<cargo ou null>"}}

INFORMAÇÕES SOBRE O GABRIEL
{conhecimento.PERFIL}
"""


def _sem_markdown(texto: str) -> str:
    return re.sub(r"[*_#`]+", "", texto or "").strip()


def responder_com_ia(historico: list[dict], mensagem: str) -> Resposta | None:
    cliente = _cliente_groq()
    if cliente is None:
        return None
    try:
        modelo = escolher_modelo(cliente)
        mensagens = [{"role": "system", "content": PROMPT_SISTEMA}]
        mensagens += [{"role": m["role"], "content": m["content"][:1000]} for m in historico[-8:]]
        mensagens.append({"role": "user", "content": mensagem[:1500]})
        parametros = dict(model=modelo, messages=mensagens, temperature=0.3, max_tokens=500,
                          response_format={"type": "json_object"})
        try:
            saida = cliente.chat.completions.create(**parametros, extra_body={"reasoning_effort": "low"})
        except Exception as erro:
            if getattr(erro, "status_code", None) != 400:
                raise
            saida = cliente.chat.completions.create(**parametros)
        conteudo = re.sub(r"<think>.*?</think>", "", saida.choices[0].message.content or "", flags=re.S)
        dados = json.loads(conteudo)
        texto = _sem_markdown(dados.get("resposta", ""))[:900]
        if not texto:
            return None
        lead = None
        if dados.get("eh_vaga") or any(dados.get(k) for k in ("empresa", "cargo")):
            lead = {"nome": dados.get("nome"), "empresa": dados.get("empresa"), "cargo": dados.get("cargo")}
        return Resposta(texto=texto, fonte="ia", lead=lead, avisar_gabriel=bool(dados.get("eh_vaga")),
                        extras={"modelo": modelo})
    except Exception:
        logger.exception("Falha na IA; usando resposta padrão")
        return None


def responder(mensagem: str, historico: list[dict] | None = None) -> Resposta:
    """Ponto único de decisão. `historico` são as mensagens anteriores desta conversa."""
    historico = historico or []
    if eh_saudacao(mensagem) and not historico:
        return Resposta(texto=conhecimento.MENU, fonte="menu")

    nome_atalho = atalho(mensagem)
    if nome_atalho:
        return Resposta(texto=conhecimento.RESPOSTAS_FIXAS[nome_atalho], fonte="atalho",
                        avisar_gabriel=(nome_atalho == "humano"))

    resposta = responder_com_ia(historico, mensagem)
    if resposta:
        if parece_vaga(mensagem):
            resposta.avisar_gabriel = True
            resposta.lead = resposta.lead or {"nome": None, "empresa": None, "cargo": None}
        return resposta

    if parece_vaga(mensagem):
        return Resposta(
            texto=("Que bom! O Gabriel vai gostar de saber 😊 Me passa seu nome, a empresa e o cargo da vaga "
                   f"que eu repasso agora. Se preferir, fala direto com ele: {conhecimento.TELEFONE_HUMANO}"),
            fonte="vaga", lead={"nome": None, "empresa": None, "cargo": None}, avisar_gabriel=True,
        )
    return Resposta(texto=conhecimento.MENU, fonte="fallback")
