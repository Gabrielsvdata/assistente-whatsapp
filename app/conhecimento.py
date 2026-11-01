"""
Tudo que o assistente sabe sobre o Gabriel.

É a única fonte de verdade das respostas: a IA recebe este texto e só pode
responder com o que está aqui. Para atualizar o assistente, edite este arquivo.
"""

NOME = "Gabriel Silvano"
TELEFONE_HUMANO = "+55 11 97401-9394"
EMAIL = "gabrielsilvanovieira7@gmail.com"
PORTFOLIO = "https://gabrielsilvano.pages.dev"
LINKEDIN = "https://linkedin.com/in/gabriel-silvano-vieira"
GITHUB = "https://github.com/Gabrielsvdata"
CURRICULO = "https://gabrielsilvano.pages.dev/curriculo_gabriel_silvano.pdf"
WHATSAPP_LINK = "https://wa.me/5511974019394"

PERFIL = f"""
{NOME} é Desenvolvedor Full Stack em São Paulo (SP), Brasil.
- Hoje: Desenvolvedor Full Stack na Uiara Amazon Xperience (desde set/2026): React, TypeScript, Node.js e Python;
  implementação de sistemas, regras de negócio com as áreas e treinamento das equipes.
- Também: Analista de Suprimentos na Stone (desde 2021): dashboards em Metabase, SQL, auditoria de dados e
  automação de controles. Mais de 5 anos de operação e logística.
- Formação: Tecnólogo em Análise e Desenvolvimento de Sistemas (FATEC, concluído em 2026);
  Técnico em Logística (ETEC); Técnico em IA (IFNMG, em andamento).
- Idiomas: português nativo, inglês técnico.
- Modelo de trabalho: aberto a presencial, híbrido ou remoto. Disponível para conversar sobre vagas de
  desenvolvedor(a) Full Stack, Front-end (React) ou Back-end (Node/Python).

STACK
- Front-end: React, TypeScript, JavaScript, Tailwind CSS, TanStack Query, HTML e CSS.
- Back-end: Node.js e Express, Python com Flask e FastAPI, APIs REST, JWT.
- Dados: PostgreSQL, MySQL, SQLite, SQL, Metabase.
- Infra: Docker, Google Cloud Run (deploy contínuo), Cloudflare, Git e GitHub.
- IA: integrações com LLM via Groq (modelos de texto e visão); Claude Code, Cursor e Codex no dia a dia.

PROJETOS (todos com link no portfólio {PORTFOLIO})
- SisPar: sistema de reembolsos corporativos. A IA de visão lê o comprovante; o código valida valor, data e
  categoria e gera um score de confiabilidade. Login por perfil (colaborador e gestor) e chatbot.
  Python/Flask, PostgreSQL, React, Docker, Cloud Run. Teste com login de demonstração:
  https://sispar.gabrielsilvanovieira7.workers.dev
- Petmind: registro de comportamento de pets; a API calcula métricas e tendências e a IA escreve o diagnóstico.
  FastAPI, SQLAlchemy, PostgreSQL, 34 testes, mypy strict. Teste: https://petmind-front.gabrielsilvanovieira7.workers.dev
- FinVise: plataforma de inteligência financeira, finalista do hackathon Oracle (No Country). Gabriel fez todo
  o front-end e a identidade visual (React 19, TypeScript, Tailwind, TanStack Query), em time.
- Club Sette: e-commerce de camisas de futebol desenvolvido sob encomenda e vendido ao cliente
  (React, TypeScript, Supabase).
- Skills de onboarding: kit open source para Claude Code, Codex e Cursor ajudarem devs recém-chegados a
  entender sistemas: https://github.com/Gabrielsvdata/dev-onboarding-skills
- Winchester: fan game beat 'em up em pixel art, feito só com Canvas e Web Audio: https://gabrielsvdata.itch.io/winchester
- Doação Solidária: API Node.js/Express que prioriza doações para as instituições mais urgentes, com Swagger.
- Este assistente: automação do WhatsApp em FastAPI + WhatsApp Cloud API + Groq, rodando no Cloud Run,
  com registro de contatos e repasse para o Gabriel.

CONTATO
- WhatsApp direto com o Gabriel: {TELEFONE_HUMANO}
- E-mail: {EMAIL}
- LinkedIn: {LINKEDIN}
- GitHub: {GITHUB}
- Currículo em PDF: {CURRICULO}
"""

MENU = (
    f"Oi! Sou o assistente do {NOME} 🤖\n\n"
    "Posso te contar sobre:\n"
    "1️⃣ Projetos e links para testar\n"
    "2️⃣ Experiência e stack\n"
    "3️⃣ Currículo e contatos\n"
    "4️⃣ Falar direto com o Gabriel\n\n"
    "Pode digitar o número ou perguntar do seu jeito. "
    "Se for sobre uma vaga, me conta a empresa e o cargo que eu já aviso o Gabriel."
)

RESPOSTAS_FIXAS = {
    "projetos": (
        "Projetos para testar agora, sem cadastro:\n\n"
        "• SisPar (reembolsos com IA): https://sispar.gabrielsilvanovieira7.workers.dev\n"
        "• Petmind (comportamento de pets com IA): https://petmind-front.gabrielsilvanovieira7.workers.dev\n"
        "• Winchester (jogo em pixel art): https://gabrielsvdata.itch.io/winchester\n\n"
        f"Todos, com código e explicação, em {PORTFOLIO}"
    ),
    "experiencia": (
        "Gabriel é Dev Full Stack na Uiara Amazon Xperience (React, TypeScript, Node e Python) "
        "e trabalha com dados na Stone (SQL e Metabase) desde 2021.\n\n"
        "Stack: React, TypeScript, Tailwind, Node/Express, Python (Flask e FastAPI), "
        "PostgreSQL/MySQL, Docker, Google Cloud Run e integrações com IA.\n\n"
        f"Detalhes: {LINKEDIN}"
    ),
    "contato": (
        f"📄 Currículo: {CURRICULO}\n"
        f"💼 LinkedIn: {LINKEDIN}\n"
        f"💻 GitHub: {GITHUB}\n"
        f"✉️ E-mail: {EMAIL}"
    ),
    "humano": (
        f"Claro! Fala direto com o Gabriel no WhatsApp {TELEFONE_HUMANO} "
        f"ou pelo e-mail {EMAIL}. Se preferir, me diz seu nome e o assunto que eu repasso agora."
    ),
}
