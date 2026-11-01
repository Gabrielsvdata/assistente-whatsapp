# Assistente do portfólio (chat + WhatsApp)

Assistente com IA que responde, no chat do meu [portfólio](https://gabrielsilvano.pages.dev), perguntas de recrutadores sobre projetos, experiência, currículo e contato, usando **só dados reais** e registrando quem demonstra interesse em vaga. O mesmo código atende pelo WhatsApp (Meta Cloud API) quando um número é ligado.

**Teste:** abra o portfólio e clique em "Pergunte sobre mim".

[![CI](https://github.com/Gabrielsvdata/assistente-whatsapp/actions/workflows/ci.yml/badge.svg)](https://github.com/Gabrielsvdata/assistente-whatsapp/actions/workflows/ci.yml)

## Como funciona

```text
WhatsApp ──▶ Meta Cloud API ──▶ POST /webhook ──▶ assistente.responder()
                                                     │
                      ┌──────────────────────────────┼──────────────────────────────┐
                      ▼                              ▼                              ▼
              atalhos fixos                 IA (Groq) com o               detecção de vaga:
           (menu, 1-4, "currículo")      conhecimento.py como         registra o lead e manda
            sem custo, sem IA           única fonte de verdade        aviso no meu WhatsApp
                      └──────────────────────────────┴──────────────────────────────┘
                                                     ▼
                                  PostgreSQL (histórico e leads) ──▶ resposta no WhatsApp
```

Decisões:
- **A IA só responde com o que está em `app/conhecimento.py`.** Nada de inventar salário, datas ou tecnologias. Quando não sabe, manda falar comigo.
- **Atalhos antes da IA.** Menu, números e palavras-chave respondem sem custo e sem latência.
- **Sem Markdown nas respostas** (o WhatsApp não formata) e no máximo 600 caracteres.
- **Idempotência:** a Meta reenvia webhooks; cada mensagem é processada uma vez só (`id_whatsapp` único).
- **Assinatura verificada** (`X-Hub-Signature-256`) e **limite por contato** (10 mensagens/minuto).
- **Modelo escolhido automaticamente** na lista de preferência: se o Groq aposentar um, o próximo assume.

## Rotas

| Rota | Para quê |
|---|---|
| `GET /health` | verificação do Cloud Run |
| `GET /webhook` | verificação do webhook pela Meta (`hub.challenge`) |
| `POST /webhook` | mensagens do WhatsApp |
| `POST /chat` | o mesmo assistente para o site: `{"mensagem": "...", "sessao": "id-do-navegador"}` |
| `GET /leads` | contatos interessados (`Authorization: Bearer ADMIN_TOKEN`) |

## Rodar local

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env        # preencha o que tiver; sem GROQ_API_KEY o assistente responde só com menu e atalhos
uvicorn app.main:app --reload
pytest -q && ruff check .
```

Teste sem WhatsApp: `curl -X POST localhost:8000/chat -H 'Content-Type: application/json' -d '{"mensagem":"oi","sessao":"teste-1234"}'`

## Colocar no ar (Cloud Run + Meta)

1. **Cloud Run**: conecte este repositório (Dockerfile), região `southamerica-east1`, acesso público, mín. 0 / máx. 2 instâncias, e as variáveis de `.env.example`.
2. **Meta for Developers** → criar app do tipo *Business* → adicionar o produto **WhatsApp**.
3. Em **WhatsApp → Configuração da API**: copie o `Phone number ID` e gere um token (de preferência um *System User token* permanente). Coloque em `WHATSAPP_PHONE_NUMBER_ID` e `WHATSAPP_TOKEN`.
4. Em **Configuração → Webhooks**: URL `https://<seu-servico>.run.app/webhook`, *Verify token* = o mesmo valor de `WHATSAPP_VERIFY_TOKEN`; assine o campo `messages`.
5. `WHATSAPP_APP_SECRET` = *App secret* do app (Configurações → Básico).
6. Mande "oi" para o número e confira os registros no Cloud Run.

> Enquanto o app está em modo de desenvolvimento, só números cadastrados como testadores recebem mensagens. Para abrir ao público, verifique o negócio na Meta e publique o app.

## Stack

FastAPI · SQLAlchemy · PostgreSQL (Neon) · Groq · WhatsApp Cloud API · Docker · Google Cloud Run · GitHub Actions
