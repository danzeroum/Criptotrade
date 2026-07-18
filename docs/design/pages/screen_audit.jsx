/* ============================================================
   A4 — Trilha de Auditoria (view_audit; operador+, nunca demo).
   Lista paginada do GET /v1/audit com filtros por ação, ator,
   alvo e período — todos aplicados no SQL do backend, então o
   total e as páginas são exatos sob qualquer filtro. Detalhe em
   modal com diff antes→depois; export CSV/JSON do conjunto
   filtrado COMPLETO (não só a página visível).
   ============================================================ */
const { useState: useAudState, useEffect: useAudEffect, useCallback: useAudCallback } = React;

const AUDIT_PAGE_SIZE = 50;

const AUDIT_ACTION_LABEL = {
  login:            'Login',
  logout:           'Logout',
  security:         'Segurança',
  user_management:  'Gestão de usuários',
  order_approved:   'Ordem aprovada',
  order_rejected:   'Ordem rejeitada',
  autonomy_changed: 'Autonomia alterada',
  config_changed:   'Config alterada',
  position_closed:  'Posição fechada',
  circuit_breaker:  'Circuit breaker',
  order_executed:   'Ordem executada',
  notification:     'Notificação',
  connection:       'Conexão de exchange',
  platform_key:     'Chave da plataforma',
  other:            'Outro',
};

const AUDIT_ACTION_BADGE = {
  login: 'info', logout: 'neutral', security: 'warn', user_management: 'violet',
  order_approved: 'ok', order_rejected: 'down', autonomy_changed: 'warn',
  config_changed: 'violet', position_closed: 'info', circuit_breaker: 'down',
  order_executed: 'neutral', notification: 'info', connection: 'warn',
  platform_key: 'violet', other: 'neutral',
};

// A2: timestamps go through the central locale/timezone-aware helper.
const fmtAudTs = (ts) => window.fmtDateTime(ts);

