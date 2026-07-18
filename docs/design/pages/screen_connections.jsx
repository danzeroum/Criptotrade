/* ============================================================
   A5 — Conexões & Chaves (manage_keys/admin; oculta no demo).
   Conexões de exchange: credenciais cifradas (key mascarada,
   secret NUNCA volta), escopo read/trade com aviso forte +
   confirmação digitada "TRADE", testnet recomendado, teste real
   read-only com permissões detectadas, rotacionar (com CTA de
   re-teste — o modo live não sobe sem teste ok) e revogar.
   Chaves da plataforma: escopadas por papel, exibidas UMA vez.
   ============================================================ */
const { useState: useConnState, useEffect: useConnEffect, useCallback: useConnCallback } = React;

const EXCHANGES_COMMON = ['binance', 'kraken', 'coinbase', 'bybit', 'okx', 'kucoin'];
const KEY_SCOPES_UI = [
  { id: 'visualizador', label: 'Visualizador (somente leitura)' },
  { id: 'operador', label: 'Operador (aprova ordens, autonomia)' },
  { id: 'admin', label: 'Admin (tudo, exceto gestão de usuários)' },
];

function TestDetail({ detail, ok }) {
  if (!detail) return null;
  if (!ok) {
    return <span style={{ fontSize: 11.5, color: 'var(--down)' }}>{detail.error}</span>;
  }
  const trade = detail.trade_detected;
  return (
    <span style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
      <Badge variant="ok" dot={false}>leitura ok</Badge>
      {trade === true && <Badge variant="warn" dot={false}>trade ok</Badge>}
      {trade === false && <Badge variant="neutral" dot={false}>trade bloqueado na exchange</Badge>}
      {trade == null && <Badge variant="neutral" dot={false}
        data-tip="A exchange não expõe essa informação — será validado no primeiro uso">
        trade não verificável
      </Badge>}
    </span>
  );
}

