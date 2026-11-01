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
    # Palavra-chave dentro de frase curta (ex.: 'manda o currículo'); perguntas maiores vão para a IA
    if len(t.split()) <= 3 or (len(t.split()) <= 6 and "?" not in texto):
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


PROMPT_SISTEMA = f"""Você é o assistente do {conhecimento.NOME}, desenvolvedor Full Stack. Fala em nome dele no chat do portfólio
e no WhatsApp. Quem conversa com você costuma ser recrutador(a), tech lead ou alguém que viu o portfólio.

COMO RESPONDER
- SEMPRE na mesma língua da última mensagem da pessoa: mensagem em inglês, resposta em inglês; em espanhol, em espanhol.
- Tom cordial e direto, sem bajulação e sem jargão de RH. Nunca comece com "Desculpe".
- Formato de mensagem de chat: até 500 caracteres, sem Markdown (nada de **, #, listas com "-" ou tabelas).
  Separe ideias com quebra de linha. No máximo 1 emoji, e só se couber bem.
- Responda PRIMEIRO à pergunta, com fatos concretos (projeto, tecnologia, resultado). Depois, se ajudar, UM link completo.
  Não cumprimente de novo se a conversa já começou.
- Em português, chame-o de "o Gabriel" (não "ele" solto) e use "avisar o Gabriel", nunca "avisar ele".
  Em inglês, apenas "Gabriel", sem artigo.
- Não exagere: o inglês dele é técnico (não diga fluente); não prometa disponibilidade que não está na lista.
- Termine com UMA pergunta no máximo. Nunca duas.
- Copie links exatamente como estão na lista, inclusive o "_" em curriculo_gabriel_silvano.pdf.
- Use SOMENTE as informações abaixo. Se não tiver a informação (salário, pretensão, datas, outras empresas ou
  tecnologias), diga isso com naturalidade e ofereça o contato direto: WhatsApp {conhecimento.TELEFONE_HUMANO}.
- Perguntas fora do tema (política, receitas, ajuda com código de terceiros): recuse em uma frase gentil e volte ao assunto.
- Se a pessoa falar de vaga, proposta ou entrevista: mostre interesse de forma sóbria, confirme o encaixe com 1 ou 2
  fatos concretos, e peça em UMA frase só o que faltar entre nome, empresa e cargo. Não peça requisitos nem benefícios.
  Diga que vai avisar o Gabriel. Quando já tiver nome, empresa e cargo, agradeça, diga que o Gabriel responde pelo
  WhatsApp ou e-mail e ofereça o currículo {conhecimento.CURRICULO}.

EXEMPLOS
Pergunta: "Ele tem experiência com React?"
Resposta: "Tem, e é o que ele mais usa hoje: React com TypeScript na Uiara Amazon Xperience e todo o front do FinVise,
finalista do hackathon Oracle (React 19, Tailwind, TanStack Query). Quer ver um projeto rodando? {conhecimento.PORTFOLIO}"

Pergunta: "Qual a pretensão salarial?"
Resposta: "Isso eu não tenho aqui, é um assunto que o Gabriel prefere tratar direto. Pode chamá-lo no WhatsApp
{conhecimento.TELEFONE_HUMANO} ou me passar seu contato que eu repasso."

Pergunta: "Sou a Ana, da Acme, temos vaga de dev pleno React/Node"
Resposta: "Que bom, Ana! A vaga combina: React/TypeScript no dia a dia e Node/Express em projetos como o Doação Solidária.
Vou avisar o Gabriel agora; ele te responde pelo WhatsApp ou e-mail. Se quiser adiantar, o currículo está em {conhecimento.CURRICULO}"

SAÍDA
Responda em JSON com as chaves:
{{"resposta": "<texto para enviar>", "eh_vaga": true|false, "nome": "<nome da pessoa ou null>",
  "empresa": "<empresa ou null>", "cargo": "<cargo ou null>"}}

INFORMAÇÕES SOBRE O GABRIEL
{conhecimento.PERFIL}
"""


def _limpar(texto: str) -> str:
    """Tira Markdown (sem mexer em "_" de URLs) e muletas como "Desculpe," no início."""
    texto = re.sub(r"\*\*|__|`|^#+\s*", "", texto or "", flags=re.M).strip()
    texto = re.sub(r"^(desculpe|desculpa|sorry)[,!]?\s*", "", texto, flags=re.I)
    return texto[:1].upper() + texto[1:] if texto else texto


def _json_da_resposta(conteudo: str) -> dict | None:
    """Lê o JSON mesmo que o modelo coloque texto ou ```json em volta."""
    conteudo = re.sub(r"<think>.*?</think>", "", conteudo or "", flags=re.S)
    inicio, fim = conteudo.find("{"), conteudo.rfind("}")
    if inicio == -1 or fim == -1:
        return None
    try:
        dados = json.loads(conteudo[inicio:fim + 1])
    except json.JSONDecodeError:
        return None
    return dados if isinstance(dados, dict) else None


def responder_com_ia(historico: list[dict], mensagem: str) -> Resposta | None:
    cliente = _cliente_groq()
    if cliente is None:
        return None
    try:
        modelo = escolher_modelo(cliente)
        mensagens = [{"role": "system", "content": PROMPT_SISTEMA}]
        mensagens += [{"role": m["role"], "content": m["content"][:1000]} for m in historico[-8:]]
        mensagens.append({"role": "user", "content": mensagem[:1500]})
        parametros = dict(model=modelo, messages=mensagens, temperature=0.2, max_tokens=450,
                          response_format={"type": "json_object"})
        try:
            saida = cliente.chat.completions.create(**parametros, extra_body={"reasoning_effort": "medium"})
        except Exception as erro:
            if getattr(erro, "status_code", None) != 400:
                raise
            saida = cliente.chat.completions.create(**parametros)
        dados = _json_da_resposta(saida.choices[0].message.content)
        if dados is None:
            logger.warning("IA devolveu algo fora do JSON: %r", (saida.choices[0].message.content or "")[:200])
            return None
        texto = _limpar(str(dados.get("resposta", ""))).replace("avisar ele", "avisar o Gabriel")[:700]
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