// Before→after diff, key by key (only the changed keys arrive from the API).
function AuditDiff({ before, after }) {
  const keys = [...new Set([...Object.keys(before ?? {}), ...Object.keys(after ?? {})])];
  if (!keys.length) return null;
  const cell = (v) => (v === undefined || v === null ? '—' : JSON.stringify(v));
  return (
    <div style={{ marginTop: 12 }}>
      <div className="label-xs" style={{ marginBottom: 6 }}>Alteração (antes → depois)</div>
      <table className="tbl" data-testid="audit-diff">
        <thead>
          <tr>
            <th style={{ textAlign: 'left' }}>Campo</th>
            <th style={{ textAlign: 'left' }}>Antes</th>
            <th style={{ textAlign: 'left' }}>Depois</th>
          </tr>
        </thead>
        <tbody>
          {keys.map(k => (
            <tr key={k}>
              <td style={{ fontFamily: 'var(--mono)', fontSize: 12 }}>{k}</td>
              <td style={{ fontFamily: 'var(--mono)', fontSize: 12, color: 'var(--down)' }}>
                {cell(before?.[k])}
              </td>
              <td style={{ fontFamily: 'var(--mono)', fontSize: 12, color: 'var(--up)' }}>
                {cell(after?.[k])}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function AuditDetailModal({ event, onClose }) {
  const rows = [
    ['Quando',  fmtAudTs(event.ts)],
    ['Ação',    AUDIT_ACTION_LABEL[event.action] ?? event.action],
    ['Ator',    event.actor],
    ['Alvo',    event.entity ?? '—'],
    ['IP',      event.ip ?? '—'],
    ['Navegador', event.ua ?? '—'],
    ['Resultado', event.success == null ? '—' : (event.success ? 'sucesso' : 'falha')],
    ['Detalhe', event.detail ?? '—'],
  ];
  return (
    <div className="lock-overlay" role="dialog" aria-label="Detalhe do evento" onClick={onClose}>
      <div className="auth-card" style={{ maxWidth: 560, maxHeight: '84vh', overflowY: 'auto' }}
        onClick={e => e.stopPropagation()}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
          <h2 style={{ fontSize: 15, fontWeight: 600 }}>
            Evento <span style={{ fontFamily: 'var(--mono)' }}>#{event.id}</span>
          </h2>
          <Btn variant="ghost" size="sm" onClick={onClose}><Icon name="x" size={14} /></Btn>
        </div>
        {rows.map(([label, value]) => (
          <div key={label} className="stat-row" style={{ padding: '7px 0' }}>
            <span className="stat-k">{label}</span>
            <span className="stat-v" style={{ fontSize: 12.5, textAlign: 'right', wordBreak: 'break-all' }}>
              {value}
            </span>
          </div>
        ))}
        <AuditDiff before={event.before} after={event.after} />
        {event.data && (
          <details style={{ marginTop: 12 }}>
            <summary style={{ fontSize: 12, color: 'var(--ink-3)', cursor: 'pointer' }}>
              Payload bruto ({event.event_type})
            </summary>
            <pre style={{
              fontSize: 11.5, fontFamily: 'var(--mono)', background: 'var(--bg)',
              border: '1px solid var(--border)', borderRadius: 'var(--r)',
              padding: 10, marginTop: 8, overflowX: 'auto',
            }}>{JSON.stringify(event.data, null, 2)}</pre>
          </details>
        )}
      </div>
    </div>
  );
}

function ScreenAudit({ addToast }) {
  const mock = !!window.USE_MOCK_DATA;
  const empty = { action: '', actor: '', entity: '', from: '', to: '' };
  const [draft,    setDraft]    = useAudState(empty);   // filter inputs
  const [filters,  setFilters]  = useAudState(empty);   // applied filters
  const [page,     setPage]     = useAudState(0);
  const [events,   setEvents]   = useAudState(null);
  const [total,    setTotal]    = useAudState(0);
  const [loading,  setLoading]  = useAudState(!mock);
  const [error,    setError]    = useAudState(null);
  const [selected, setSelected] = useAudState(null);

  const load = useAudCallback(() => {
    if (mock) {
      // e2e/mock: same filter semantics as the backend, applied client-side.
      const all = (CT.auditEvents ?? []).filter(e =>
        (!filters.action || e.action === filters.action) &&
        (!filters.actor || e.actor === filters.actor) &&
        (!filters.entity || (e.entity ?? '').toLowerCase().includes(filters.entity.toLowerCase())));
      setTotal(all.length);
      setEvents(all.slice(page * AUDIT_PAGE_SIZE, (page + 1) * AUDIT_PAGE_SIZE));
      return;
    }
    setLoading(true);
    setError(null);
    CT_API.getAudit({ ...filters, limit: AUDIT_PAGE_SIZE, offset: page * AUDIT_PAGE_SIZE })
      .then(env => {
        setEvents(env.data ?? []);
        setTotal(env.meta?.total ?? (env.data ?? []).length);
        setLoading(false);
      })
      .catch(e => { setError(e); setLoading(false); });
  }, [mock, filters, page]);

  useAudEffect(() => { load(); }, [load]);

  const apply = (e) => { e?.preventDefault(); setPage(0); setFilters({ ...draft }); };
  const clear = () => { setDraft(empty); setPage(0); setFilters(empty); };

  const openDetail = (ev) => {
    if (mock) { setSelected(ev); return; }
    CT_API.getAuditEvent(ev.id)
      .then(setSelected)
      .catch(() => setSelected(ev));  // fallback: show the row we already have
  };

  const doExport = async (format) => {
    if (mock) { addToast?.('Modo demo: export não disponível.', 'info'); return; }
    try {
      const blob = await CT_API.exportAudit(format, filters);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `auditoria.${format}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      addToast?.(e?.message ?? 'Falha ao exportar.', 'alert');
    }
  };

  const pages = Math.max(1, Math.ceil(total / AUDIT_PAGE_SIZE));

  let body;
  if (loading) {
    body = <LoadingState label="Carregando trilha…" />;
  } else if (error) {
    body = <ErrorState message="Erro ao carregar a trilha de auditoria" onRetry={load} />;
  } else {
    body = (
      <div className="card">
        <div className="card-head">
          <span className="card-title"><Icon name="clock" />Eventos</span>
          <Badge variant="neutral" dot={false}>{total} evento(s)</Badge>
        </div>
        <div style={{ overflowX: 'auto' }}>
          <table className="tbl">
            <thead>
              <tr>
                <th style={{ textAlign: 'left' }}>Quando</th>
                <th style={{ textAlign: 'left' }}>Ação</th>
                <th style={{ textAlign: 'left' }}>Ator</th>
                <th style={{ textAlign: 'left' }}>Alvo</th>
                <th style={{ textAlign: 'left' }}>IP</th>
                <th style={{ textAlign: 'left' }}>Detalhe</th>
              </tr>
            </thead>
            <tbody>
              {(events ?? []).map(e => (
                <tr key={e.id} onClick={() => openDetail(e)} style={{ cursor: 'pointer' }}>
                  <td style={{ fontFamily: 'var(--mono)', fontSize: 12, whiteSpace: 'nowrap' }}>
                    {fmtAudTs(e.ts)}
                  </td>
                  <td>
                    <Badge variant={AUDIT_ACTION_BADGE[e.action] ?? 'neutral'} dot={false}>
                      {AUDIT_ACTION_LABEL[e.action] ?? e.action}
                    </Badge>
                  </td>
                  <td style={{ fontFamily: 'var(--mono)', fontSize: 12 }}>{e.actor}</td>
                  <td style={{ fontFamily: 'var(--mono)', fontSize: 12 }}>{e.entity ?? '—'}</td>
                  <td style={{ fontFamily: 'var(--mono)', fontSize: 12 }}>{e.ip ?? '—'}</td>
                  <td style={{
                    fontSize: 12, color: 'var(--ink-2)', maxWidth: 260,
                    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                  }}>{e.detail ?? '—'}</td>
                </tr>
              ))}
              {(events ?? []).length === 0 && (
                <tr><td colSpan={6}>
                  <EmptyState label="Nenhum evento"
                    sub="Nada corresponde aos filtros — ou o ledger ainda está vazio." />
                </td></tr>
              )}
            </tbody>
          </table>
        </div>
        <div style={{
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          padding: '10px 16px', borderTop: '1px solid var(--border)',
        }}>
          <span style={{ fontSize: 12, color: 'var(--ink-3)' }}>
            página {page + 1} de {pages}
          </span>
          <span style={{ display: 'flex', gap: 8 }}>
            <Btn variant="ghost" size="sm" disabled={page === 0}
              onClick={() => setPage(p => Math.max(0, p - 1))}>Anterior</Btn>
            <Btn variant="ghost" size="sm" disabled={page + 1 >= pages}
              onClick={() => setPage(p => p + 1)}>Próxima</Btn>
          </span>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="page-head">
        <div>
          <h1 className="page-title">Trilha de Auditoria</h1>
          <div className="page-sub">Quem fez o quê, quando — direto do ledger imutável</div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <Btn variant="ghost" size="sm" onClick={() => doExport('csv')}
            data-tip="Exporta o conjunto filtrado completo">
            <Icon name="bar" size={13} /> CSV
          </Btn>
          <Btn variant="ghost" size="sm" onClick={() => doExport('json')}
            data-tip="Exporta o conjunto filtrado completo">
            <Icon name="list" size={13} /> JSON
          </Btn>
          <Btn variant="ghost" size="sm" onClick={load}><Icon name="refresh" size={13} /></Btn>
        </div>
      </div>

      <form className="card" style={{ marginBottom: 16 }} onSubmit={apply}>
        <div className="card-pad" style={{ display: 'flex', flexWrap: 'wrap', gap: 10, alignItems: 'flex-end' }}>
          <label className="auth-field" style={{ margin: 0, minWidth: 170 }}>
            <span className="label-xs">Ação</span>
            <select className="auth-input" value={draft.action} aria-label="Ação"
              onChange={e => setDraft(d => ({ ...d, action: e.target.value }))}>
              <option value="">Todas</option>
              {Object.entries(AUDIT_ACTION_LABEL).filter(([id]) => id !== 'other').map(([id, label]) => (
                <option key={id} value={id}>{label}</option>
              ))}
            </select>
          </label>
          <label className="auth-field" style={{ margin: 0, minWidth: 170 }}>
            <span className="label-xs">Ator</span>
            <input className="auth-input" placeholder="email, api-key, orchestrator…"
              value={draft.actor} onChange={e => setDraft(d => ({ ...d, actor: e.target.value }))} />
          </label>
          <label className="auth-field" style={{ margin: 0, minWidth: 150 }}>
            <span className="label-xs">Alvo</span>
            <input className="auth-input" placeholder="par, escopo, e-mail…"
              value={draft.entity} onChange={e => setDraft(d => ({ ...d, entity: e.target.value }))} />
          </label>
          <label className="auth-field" style={{ margin: 0 }}>
            <span className="label-xs">De</span>
            <input className="auth-input" type="date" value={draft.from}
              onChange={e => setDraft(d => ({ ...d, from: e.target.value }))} />
          </label>
          <label className="auth-field" style={{ margin: 0 }}>
            <span className="label-xs">Até</span>
            <input className="auth-input" type="date" value={draft.to}
              onChange={e => setDraft(d => ({ ...d, to: e.target.value }))} />
          </label>
          <div style={{ display: 'flex', gap: 8 }}>
            <Btn variant="primary" size="sm">Filtrar</Btn>
            <Btn variant="ghost" size="sm" type="button" onClick={clear}>Limpar</Btn>
          </div>
        </div>
      </form>

      {body}

      {selected && <AuditDetailModal event={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}
window.ScreenAudit = ScreenAudit;
