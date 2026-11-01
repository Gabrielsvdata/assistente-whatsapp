"""
Registro das conversas e dos contatos interessados (leads).

DATABASE_URL vazio usa SQLite local (assistente.db). Em produção, Postgres (Neon).
"""

import os
from datetime import UTC, datetime

from sqlalchemy import DateTime, Integer, String, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
from sqlalchemy.pool import StaticPool

_url = os.getenv("DATABASE_URL", "sqlite:///assistente.db").replace("postgres://", "postgresql://", 1)
if _url.startswith("postgresql://"):
    _url = _url.replace("postgresql://", "postgresql+psycopg2://", 1)
if _url.startswith("sqlite"):
    # Banco em memória compartilha uma única conexão; arquivo aceita várias threads
    _opcoes = {"connect_args": {"check_same_thread": False}}
    if ":memory:" in _url:
        _opcoes["poolclass"] = StaticPool
else:
    _opcoes = {"pool_pre_ping": True, "pool_recycle": 280}
engine = create_engine(_url, **_opcoes)


class Base(DeclarativeBase):
    pass


def agora() -> datetime:
    return datetime.now(UTC)


class Mensagem(Base):
    __tablename__ = "mensagens"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_whatsapp: Mapped[str | None] = mapped_column(String(120), unique=True, nullable=True)
    canal: Mapped[str] = mapped_column(String(20), default="whatsapp")
    contato: Mapped[str] = mapped_column(String(40), index=True)
    papel: Mapped[str] = mapped_column(String(10))  # user | assistant
    conteudo: Mapped[str] = mapped_column(Text)
    fonte: Mapped[str | None] = mapped_column(String(20), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)


class Lead(Base):
    __tablename__ = "leads"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    contato: Mapped[str] = mapped_column(String(40), index=True)
    nome: Mapped[str | None] = mapped_column(String(120), nullable=True)
    empresa: Mapped[str | None] = mapped_column(String(120), nullable=True)
    cargo: Mapped[str | None] = mapped_column(String(120), nullable=True)
    ultima_mensagem: Mapped[str] = mapped_column(Text)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora, onupdate=agora)


def criar_tabelas() -> None:
    Base.metadata.create_all(engine)


def ja_processada(sessao: Session, id_whatsapp: str) -> bool:
    return bool(id_whatsapp) and sessao.scalar(select(Mensagem.id).where(Mensagem.id_whatsapp == id_whatsapp)) is not None


def historico(sessao: Session, contato: str, limite: int = 10) -> list[dict]:
    linhas = sessao.scalars(
        select(Mensagem).where(Mensagem.contato == contato).order_by(Mensagem.id.desc()).limit(limite)
    ).all()
    return [{"role": m.papel, "content": m.conteudo} for m in reversed(linhas)]


def registrar(sessao: Session, contato: str, papel: str, conteudo: str, canal: str = "whatsapp",
              id_whatsapp: str | None = None, fonte: str | None = None) -> None:
    sessao.add(Mensagem(contato=contato, papel=papel, conteudo=conteudo, canal=canal,
                        id_whatsapp=id_whatsapp or None, fonte=fonte))


def salvar_lead(sessao: Session, contato: str, dados: dict, ultima_mensagem: str) -> Lead:
    """Cria ou completa o lead do contato, sem apagar o que já foi informado antes."""
    lead = sessao.scalar(select(Lead).where(Lead.contato == contato))
    if lead is None:
        lead = Lead(contato=contato, ultima_mensagem=ultima_mensagem)
        sessao.add(lead)
    for campo in ("nome", "empresa", "cargo"):
        valor = (dados.get(campo) or "").strip()
        if valor and valor.lower() != "null":
            setattr(lead, campo, valor[:120])
    lead.ultima_mensagem = ultima_mensagem[:2000]
    return lead
