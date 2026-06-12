# Ações Pendentes do Dono

> **O que é isto:** itens que dependem de **você** (DNS, segredos, contas externas,
> decisões de negócio). O agente implementa tudo que consegue sem esses acessos;
> esta lista é o que falta para **ligar e testar em produção**. Trabalhe de cima
> para baixo — a seção 🔴 desbloqueia o deploy; as demais ampliam o sistema.
>
> Última atualização: 2026-06-12.

---

## 🔴 Bloqueia produção — deploy TLS (P3-2, já em `master`)

- [ ] **DNS**: aponte `criptotrade.buildtovalue.cloud` (A/AAAA) para o IP do host de deploy.
- [ ] **Firewall/host**: abra as portas **80** e **443** (HTTP-01 do Let's Encrypt usa a 80; o tráfego real usa a 443).
- [ ] **`.env` no host**: `cp .env.prod.example .env` e defina um **`API_KEYS` forte** — ex.: `openssl rand -hex 32`. O app **recusa subir** em produção sem isso (guard fail-closed).
- [ ] **Emitir certificado** (uma vez): `./deploy/init-letsencrypt.sh` (precisa do DNS já propagado + portas abertas).
- [ ] **Subir a stack**: `docker compose -f docker-compose.prod.yml up -d --build` (`--build` embute o console).
- [ ] **Smoke test** (no host): `curl -I https://criptotrade.buildtovalue.cloud/health` → 200 + header `Strict-Transport-Security`; `http://…` deve dar **301**; portas internas (8000/8501/9090) **não** acessíveis de fora.

## 🟠 Decisões de produto

- [ ] **Ir a real (`EXCHANGE_DRY_RUN`)**: hoje está **`true`** (dados sintéticos, zero rede de corretora) em todos os composes. Virar para `false` é uma decisão deliberada — só depois de validar a stack e as credenciais da corretora. **Não** vire junto com o deploy.
- [ ] **Autenticação do Console (P3-1)**: o console no browser precisa de uma **API key** (`window.API_KEY`) para chamar `/v1/*` protegido — sem ela, as chamadas retornam 401. Decida a UX: tela de login, injeção da key no build, ou um proxy que adiciona o header. (Hoje o console sobe e renderiza, mas os dados protegidos não carregam sem key.)
- [ ] **Console React vs Streamlit**: o React (`docs/design/pages`) agora tem build de produção e é servido pelo nginx, mas a UI operacional atual é o Streamlit. Decida se o React passa a ser a UI primária (isso prioriza P3-4 — cliente tipado — e o E2E do P3-5).

## 🟡 Contas / credenciais externas (desbloqueiam itens do roadmap)

- [ ] **Sentry DSN (P3-3)**: crie um projeto no Sentry e forneça o **DSN** (uma env, ex.: `SENTRY_DSN`). O agente vai deixar o SDK wired e inerte sem DSN; com o DSN, os 5xx passam a ser reportados.
- [ ] **Pipeline de deploy / CD (P3-6)**: para "deploy no merge" é preciso que você proveja **host de deploy + forma de acesso** (chave SSH ou registry de imagens) e cadastre os **GitHub Secrets** correspondentes. O agente faz a parte de **validação de config pré-deploy** na CI; o passo que efetivamente publica no seu host depende desses segredos.

---

### Como o agente registra aqui
Sempre que uma tarefa do roadmap esbarrar em algo que só você pode fazer, o item
entra nesta lista (com contexto e o "como"), e o agente **segue para a próxima
atividade** em vez de travar. No fim, esta página é o seu checklist de configuração.
