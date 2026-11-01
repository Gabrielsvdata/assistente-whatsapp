"""
Cliente da WhatsApp Cloud API (Meta) e leitura dos webhooks.

Variáveis de ambiente:
- WHATSAPP_TOKEN: token de acesso do app na Meta.
- WHATSAPP_PHONE_NUMBER_ID: ID do número (não é o telefone).
- WHATSAPP_VERIFY_TOKEN: texto que você inventa e repete no painel da Meta ao cadastrar o webhook.
- WHATSAPP_APP_SECRET: segredo do app, usado para validar a assinatura dos webhooks (opcional em dev).
"""

import hashlib
import hmac
import logging
import os
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

VERSAO_API = os.getenv("WHATSAPP_API_VERSION", "v21.0")


@dataclass
class MensagemRecebida:
    id: str
    de: str  # telefone de quem mandou, em formato internacional sem "+"
    nome: str
    texto: str
    tipo: str


def extrair_mensagens(payload: dict) -> list[MensagemRecebida]:
    """Lê o payload do webhook e devolve só as mensagens novas (ignora status de entrega)."""
    mensagens = []
    for entrada in payload.get("entry", []):
        for mudanca in entrada.get("changes", []):
            valor = mudanca.get("value", {})
            nomes = {c.get("wa_id"): c.get("profile", {}).get("name", "") for c in valor.get("contacts", [])}
            for m in valor.get("messages", []):
                tipo = m.get("type", "")
                if tipo == "text":
                    texto = m.get("text", {}).get("body", "")
                elif tipo == "interactive":
                    inter = m.get("interactive", {})
                    texto = (inter.get("button_reply") or inter.get("list_reply") or {}).get("title", "")
                elif tipo == "button":
                    texto = m.get("button", {}).get("text", "")
                else:
                    texto = ""
                mensagens.append(MensagemRecebida(
                    id=m.get("id", ""), de=m.get("from", ""), nome=nomes.get(m.get("from", ""), ""),
                    texto=texto, tipo=tipo,
                ))
    return mensagens


def assinatura_valida(corpo: bytes, cabecalho: str | None) -> bool:
    """Confere o X-Hub-Signature-256. Sem APP_SECRET configurado, aceita (útil em desenvolvimento)."""
    segredo = os.getenv("WHATSAPP_APP_SECRET", "").strip()
    if not segredo:
        return True
    if not cabecalho or not cabecalho.startswith("sha256="):
        return False
    esperado = hmac.new(segredo.encode(), corpo, hashlib.sha256).hexdigest()
    return hmac.compare_digest(esperado, cabecalho.split("=", 1)[1])


class ClienteWhatsApp:
    def __init__(self) -> None:
        self.token = os.getenv("WHATSAPP_TOKEN", "").strip()
        self.phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "").strip()

    @property
    def configurado(self) -> bool:
        return bool(self.token and self.phone_number_id)

    def _url(self) -> str:
        return f"https://graph.facebook.com/{VERSAO_API}/{self.phone_number_id}/messages"

    def _enviar(self, corpo: dict) -> dict | None:
        if not self.configurado:
            logger.warning("WhatsApp não configurado; mensagem não enviada: %s", corpo)
            return None
        resposta = httpx.post(self._url(), json=corpo, timeout=20.0,
                              headers={"Authorization": f"Bearer {self.token}"})
        if resposta.status_code >= 400:
            logger.error("Erro ao enviar WhatsApp (%s): %s", resposta.status_code, resposta.text[:300])
            return None
        return resposta.json()

    def enviar_texto(self, para: str, texto: str) -> dict | None:
        return self._enviar({
            "messaging_product": "whatsapp", "to": para, "type": "text",
            "text": {"preview_url": True, "body": texto[:4000]},
        })

    def marcar_lida(self, id_mensagem: str) -> None:
        if self.configurado and id_mensagem:
            self._enviar({"messaging_product": "whatsapp", "status": "read", "message_id": id_mensagem})
