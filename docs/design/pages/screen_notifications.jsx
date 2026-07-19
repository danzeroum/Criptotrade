/* ============================================================
   A6 — Notificações & Canais (edit_settings/admin; oculta no
   demo — contém secrets de canal). Canais e-mail/Telegram/Slack/
   webhook com teste de envio REAL (o botão mostra o destino
   mascarado), regras evento × severidade → canais, quiet hours
   (só a entrega externa é silenciada — nada some do console) e
   agrupamento anti-flood.
   ============================================================ */
const { useState: useNotState, useEffect: useNotEffect, useCallback: useNotCallback } = React;

const CHANNEL_META = {
  email:    { label: 'E-mail',   icon: 'bell',  fields: [
    { key: 'to_email', label: 'Destinatário', type: 'email', placeholder: 'voce@dominio.com' }] },
  telegram: { label: 'Telegram', icon: 'zap',   fields: [
    { key: 'bot_token', label: 'Bot token', secret: true, placeholder: '123456:ABC…' },
    { key: 'chat_id', label: 'Chat ID', placeholder: '-100200300' }] },
  slack:    { label: 'Slack',    icon: 'info',  fields: [
    { key: 'webhook_url', label: 'Webhook URL', secret: true, placeholder: 'https://hooks.slack.com/…' }] },
  webhook:  { label: 'Webhook',  icon: 'zap',   fields: [
    { key: 'url', label: 'URL', secret: true, placeholder: 'https://…' },
    { key: 'secret', label: 'Secret HMAC (opcional)', secret: true, optional: true }] },
};

const SEVERITIES_UI = [
  { id: 'low', label: 'Low+' }, { id: 'medium', label: 'Medium+' },
  { id: 'high', label: 'High+' }, { id: 'critical', label: 'Critical' },
];

const ALERT_TYPES_UI = [
  { id: '*', label: 'Qualquer evento' },
  { id: 'circuit_breaker', label: 'Circuit breaker' },
  { id: 'guardrail_violation', label: 'Violação de guardrail' },
  { id: 'behavioral', label: 'Alerta comportamental' },
];

function ChannelModal({ existing, onClose, onSaved, addToast }) {
  const mock = !!window.USE_MOCK_DATA;
  const [kind, setKind] = useNotState(existing?.kind ?? 'telegram');
  const [label, setLabel] = useNotState(existing?.label ?? '');
  const [config, setConfig] = useNotState(existing?.config_masked ?? {});
  const [busy, setBusy] = useNotState(false);
  const [error, setError] = useNotState(null);
  const meta = CHANNEL_META[kind];

  const submit = async (e) => {
    e.preventDefault();
    if (mock) { addToast?.('Modo demo: ação não aplicada.', 'info'); onClose?.(); return; }
    setBusy(true); setError(null);
    try {
      if (existing) await CT_API.patchChannel(existing.id, { label, config });
      else await CT_API.createChannel({ kind, label, config });
      onSaved?.();
      onClose?.();
    } catch (err) { setError(err?.message ?? 'Não foi possível salvar o canal.'); setBusy(false); }
  };

  return (
    <div className="lock-overlay" role="dialog" aria-label="Canal de notificação" onClick={onClose}>
      <div className="auth-card" style={{ maxWidth: 420 }} onClick={e => e.stopPropagation()}>
        <h2 style={{ fontSize: 15, fontWeight: 600, marginBottom: 12 }}>
          {existing ? `Editar canal — ${existing.label}` : 'Conectar canal'}
        </h2>
        <form onSubmit={submit}>
          {error && <div className="auth-error" role="alert">{error}</div>}
          {!existing && (
            <label className="auth-field">
              <span className="label-xs">Tipo</span>
              <select className="auth-input" value={kind}
                onChange={e => { setKind(e.target.value); setConfig({}); }}>
                {Object.entries(CHANNEL_META).map(([id, m]) =>
                  <option key={id} value={id}>{m.label}</option>)}
              </select>
            </label>
          )}
          <label className="auth-field">
            <span className="label-xs">Nome</span>
            <input className="auth-input" required maxLength={60} value={label}
              placeholder="ex.: Ops crítico" onChange={e => setLabel(e.target.value)} />
          </label>
          {meta.fields.map(f => (
            <label key={f.key} className="auth-field">
              <span className="label-xs">{f.label}{f.secret ? ' 🔒' : ''}</span>
              <input className="auth-input" type={f.type ?? 'text'}
                required={!f.optional} placeholder={f.placeholder ?? ''}
                value={config[f.key] ?? ''}
                onChange={e => setConfig(c => ({ ...c, [f.key]: e.target.value }))} />
            </label>
          ))}
          {existing && (
            <p style={{ fontSize: 11.5, color: 'var(--ink-3)', margin: '0 0 10px' }}>
              Campos 🔒 aparecem mascarados — deixe como está para manter o valor salvo.
            </p>
          )}
          <div style={{ display: 'flex', gap: 8 }}>
            <Btn variant="primary" size="sm" disabled={busy}>{busy ? '…' : 'Salvar'}</Btn>
            <Btn variant="ghost" size="sm" type="button" onClick={onClose}>Cancelar</Btn>
          </div>
        </form>
      </div>
    </div>
  );
}

