# Política de Segurança

O Criptotrade é um sistema financeiro (trading de cripto). Levamos segurança a
sério — mesmo em modo paper-trading, uma configuração insegura pode expor a API,
segredos ou, no futuro com trading real, capital.

## Versões suportadas

O projeto está em estágio **paper-trading / alpha**. Apenas o `master` recebe
correções de segurança.

## Reportando uma vulnerabilidade

**Não** abra uma issue pública para vulnerabilidades. Em vez disso:

- Envie um relatório privado por **[GitHub Security Advisories]**
  (`Security` → `Report a vulnerability` no repositório), ou
- contate o mantenedor do repositório diretamente.

Inclua: descrição, passos de reprodução, impacto potencial e, se possível, uma
sugestão de correção. Faremos o possível para responder rapidamente e coordenar
uma divulgação responsável após a correção.

[GitHub Security Advisories]: https://docs.github.com/pt/code-security/security-advisories

## Superfície e controles atuais

Controles já implementados (ver `docs/architecture/arquitetura.md §11` e a
auditoria `docs/auditoria-criptotrade-2026-06.md`):

- **Autenticação** por `X-API-Key` (`API_KEYS`), timing-safe
  (`secrets.compare_digest`), **fail-closed em produção** (a API recusa subir sem
  `API_KEYS` quando `APP_ENV=production`).
- **CORS** travável por `CORS_ORIGINS` (sem `*` em produção — validado na CI por
  `scripts/validate_deploy_config.py`).
- **Rate limiting** (`RateLimitMiddleware`, Redis opcional).
- **Headers de segurança** (CSP, HSTS, X-Frame-Options, etc.) via middleware + nginx.
- **Confirmação explícita** (`confirm: true`) para mutações de alto impacto.
- **Sem segredos no repo**: `.env` gitignored; CI roda `secret-scan`.
- **Paper-trading-first**: `EXCHANGE_DRY_RUN` obrigatório; zero rede de corretora
  por padrão.

## Boas práticas para operadores

- Gere um `API_KEYS` forte (`openssl rand -hex 32`) e nunca o commite.
- Só vire `EXCHANGE_DRY_RUN=false` como decisão deliberada, após validar a stack
  (ver `docs/acaoPendenteDono.md`).
- Mantenha `CORS_ORIGINS` restrito à origem real do console.