function ConnectionModal({ onClose, onSaved, addToast }) {
  const mock = !!window.USE_MOCK_DATA;
  const [form, setForm] = useConnState({
    exchange_id: 'binance', label: '', api_key: '', api_secret: '',
    scope: 'read', testnet: true, confirm: '',
  });
  const [busy, setBusy] = useConnState(false);
  const [error, setError] = useConnState(null);
  const tradeReady = form.scope !== 'trade' || form.confirm === 'TRADE';

  const submit = async (e) => {
    e.preventDefault();
    if (mock) { addToast?.('Modo demo: ação não aplicada.', 'info'); onClose?.(); return; }
    setBusy(true); setError(null);
    try {
      const body = { ...form };
      if (form.scope !== 'trade') delete body.confirm;
      await CT_API.createConnection(body);
      addToast?.('Conexão adicionada — rode "Testar" para validá-la.', 'check');
      onSaved?.(); onClose?.();
    } catch (err) { setError(err?.message ?? 'Não foi possível salvar.'); setBusy(false); }
  };

  return (
    <div className="lock-overlay" role="dialog" aria-label="Nova conexão" onClick={onClose}>
      <div className="auth-card" style={{ maxWidth: 440, maxHeight: '88vh', overflowY: 'auto' }}
        onClick={e => e.stopPropagation()}>
        <h2 style={{ fontSize: 15, fontWeight: 600, marginBottom: 12 }}>Conectar exchange</h2>
        <form onSubmit={submit}>
          {error && <div className="auth-error" role="alert">{error}</div>}
          <div style={{ display: 'flex', gap: 10 }}>
            <label className="auth-field" style={{ flex: 1 }}>
              <span className="label-xs">Exchange (id ccxt)</span>
              <input className="auth-input" list="ct-exchanges" required value={form.exchange_id}
                onChange={e => setForm(f => ({ ...f, exchange_id: e.target.value }))} />
              <datalist id="ct-exchanges">
                {EXCHANGES_COMMON.map(x => <option key={x} value={x} />)}
              </datalist>
            </label>
            <label className="auth-field" style={{ flex: 1 }}>
              <span className="label-xs">Nome</span>
              <input className="auth-input" required maxLength={60} value={form.label}
                placeholder="ex.: Binance principal"
                onChange={e => setForm(f => ({ ...f, label: e.target.value }))} />
            </label>
          </div>
          <label className="auth-field">
            <span className="label-xs">API key</span>
            <input className="auth-input" required minLength={6} value={form.api_key}
              autoComplete="off"
              onChange={e => setForm(f => ({ ...f, api_key: e.target.value }))} />
          </label>
          <label className="auth-field">
            <span className="label-xs">API secret 🔒 (nunca será exibido de novo)</span>
            <input className="auth-input" type="password" required minLength={6}
              value={form.api_secret} autoComplete="off"
              onChange={e => setForm(f => ({ ...f, api_secret: e.target.value }))} />
          </label>
          <label style={{ display: 'flex', gap: 7, alignItems: 'flex-start', fontSize: 12.5,
                          margin: '2px 0 10px' }}>
            <input type="checkbox" checked={form.testnet} style={{ marginTop: 2 }}
              onChange={e => setForm(f => ({ ...f, testnet: e.target.checked }))} />
            <span><b>Testnet/sandbox</b> — recomendado: valide o fluxo completo em
              testnet antes de apontar para a conta real.</span>
          </label>
          <div className="auth-field">
            <span className="label-xs">Escopo</span>
            <div style={{ display: 'flex', gap: 14, paddingTop: 4, fontSize: 12.5 }}>
              <label style={{ display: 'flex', gap: 5, alignItems: 'center' }}>
                <input type="radio" name="scope" checked={form.scope === 'read'}
                  onChange={() => setForm(f => ({ ...f, scope: 'read', confirm: '' }))} />
                Somente leitura
              </label>
              <label style={{ display: 'flex', gap: 5, alignItems: 'center' }}>
                <input type="radio" name="scope" checked={form.scope === 'trade'}
                  onChange={() => setForm(f => ({ ...f, scope: 'trade' }))} />
                Trade
              </label>
            </div>
          </div>
          {form.scope === 'trade' && (
            <div style={{
              border: '1px solid var(--down-line)', background: 'var(--down-bg)',
              borderRadius: 'var(--r)', padding: 12, marginBottom: 10,
            }} data-testid="trade-warning">
              <div style={{ display: 'flex', gap: 8, alignItems: 'center', fontWeight: 600,
                            fontSize: 13, color: 'var(--down)', marginBottom: 6 }}>
                <Icon name="alert" size={15} /> Escopo de trade — leia antes de continuar
              </div>
              <p style={{ fontSize: 12.5, lineHeight: 1.6, margin: '0 0 10px' }}>
                Com este escopo, o sistema passa a poder <b>enviar e cancelar ordens
                reais com o seu dinheiro</b> nesta exchange (respeitando guardrails,
                circuit breaker e HITL — mas as ordens são reais). Prefira criar a
                chave na exchange <b>sem permissão de saque</b> e travada no IP de
                egresso mostrado nesta tela.
              </p>
              <label className="auth-field" style={{ margin: 0 }}>
                <span className="label-xs">Digite TRADE para confirmar</span>
                <input className="auth-input" value={form.confirm} autoComplete="off"
                  onChange={e => setForm(f => ({ ...f, confirm: e.target.value }))} />
              </label>
            </div>
          )}
          <div style={{ display: 'flex', gap: 8 }}>
            <Btn variant="primary" size="sm" disabled={busy || !tradeReady}>
              {busy ? '…' : 'Conectar'}
            </Btn>
            <Btn variant="ghost" size="sm" type="button" onClick={onClose}>Cancelar</Btn>
          </div>
        </form>
      </div>
    </div>
  );
}

function RotateModal({ conn, onClose, onRotated, addToast }) {
  const mock = !!window.USE_MOCK_DATA;
  const [secret, setSecret] = useConnState('');
  const [key, setKey] = useConnState('');
  const [busy, setBusy] = useConnState(false);
  const [error, setError] = useConnState(null);

  const submit = async (e) => {
    e.preventDefault();
    if (mock) { addToast?.('Modo demo: ação não aplicada.', 'info'); onClose?.(); return; }
    setBusy(true); setError(null);
    try {
      const body = { api_secret: secret };
      if (key) body.api_key = key;
      await CT_API.rotateConnection(conn.id, body);
      onRotated?.(conn);
      onClose?.();
    } catch (err) { setError(err?.message ?? 'Falha ao rotacionar.'); setBusy(false); }
  };

  return (
    <div className="lock-overlay" role="dialog" aria-label="Rotacionar secret" onClick={onClose}>
      <div className="auth-card" style={{ maxWidth: 400 }} onClick={e => e.stopPropagation()}>
        <h2 style={{ fontSize: 15, fontWeight: 600, marginBottom: 8 }}>
          Rotacionar — {conn.label}
        </h2>
        <p style={{ fontSize: 12.5, color: 'var(--ink-2)', lineHeight: 1.6, marginBottom: 10 }}>
          A rotação zera o status de teste desta conexão.
          {conn.is_active && conn.scope === 'trade' && (
            <b> Ela é a conexão ativa de trade: o modo live não sobe até um novo
            teste ok.</b>
          )}
        </p>
        <form onSubmit={submit}>
          {error && <div className="auth-error" role="alert">{error}</div>}
          <label className="auth-field">
            <span className="label-xs">Nova API key (opcional — vazio mantém a atual)</span>
            <input className="auth-input" value={key} autoComplete="off"
              onChange={e => setKey(e.target.value)} />
          </label>
          <label className="auth-field">
            <span className="label-xs">Novo API secret 🔒</span>
            <input className="auth-input" type="password" required minLength={6}
              value={secret} autoComplete="off" onChange={e => setSecret(e.target.value)} />
          </label>
          <div style={{ display: 'flex', gap: 8 }}>
            <Btn variant="primary" size="sm" disabled={busy}>{busy ? '…' : 'Rotacionar'}</Btn>
            <Btn variant="ghost" size="sm" type="button" onClick={onClose}>Cancelar</Btn>
          </div>
        </form>
      </div>
    </div>
  );
}