function ScreenNotifications({ addToast }) {
  const mock = !!window.USE_MOCK_DATA;
  const [channels, setChannels] = useNotState(mock ? (CT.notificationChannels ?? []) : null);
  const [rules, setRules] = useNotState(mock ? (CT.notificationRules ?? []) : null);
  const [settings, setSettings] = useNotState(mock
    ? { quiet_start: '22:00', quiet_end: '07:00', quiet_tz: 'America/Sao_Paulo', group_window_min: 5 }
    : null);
  const [loading, setLoading] = useNotState(!mock);
  const [error, setError] = useNotState(null);
  const [editing, setEditing] = useNotState(null);   // null | 'new' | channel
  const [testing, setTesting] = useNotState(null);   // channel id being tested
  const [ruleDraft, setRuleDraft] = useNotState(null);
  // N7: pair options for the rule scope (from /v1/pairs — never hardcoded).
  const [pairOptions, setPairOptions] = useNotState([]);
  useNotEffect(() => {
    loadPairsRich().then(r => setPairOptions([...new Set([
      ...((r && r.operados) || []).map(o => o.symbol),
      ...((r && r.observaveis) || []),
    ])])).catch(() => {});
  }, []);

  const load = useNotCallback(() => {
    if (mock) return;
    setLoading(true);
    Promise.all([CT_API.getChannels(), CT_API.getNotifRules(), CT_API.getNotifSettings()])
      .then(([c, r, s]) => {
        setChannels(c ?? []); setRules(r ?? []); setSettings(s);
        setLoading(false); setError(null);
      })
      .catch(e => { setError(e); setLoading(false); });
  }, [mock]);

  useNotEffect(() => { load(); }, [load]);

  const act = async (fn, okMsg) => {
    if (mock) { addToast?.('Modo demo: ação não aplicada.', 'info'); return; }
    try { await fn(); if (okMsg) addToast?.(okMsg, 'check'); load(); }
    catch (e) { addToast?.(e?.message ?? 'Falha na ação.', 'alert'); }
  };

  const runTest = async (ch) => {
    if (mock) { addToast?.(`Teste enviado para ${ch.destination_masked} (demo).`, 'check'); return; }
    setTesting(ch.id);
    try {
      const r = await CT_API.testChannel(ch.id);
      addToast?.(r.ok
        ? `✅ Teste entregue em ${r.destination}.`
        : `Falha no teste: ${r.error}`, r.ok ? 'check' : 'alert');
      load();
    } catch (e) { addToast?.(e?.message ?? 'Falha no teste.', 'alert'); }
    finally { setTesting(null); }
  };

  if (loading) return <LoadingState label="Carregando notificações…" />;
  if (error) return <ErrorState message="Erro ao carregar notificações" onRetry={load} />;

  const channelName = (id) => (channels ?? []).find(c => c.id === id)?.label ?? '?';

  return (
    <div>
      <div className="page-head">
        <div>
          <h1 className="page-title">Notificações & Canais</h1>
          <div className="page-sub">Para onde os alertas vão — e-mail, Telegram, Slack, webhook</div>
        </div>
        <Btn variant="primary" size="sm" onClick={() => setEditing('new')}>
          <Icon name="plus" size={13} /> Conectar canal
        </Btn>
      </div>

      {/* --------------------------------------------------------- channels */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-head">
          <span className="card-title"><Icon name="bell" />Canais</span>
          <Badge variant="neutral" dot={false}>{(channels ?? []).length} canal(is)</Badge>
        </div>
        <div style={{ overflowX: 'auto' }}>
          <table className="tbl">
            <thead>
              <tr>
                <th style={{ textAlign: 'left' }}>Canal</th>
                <th style={{ textAlign: 'left' }}>Destino</th>
                <th style={{ textAlign: 'left' }}>Último teste</th>
                <th style={{ textAlign: 'right' }}>Ações</th>
              </tr>
            </thead>
            <tbody>
              {(channels ?? []).map(ch => (
                <tr key={ch.id}>
                  <td>
                    <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <Icon name={CHANNEL_META[ch.kind]?.icon ?? 'bell'} size={14} />
                      <span style={{ fontWeight: 500 }}>{ch.label}</span>
                      <Badge variant="neutral" dot={false}>{CHANNEL_META[ch.kind]?.label ?? ch.kind}</Badge>
                      {!ch.enabled && <Badge variant="warn" dot={false}>pausado</Badge>}
                    </span>
                  </td>
                  <td style={{ fontFamily: 'var(--mono)', fontSize: 12 }}>{ch.destination_masked}</td>
                  <td>
                    {ch.last_test_at == null
                      ? <span style={{ color: 'var(--ink-3)', fontSize: 12 }}>nunca testado</span>
                      : <Badge variant={ch.last_test_ok ? 'ok' : 'down'} dot={false}>
                          {ch.last_test_ok ? 'ok' : 'falhou'} · {fmtDateTime(ch.last_test_at)}
                        </Badge>}
                    {ch.last_test_ok === false && ch.last_error && (
                      <div style={{ fontSize: 11, color: 'var(--down)', marginTop: 2 }}>{ch.last_error}</div>
                    )}
                  </td>
                  <td style={{ textAlign: 'right', whiteSpace: 'nowrap' }}>
                    {/* Nota UX 2: o destino mascarado dá sentido ao resultado. */}
                    <Btn variant="ghost" size="sm" disabled={testing === ch.id}
                      data-tip={`Enviar teste para ${ch.destination_masked}`}
                      onClick={() => runTest(ch)}>
                      {testing === ch.id ? 'Enviando…' : 'Testar'}
                    </Btn>
                    <Btn variant="ghost" size="sm" onClick={() => setEditing(ch)}>Editar</Btn>
                    <Btn variant="ghost" size="sm"
                      onClick={() => act(() => CT_API.deleteChannel(ch.id), 'Canal removido.')}>
                      Remover
                    </Btn>
                  </td>
                </tr>
              ))}
              {(channels ?? []).length === 0 && (
                <tr><td colSpan={4}>
                  <EmptyState label="Nenhum canal conectado"
                    sub="Conecte e-mail, Telegram, Slack ou webhook para receber alertas fora do console." />
                </td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* ------------------------------------------------------------ rules */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-head">
          <span className="card-title"><Icon name="shield" />Regras de entrega</span>
          <Btn variant="ghost" size="sm" onClick={() =>
            setRuleDraft({ alert_type: '*', min_severity: 'high', channel_ids: [], pairs: ['*'] })}>
            <Icon name="plus" size={13} /> Nova regra
          </Btn>
        </div>
        <div className="card-pad" style={{ padding: '6px 16px 12px' }}>
          {(rules ?? []).map(r => (
            <div key={r.id} className="stat-row" style={{ padding: '9px 0', gap: 10, flexWrap: 'wrap' }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                <Badge variant="neutral" dot={false}>
                  {ALERT_TYPES_UI.find(t => t.id === r.alert_type)?.label ?? r.alert_type}
                </Badge>
                <Badge variant={{ low: 'neutral', medium: 'info', high: 'warn', critical: 'down' }[r.min_severity]} dot={false}>
                  ≥ {r.min_severity}
                </Badge>
                <span style={{ fontSize: 12.5, color: 'var(--ink-2)' }}>
                  → {r.channel_ids.map(channelName).join(', ') || 'nenhum canal'}
                </span>
                {r.pairs && !r.pairs.includes('*') && (
                  <Badge variant="info" dot={false}>só {r.pairs.join(', ')}</Badge>
                )}
                {!r.enabled && <Badge variant="warn" dot={false}>pausada</Badge>}
              </span>
              <span>
                <Btn variant="ghost" size="sm"
                  onClick={() => act(() => CT_API.patchNotifRule(r.id, { enabled: !r.enabled }),
                    r.enabled ? 'Regra pausada.' : 'Regra reativada.')}>
                  {r.enabled ? 'Pausar' : 'Ativar'}
                </Btn>
                <Btn variant="ghost" size="sm"
                  onClick={() => act(() => CT_API.deleteNotifRule(r.id), 'Regra removida.')}>
                  Remover
                </Btn>
              </span>
            </div>
          ))}
          {(rules ?? []).length === 0 && (
            <EmptyState label="Nenhuma regra"
              sub="Sem regras, nada é entregue — ex.: circuit breaker (critical) → Telegram + e-mail." />
          )}
          {ruleDraft && (
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'flex-end',
                          borderTop: '1px solid var(--border)', paddingTop: 12, marginTop: 6 }}>
              <label className="auth-field" style={{ margin: 0, minWidth: 170 }}>
                <span className="label-xs">Evento</span>
                <select className="auth-input" value={ruleDraft.alert_type} aria-label="Evento"
                  onChange={e => setRuleDraft(d => ({ ...d, alert_type: e.target.value }))}>
                  {ALERT_TYPES_UI.map(t => <option key={t.id} value={t.id}>{t.label}</option>)}
                </select>
              </label>
              <label className="auth-field" style={{ margin: 0, minWidth: 130 }}>
                <span className="label-xs">Severidade mínima</span>
                <select className="auth-input" value={ruleDraft.min_severity} aria-label="Severidade mínima"
                  onChange={e => setRuleDraft(d => ({ ...d, min_severity: e.target.value }))}>
                  {SEVERITIES_UI.map(s => <option key={s.id} value={s.id}>{s.label}</option>)}
                </select>
              </label>
              <div className="auth-field" style={{ margin: 0 }}>
                <span className="label-xs">Canais</span>
                <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', paddingTop: 6 }}>
                  {(channels ?? []).map(c => (
                    <label key={c.id} style={{ display: 'flex', gap: 5, alignItems: 'center', fontSize: 12.5 }}>
                      <input type="checkbox"
                        checked={ruleDraft.channel_ids.includes(c.id)}
                        onChange={e => setRuleDraft(d => ({
                          ...d,
                          channel_ids: e.target.checked
                            ? [...d.channel_ids, c.id]
                            : d.channel_ids.filter(x => x !== c.id),
                        }))} />
                      {c.label}
                    </label>
                  ))}
                </div>
              </div>
              <div className="auth-field" style={{ margin: 0 }}>
                <span className="label-xs">Pares</span>
                <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', paddingTop: 6, alignItems: 'center' }}>
                  <label style={{ display: 'flex', gap: 5, alignItems: 'center', fontSize: 12.5 }}>
                    <input type="checkbox" checked={ruleDraft.pairs.includes('*')}
                      onChange={e => setRuleDraft(d => ({ ...d, pairs: e.target.checked ? ['*'] : [] }))} />
                    Todos
                  </label>
                  {!ruleDraft.pairs.includes('*') && pairOptions.map(p => (
                    <label key={p} style={{ display: 'flex', gap: 5, alignItems: 'center', fontSize: 12.5 }}>
                      <input type="checkbox" checked={ruleDraft.pairs.includes(p)}
                        onChange={e => setRuleDraft(d => ({
                          ...d,
                          pairs: e.target.checked ? [...d.pairs, p] : d.pairs.filter(x => x !== p),
                        }))} />
                      {p}
                    </label>
                  ))}
                </div>
              </div>
              <span style={{ display: 'flex', gap: 8 }}>
                <Btn variant="primary" size="sm"
                  onClick={() => act(() => CT_API.createNotifRule(ruleDraft), 'Regra criada.')
                    .then(() => setRuleDraft(null))}>
                  Criar
                </Btn>
                <Btn variant="ghost" size="sm" onClick={() => setRuleDraft(null)}>Cancelar</Btn>
              </span>
            </div>
          )}
        </div>
      </div>

      {/* ---------------------------------------------- quiet hours / flood */}
      <div className="card">
        <div className="card-head">
          <span className="card-title"><Icon name="clock" />Silêncio & agrupamento</span>
        </div>
        <div className="card-pad">
          {/* Nota UX 1: deixar claro que NADA some do console. */}
          <p style={{ fontSize: 12.5, color: 'var(--ink-2)', lineHeight: 1.6, margin: '0 0 12px' }}>
            Durante o silêncio, alertas <b>low/medium não são enviados aos canais</b>;
            high/critical passam sempre. <b>Nada some do console</b> — o drawer de
            alertas continua mostrando tudo; só a entrega externa é silenciada.
            O agrupamento suprime repetições do mesmo alerta dentro da janela e
            anexa “(+N suprimidos)” na próxima entrega.
          </p>
          <NotifSettingsForm settings={settings} mock={mock} addToast={addToast}
            onSaved={(s) => setSettings(s)} />
        </div>
      </div>

      {editing && (
        <ChannelModal existing={editing === 'new' ? null : editing}
          addToast={addToast} onClose={() => setEditing(null)} onSaved={load} />
      )}
    </div>
  );
}

function NotifSettingsForm({ settings, mock, addToast, onSaved }) {
  const [draft, setDraft] = useNotState({
    quiet_start: settings?.quiet_start ?? '',
    quiet_end: settings?.quiet_end ?? '',
    quiet_tz: settings?.quiet_tz ?? (CT_PREFS.timezone() ?? 'America/Sao_Paulo'),
    group_window_min: settings?.group_window_min ?? 5,
  });
  const [busy, setBusy] = useNotState(false);

  const save = async (e) => {
    e.preventDefault();
    if (mock) { addToast?.('Modo demo: ação não aplicada.', 'info'); return; }
    setBusy(true);
    try {
      const body = draft.quiet_start && draft.quiet_end
        ? { quiet_start: draft.quiet_start, quiet_end: draft.quiet_end,
            quiet_tz: draft.quiet_tz, group_window_min: +draft.group_window_min }
        : { clear_quiet_hours: true, quiet_tz: draft.quiet_tz,
            group_window_min: +draft.group_window_min };
      const out = await CT_API.patchNotifSettings(body);
      onSaved?.(out);
      addToast?.('Configuração de entrega salva.', 'check');
    } catch (err) { addToast?.(err?.message ?? 'Falha ao salvar.', 'alert'); }
    finally { setBusy(false); }
  };

  return (
    <form onSubmit={save} style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'flex-end' }}>
      <label className="auth-field" style={{ margin: 0 }}>
        <span className="label-xs">Silêncio — início</span>
        <input className="auth-input" type="time" value={draft.quiet_start}
          onChange={e => setDraft(d => ({ ...d, quiet_start: e.target.value }))} />
      </label>
      <label className="auth-field" style={{ margin: 0 }}>
        <span className="label-xs">Silêncio — fim</span>
        <input className="auth-input" type="time" value={draft.quiet_end}
          onChange={e => setDraft(d => ({ ...d, quiet_end: e.target.value }))} />
      </label>
      <label className="auth-field" style={{ margin: 0, minWidth: 200 }}>
        <span className="label-xs">Fuso do silêncio (pré-preenchido do seu perfil)</span>
        <input className="auth-input" list="ct-notif-tz-list" value={draft.quiet_tz}
          onChange={e => setDraft(d => ({ ...d, quiet_tz: e.target.value }))} />
        <datalist id="ct-notif-tz-list">
          {(() => {
            try {
              const common = ['America/Sao_Paulo', 'UTC', 'America/New_York', 'Europe/Lisbon', 'Europe/London'];
              const all = Intl.supportedValuesOf('timeZone');
              return [...common, ...all.filter(t => !common.includes(t))];
            } catch (_) { return ['America/Sao_Paulo', 'UTC']; }
          })().map(tz => <option key={tz} value={tz} />)}
        </datalist>
      </label>
      <label className="auth-field" style={{ margin: 0, width: 130 }}>
        <span className="label-xs">Janela anti-flood (min)</span>
        <input className="auth-input" type="number" min={1} max={120}
          value={draft.group_window_min}
          onChange={e => setDraft(d => ({ ...d, group_window_min: e.target.value }))} />
      </label>
      <Btn variant="primary" size="sm" disabled={busy}>{busy ? '…' : 'Salvar'}</Btn>
    </form>
  );
}
window.ScreenNotifications = ScreenNotifications;