function KeyCreatedModal({ created, onClose }) {
  return (
    <div className="lock-overlay" role="dialog" aria-label="Chave criada" onClick={onClose}>
      <div className="auth-card" style={{ maxWidth: 440 }} onClick={e => e.stopPropagation()}>
        <h2 style={{ fontSize: 15, fontWeight: 600, marginBottom: 6 }}>
          Chave “{created.label}” criada
        </h2>
        <p style={{ fontSize: 12.5, color: 'var(--ink-2)', lineHeight: 1.6, marginBottom: 10 }}>
          Copie agora — a chave completa <b>não será exibida novamente</b> (guardamos
          apenas um hash).
        </p>
        <div data-testid="platform-key-value" style={{
          fontFamily: 'var(--mono)', fontSize: 13, background: 'var(--bg)',
          border: '1px solid var(--border)', borderRadius: 'var(--r)',
          padding: '10px 12px', marginBottom: 14, wordBreak: 'break-all', userSelect: 'all',
        }}>{created.key}</div>
        <Btn variant="primary" size="sm" onClick={onClose}>Copiei a chave</Btn>
      </div>
    </div>
  );
}

function ScreenConnections({ addToast }) {
  const mock = !!window.USE_MOCK_DATA;
  const [conns, setConns] = useConnState(mock ? (CT.connections ?? []) : null);
  const [keys, setKeys] = useConnState(mock ? (CT.platformKeys ?? []) : null);
  const [egress, setEgress] = useConnState(mock ? { ip: '203.0.113.42', cached: true } : null);
  const [loading, setLoading] = useConnState(!mock);
  const [error, setError] = useConnState(null);
  const [connecting, setConnecting] = useConnState(false);
  const [rotating, setRotating] = useConnState(null);
  const [testing, setTesting] = useConnState(null);
  const [keyDraft, setKeyDraft] = useConnState(null);
  const [keyCreated, setKeyCreated] = useConnState(null);

  const load = useConnCallback(() => {
    if (mock) return;
    setLoading(true);
    Promise.all([CT_API.getConnections(), CT_API.getPlatformKeys(),
                 CT_API.getEgressIp().catch(() => null)])
      .then(([c, k, ip]) => {
        setConns(c ?? []); setKeys(k ?? []); setEgress(ip);
        setLoading(false); setError(null);
      })
      .catch(e => { setError(e); setLoading(false); });
  }, [mock]);

  useConnEffect(() => { load(); }, [load]);

  const act = async (fn, okMsg) => {
    if (mock) { addToast?.('Modo demo: ação não aplicada.', 'info'); return; }
    try { await fn(); if (okMsg) addToast?.(okMsg, 'check'); load(); }
    catch (e) { addToast?.(e?.message ?? 'Falha na ação.', 'alert'); }
  };

  const runTest = async (conn) => {
    if (mock) { addToast?.('Teste executado (demo).', 'check'); return; }
    setTesting(conn.id);
    try {
      const r = await CT_API.testConnection(conn.id);
      addToast?.(r.ok
        ? `✅ ${conn.label}: leitura ok${r.trade_detected ? ' · trade ok' : ''}.`
        : `Teste falhou: ${r.error}`, r.ok ? 'check' : 'alert');
      load();
    } catch (e) { addToast?.(e?.message ?? 'Falha no teste.', 'alert'); }
    finally { setTesting(null); }
  };

  // Nota 2 da revisão: pós-rotate, encadeia o CTA de teste imediato.
  const onRotated = (conn) => {
    load();
    addToast?.(`Secret rotacionado. Teste a conexão agora${
      conn.is_active && conn.scope === 'trade'
        ? ' — o modo live não sobe até um teste ok' : ''}.`, 'alert');
  };

  if (loading) return <LoadingState label="Carregando conexões…" />;
  if (error) return <ErrorState message="Erro ao carregar conexões" onRetry={load} />;

  const activeKeys = (keys ?? []).filter(k => !k.revoked);

  return (
    <div>
      <div className="page-head">
        <div>
          <h1 className="page-title">Conexões & Chaves</h1>
          <div className="page-sub">Credenciais de exchange e chaves de acesso à plataforma</div>
        </div>
        <Btn variant="primary" size="sm" onClick={() => setConnecting(true)}>
          <Icon name="plus" size={13} /> Conectar exchange
        </Btn>
      </div>

      {/* ------------------------------------------------------ connections */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-head">
          <span className="card-title"><Icon name="zap" />Conexões de exchange</span>
          <Badge variant="neutral" dot={false}>{(conns ?? []).length} conexão(ões)</Badge>
        </div>
        <div className="card-pad" style={{ padding: '6px 16px 12px' }}>
          {(conns ?? []).filter(c => !c.revoked).map(c => (
            <div key={c.id} style={{ borderBottom: '1px solid var(--border)', padding: '12px 0' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, flexWrap: 'wrap' }}>
                <span style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                  <span style={{ fontWeight: 600 }}>{c.label}</span>
                  <Badge variant="neutral" dot={false}>{c.exchange_id}</Badge>
                  <Badge variant={c.scope === 'trade' ? 'warn' : 'info'} dot={false}>
                    {c.scope === 'trade' ? 'trade' : 'somente leitura'}
                  </Badge>
                  <Badge variant={c.testnet ? 'neutral' : 'down'} dot={false}>
                    {c.testnet ? 'testnet' : 'REAL'}
                  </Badge>
                  {c.is_active && <Badge variant="ok" dot={false}>Ativa</Badge>}
                  <span style={{ fontFamily: 'var(--mono)', fontSize: 12, color: 'var(--ink-3)' }}>
                    key {c.api_key_masked}
                  </span>
                </span>
                <span style={{ whiteSpace: 'nowrap' }}>
                  <Btn variant="ghost" size="sm" disabled={testing === c.id}
                    onClick={() => runTest(c)}>
                    {testing === c.id ? 'Testando…' : 'Testar'}
                  </Btn>
                  {!c.is_active && (
                    <Btn variant="ghost" size="sm"
                      onClick={() => act(() => CT_API.activateConnection(c.id),
                        `${c.label} agora é a conexão ativa.`)}>
                      Ativar
                    </Btn>
                  )}
                  <Btn variant="ghost" size="sm" onClick={() => setRotating(c)}>Rotacionar</Btn>
                  <Btn variant="ghost" size="sm"
                    onClick={() => act(() => CT_API.revokeConnection(c.id), 'Conexão revogada.')}>
                    Revogar
                  </Btn>
                </span>
              </div>
              <div style={{ marginTop: 6, display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                {c.last_test_at == null
                  ? <Badge variant="warn" dot={false}>nunca testada — rode “Testar”</Badge>
                  : <>
                      <Badge variant={c.last_test_ok ? 'ok' : 'down'} dot={false}>
                        teste {c.last_test_ok ? 'ok' : 'falhou'} · {fmtDateTime(c.last_test_at)}
                      </Badge>
                      <TestDetail detail={c.last_test_detail} ok={c.last_test_ok} />
                    </>}
              </div>
            </div>
          ))}
          {(conns ?? []).filter(c => !c.revoked).length === 0 && (
            <EmptyState label="Nenhuma conexão"
              sub="Sem conexão gerida, o sistema segue no fallback por variáveis de ambiente (somente paper)." />
          )}
        </div>
      </div>

      {/* -------------------------------------------------------- egress IP */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-pad" style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
          <Icon name="shield" size={15} style={{ color: 'var(--ink-3)', flexShrink: 0 }} />
          <p style={{ fontSize: 12.5, color: 'var(--ink-2)', margin: 0, flex: 1, minWidth: 260 }}>
            <b>Proteção recomendada:</b> no painel da exchange, restrinja a chave ao
            IP de egresso desta VPS{egress?.ip
              ? <> — <span style={{ fontFamily: 'var(--mono)' }}>{egress.ip}</span></>
              : <> ({egress?.error ?? 'detectando…'})</>}.
            Assim, mesmo vazada, a chave não funciona de outro lugar.
          </p>
        </div>
      </div>

      {/* ---------------------------------------------------- platform keys */}
      <div className="card">
        <div className="card-head">
          <span className="card-title"><Icon name="lock" />Chaves da plataforma</span>
          <Btn variant="ghost" size="sm" onClick={() =>
            setKeyDraft({ label: '', scope: 'visualizador' })}>
            <Icon name="plus" size={13} /> Criar chave
          </Btn>
        </div>
        <div style={{ overflowX: 'auto' }}>
          <table className="tbl">
            <thead>
              <tr>
                <th style={{ textAlign: 'left' }}>Chave</th>
                <th style={{ textAlign: 'left' }}>Escopo</th>
                <th style={{ textAlign: 'left' }}>Último uso</th>
                <th style={{ textAlign: 'left' }}>Criada</th>
                <th style={{ textAlign: 'right' }}>Ações</th>
              </tr>
            </thead>
            <tbody>
              {activeKeys.map(k => (
                <tr key={k.id}>
                  <td>
                    <div style={{ fontWeight: 500 }}>{k.label}</div>
                    <div style={{ fontFamily: 'var(--mono)', fontSize: 11.5, color: 'var(--ink-3)' }}>
                      {k.key_prefix}…
                    </div>
                  </td>
                  <td><Badge variant={{ visualizador: 'neutral', operador: 'info', admin: 'violet' }[k.scope]} dot={false}>{k.scope}</Badge></td>
                  <td style={{ fontFamily: 'var(--mono)', fontSize: 12 }}>
                    {k.last_used_at ? fmtDateTime(k.last_used_at) : 'nunca'}
                  </td>
                  <td style={{ fontFamily: 'var(--mono)', fontSize: 12 }}>{fmtDateTime(k.created_at)}</td>
                  <td style={{ textAlign: 'right' }}>
                    <Btn variant="ghost" size="sm"
                      onClick={() => act(() => CT_API.revokePlatformKey(k.id), 'Chave revogada.')}>
                      Revogar
                    </Btn>
                  </td>
                </tr>
              ))}
              {activeKeys.length === 0 && (
                <tr><td colSpan={5}>
                  <EmptyState label="Nenhuma chave"
                    sub="Crie chaves escopadas para integrações (Grafana, webhooks, bots) — as API_KEYS por env viram legado admin." />
                </td></tr>
              )}
            </tbody>
          </table>
        </div>
        {keyDraft && (
          <div className="card-pad" style={{ borderTop: '1px solid var(--border)', display: 'flex',
                                             gap: 10, flexWrap: 'wrap', alignItems: 'flex-end' }}>
            <label className="auth-field" style={{ margin: 0, minWidth: 180 }}>
              <span className="label-xs">Nome (identifica a integração)</span>
              <input className="auth-input" maxLength={60} value={keyDraft.label}
                placeholder="ex.: grafana-readonly"
                onChange={e => setKeyDraft(d => ({ ...d, label: e.target.value }))} />
            </label>
            <label className="auth-field" style={{ margin: 0, minWidth: 220 }}>
              <span className="label-xs">Escopo</span>
              <select className="auth-input" value={keyDraft.scope} aria-label="Escopo da chave"
                onChange={e => setKeyDraft(d => ({ ...d, scope: e.target.value }))}>
                {KEY_SCOPES_UI.map(s => <option key={s.id} value={s.id}>{s.label}</option>)}
              </select>
            </label>
            <span style={{ display: 'flex', gap: 8 }}>
              <Btn variant="primary" size="sm" disabled={!keyDraft.label}
                onClick={async () => {
                  if (mock) {
                    setKeyCreated({ label: keyDraft.label, key: 'ctk_demo1234exemplo-nao-e-uma-chave-real' });
                    setKeyDraft(null);
                    return;
                  }
                  try {
                    const created = await CT_API.createPlatformKey(keyDraft);
                    setKeyCreated(created);
                    setKeyDraft(null);
                    load();
                  } catch (e) { addToast?.(e?.message ?? 'Falha ao criar chave.', 'alert'); }
                }}>
                Criar
              </Btn>
              <Btn variant="ghost" size="sm" onClick={() => setKeyDraft(null)}>Cancelar</Btn>
            </span>
          </div>
        )}
      </div>

      {connecting && (
        <ConnectionModal addToast={addToast} onClose={() => setConnecting(false)} onSaved={load} />
      )}
      {rotating && (
        <RotateModal conn={rotating} addToast={addToast}
          onClose={() => setRotating(null)} onRotated={onRotated} />
      )}
      {keyCreated && <KeyCreatedModal created={keyCreated} onClose={() => setKeyCreated(null)} />}
    </div>
  );
}
window.ScreenConnections = ScreenConnections;
