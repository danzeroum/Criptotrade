/* ============================================================
   Criptotrade — Screen: HITL Controls
   ============================================================ */
const { useState, useEffect, useCallback } = React;

function ConfidenceBreakdown({ breakdown }) {
  if (!breakdown || !breakdown.length) return null;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 7, marginTop: 10 }}>
      <div className="label-xs" style={{ marginBottom: 2 }}>Fatores de confiança</div>
      {breakdown.map(f => (
        <div key={f.key}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
            <span style={{ fontSize: 11.5, color: 'var(--ink-3)' }}>{f.key}</span>
            <span style={{ fontSize: 11.5, fontFamily: 'var(--mono)', color: 'var(--ink-2)' }}>
              {Math.round((f.score ?? f.value ?? 0) * 100)}%
            </span>
          </div>
          <Meter value={(f.score ?? f.value ?? 0) * 100} max={100} warn={60} crit={80} />
        </div>
      ))}
    </div>
  );
}

function PendingOrderCard({ order, onDecide, highlight = false, ctx = null }) {
  // A3 gating: authenticated Visualizador sees NO action controls (spec
  // acceptance); the public demo shows them DISABLED with a discovery tooltip
  // (approved demo-mode correction). 'off'/operador/admin get the live UI.
  const canApprove = CT_AUTH.can('approve_order');
  const demoView = !canApprove && CT_AUTH.kind() === 'demo';
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  // Two-step confirmation on financial actions (mirrors the paper-order confirm
  // on the Market screen). `confirming` holds the pending action, or null.
  const [confirming, setConfirming] = useState(null);

  const decide = async (action) => {
    setBusy(true);
    await onDecide(order.id, action, note);
    setConfirming(null);
    setBusy(false);
  };

  return (
    <div className="card" style={{
      marginBottom: 12,
      ...(highlight ? { outline: '2px solid var(--warn)', outlineOffset: -1 } : {}),
    }}>
      <div className="card-head">
        <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
          <Badge variant={order.side === 'buy' ? 'ok' : 'down'}>
            {order.side === 'buy' ? 'COMPRA' : 'VENDA'}
          </Badge>
          <span style={{ fontFamily: 'var(--mono)', fontWeight: 600, fontSize: 14 }}>{order.pair}</span>
          <span style={{ fontSize: 12.5, color: 'var(--ink-3)' }}>{order.strategy}</span>
          {order.critical && <Badge variant="down">CRÍTICO</Badge>}
          {highlight && <Badge variant="warn">vindo do Mercado</Badge>}
        </div>
        <Badge variant="neutral" dot={false}>
          {Math.round((order.confidence ?? 0) * 100)}% confiança
        </Badge>
      </div>
      {/* N4: mini-contexto do par (preço atual vs entrada + regime), do desk/summary
          — buscado 1× na tela e distribuído, nunca por ordem. */}
      {ctx && ctx.last != null && (
        <div className="hitl-ctx">
          <span>Agora <b>{fmtUsd(ctx.last)}</b></span>
          {order.price ? (
            <span className={(ctx.last - order.price) >= 0 ? 'up' : 'down'}>
              {(ctx.last - order.price) >= 0 ? '+' : ''}
              {fmtNum((ctx.last - order.price) / order.price * 100, 2)}% vs entrada
            </span>
          ) : null}
          {ctx.regime_label && <span className="badge badge-neutral">{ctx.regime_label}</span>}
        </div>
      )}
      <div className="card-pad">
        <div className="grid" style={{ gridTemplateColumns: 'repeat(5, 1fr)', marginBottom: 12, gap: 0 }}>
          {[
            { label: 'Quantidade', value: String(order.quantity) },
            { label: 'Preço', value: fmtUsd(order.price ?? 0) },
            { label: 'Nocional', value: fmtUsd(order.notional ?? 0) },
            { label: 'Stop Loss', value: order.stop_loss ? fmtUsd(order.stop_loss) : '—', color: 'var(--down)' },
            { label: 'R/R', value: order.rr ? `${order.rr}×` : '—', color: order.rr >= 2.5 ? 'var(--up)' : 'var(--warn)' },
          ].map(cell => (
            <div key={cell.label}>
              <div style={{ fontSize: 10.5, color: 'var(--ink-3)', marginBottom: 3 }}>{cell.label}</div>
              <div style={{ fontFamily: 'var(--mono)', fontWeight: 500, fontSize: 13, color: cell.color }}>{cell.value}</div>
            </div>
          ))}
        </div>

        {order.reason && (
          <p style={{ fontSize: 12.5, color: 'var(--ink-2)', marginBottom: 12, lineHeight: 1.6 }}>
            {order.reason}
          </p>
        )}

        <ConfidenceBreakdown breakdown={order.confidence_breakdown} />

        {!canApprove && !demoView && (
          <div style={{ marginTop: 14, display: 'flex', alignItems: 'center', gap: 7,
            fontSize: 12, color: 'var(--ink-3)' }}>
            <Icon name="lock" size={12} /> Somente leitura — seu perfil não aprova ordens.
          </div>
        )}
        {demoView && (
          <div style={{ marginTop: 14, display: 'flex', gap: 8, alignItems: 'center' }}>
            <Btn variant="down" size="sm" disabled
              data-tip="Somente leitura no ambiente de demonstração — no produto real, este botão rejeita a ordem">
              <Icon name="x" size={13} /> Rejeitar
            </Btn>
            <Btn variant="up" size="sm" disabled
              data-tip="Somente leitura no ambiente de demonstração — no produto real, este botão aprova a ordem">
              <Icon name="check" size={13} /> Aprovar
            </Btn>
          </div>
        )}
        {canApprove && (
        <div style={{ marginTop: 14, display: 'flex', gap: 8, alignItems: 'center' }}>
          <input
            className="input"
            placeholder="Nota (opcional)"
            value={note}
            onChange={e => setNote(e.target.value)}
            style={{ flex: 1, padding: '7px 10px', fontSize: 12.5 }}
          />
          {confirming ? (
            <>
              <span style={{ fontSize: 12, color: 'var(--ink-2)', marginRight: 4 }}>
                Confirmar {confirming === 'approved' ? 'aprovação' : 'rejeição'}?
              </span>
              <Btn variant="ghost" size="sm" onClick={() => setConfirming(null)} disabled={busy}>
                Cancelar
              </Btn>
              <Btn
                variant={confirming === 'approved' ? 'up' : 'down'}
                size="sm"
                onClick={() => decide(confirming)}
                disabled={busy}
              >
                <Icon name={confirming === 'approved' ? 'check' : 'x'} size={13} /> Confirmar
              </Btn>
            </>
          ) : (
            <>
              <Btn variant="down" size="sm" onClick={() => setConfirming('rejected')} disabled={busy}>
                <Icon name="x" size={13} /> Rejeitar
              </Btn>
              <Btn variant="up" size="sm" onClick={() => setConfirming('approved')} disabled={busy}>
                <Icon name="check" size={13} /> Aprovar
              </Btn>
            </>
          )}
        </div>
        )}
      </div>
    </div>
  );
}

function ScreenHITL({ addToast }) {
  const [config, setConfig] = useState(null);
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  // M2: pair handed over by Mercado's "Ver no HITL" — highlight its orders once.
  const [focusPair] = useState(() => {
    try {
      const p = sessionStorage.getItem('ct.hitl.focus');
      if (p) sessionStorage.removeItem('ct.hitl.focus');
      return p || null;
    } catch (_) { return null; }
  });
  // N4: arriving from Mercado's "Ver no HITL" pre-filters the queue to that pair.
  const [pairFilter, setPairFilter] = useState(focusPair);
  // N4: per-pair context (preço atual + regime) from the desk snapshot — fetched
  // ONCE here and distributed to the cards, never one request per order.
  const [deskCtx, setDeskCtx] = useState(() => ({}));
  useEffect(() => {
    CT_API.getDeskSummary().then(d => {
      const map = {};
      (d.rows || []).forEach(r => { map[r.symbol] = { last: r.last, regime_label: r.regime_label }; });
      setDeskCtx(map);
    }).catch(() => {});
  }, []);

  const load = useCallback(() => {
    setLoading(true);
    Promise.all([
      CT_API.getHITL(),
      CT_API.getOrders(200, 0, '&status=pending'),
    ])
      .then(([cfg, ords]) => {
        setConfig(cfg);
        setOrders(Array.isArray(ords) ? ords : []);
        setLoading(false);
      })
      .catch(e => { setError(e); setLoading(false); });
  }, []);

  useEffect(() => { load(); }, [load]);

  const decide = async (orderId, action, note) => {
    try {
      // A3: no client-sent operator — the server stamps the session identity.
      await CT_API.decideOrder(orderId, {
        action,
        operator_note: note || undefined,
      });
      load();
      addToast?.(action === 'approved' ? 'Ordem aprovada' : 'Ordem rejeitada', 'check');
    } catch (e) {
      console.error('decide error', e);
      addToast?.('Erro ao processar a ordem', 'alert');
    }
  };

  const setLevel = async (level) => {
    try {
      // A3: no client-sent operator — the server stamps the session identity.
      const updated = await CT_API.patchHITL({
        level,
        reason: 'Alterado via console',
      });
      setConfig(updated);
      addToast?.('Nível de autonomia atualizado', 'check');
    } catch (e) {
      console.error('setLevel error', e);
      addToast?.('Erro ao alterar o nível de autonomia', 'alert');
    }
  };

  if (loading) return <LoadingState label="Carregando HITL…" />;
  if (error) return (
    <ErrorState
      message="Erro ao carregar configurações HITL"
      onRetry={() => { setError(null); load(); }}
    />
  );

  const pending = orders.filter(o => !o.status || o.status === 'pending');

  return (
    <div>
      <div className="page-head">
        <div>
          <h1 className="page-title">HITL Controls</h1>
          <div className="page-sub">Human-in-the-Loop · aprovação de ordens e nível de autonomia</div>
        </div>
        <Btn variant="ghost" size="sm" onClick={load}>
          <Icon name="refresh" size={13} /> Atualizar
        </Btn>
      </div>

      <div className="grid kpi-row" style={{ marginBottom: 20 }}>
        <div className="card">
          <KPI label="Pendentes" value={pending.length} format="int" icon="clock" />
        </div>
        <div className="card">
          <KPI label="Aprovadas hoje" value={config?.human_approved_today ?? 0} format="int" icon="check" />
        </div>
        <div className="card">
          <KPI label="Rejeitadas hoje" value={config?.human_rejected_today ?? 0} format="int" icon="x" />
        </div>
        <div className="card">
          <KPI
            label="Limite auto-aprovação"
            value={config?.threshold_usdt ?? 0}
            format="usd"
            icon="dollar"
          />
        </div>
      </div>

      {/* M9: class-based grid so the rail stacks below the list < 1100px. */}
      <div className="grid grid-chart-rail" style={{ gap: 20 }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
            <h2 style={{ fontSize: 15, fontWeight: 600 }}>Ordens Pendentes</h2>
            <Badge variant={pending.length > 0 ? 'warn' : 'ok'}>
              {pending.length} aguardando
            </Badge>
          </div>
          {/* N4: filtro por par (chips com contagem) — a fila mistura BTC/XRP/BNB. */}
          {(() => {
            const counts = pending.reduce((m, o) => ((m[o.pair] = (m[o.pair] || 0) + 1), m), {});
            const pairs = Object.keys(counts);
            if (pairs.length <= 1) return null;
            return (
              <div className="hitl-chips">
                <button className={'chip-btn' + (!pairFilter ? ' active' : '')}
                  onClick={() => setPairFilter(null)}>Todos ({pending.length})</button>
                {pairs.map(p => (
                  <button key={p} className={'chip-btn' + (pairFilter === p ? ' active' : '')}
                    onClick={() => setPairFilter(p)}>{p} ({counts[p]})</button>
                ))}
              </div>
            );
          })()}
          {(() => {
            const shown = pairFilter ? pending.filter(o => o.pair === pairFilter) : pending;
            if (shown.length === 0) {
              return <EmptyState label="Nenhuma ordem pendente"
                sub={pairFilter ? `Nenhuma ordem de ${pairFilter}` : 'Todas as ordens foram processadas'} />;
            }
            return shown.map(order => (
              <PendingOrderCard key={order.id} order={order} onDecide={decide}
                ctx={deskCtx[order.pair]}
                highlight={focusPair != null && order.pair === focusPair} />
            ));
          })()}
        </div>

        <div className="card">
          <div className="card-head">
            <span className="card-title"><Icon name="shield" />Nível de Autonomia</span>
          </div>
          <div className="card-pad">
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {(config?.levels ?? []).map(lv => {
                const active = config?.current_level === lv.level;
                const canAutonomy = CT_AUTH.can('change_autonomy');
                const demoAutonomy = !canAutonomy && CT_AUTH.kind() === 'demo';
                return (
                  <button
                    key={lv.level}
                    onClick={canAutonomy ? () => setLevel(lv.level) : undefined}
                    disabled={!canAutonomy}
                    data-tip={demoAutonomy
                      ? 'Somente leitura no ambiente de demonstração — no produto real, este controle muda a autonomia'
                      : (!canAutonomy ? 'Seu perfil não altera o nível de autonomia' : undefined)}
                    style={{
                      display: 'flex', alignItems: 'flex-start', gap: 10,
                      padding: '10px 12px', borderRadius: 'var(--r-sm)',
                      border: `1.5px solid ${active ? 'var(--accent)' : 'var(--border)'}`,
                      background: active ? 'var(--surface-2)' : 'transparent',
                      cursor: canAutonomy ? 'pointer' : 'not-allowed', textAlign: 'left', width: '100%',
                    }}
                  >
                    <div style={{
                      width: 24, height: 24, borderRadius: 6, flexShrink: 0,
                      background: active ? 'var(--accent)' : 'var(--surface-3)',
                      color: active ? '#fff' : 'var(--ink-3)',
                      display: 'grid', placeItems: 'center',
                      fontFamily: 'var(--mono)', fontSize: 12, fontWeight: 600,
                    }}>
                      {lv.level}
                    </div>
                    <div>
                      <div style={{ fontSize: 12.5, fontWeight: 500, marginBottom: 2 }}>
                        {lv.description}
                      </div>
                      <div style={{ fontSize: 11, color: 'var(--ink-3)', fontFamily: 'var(--mono)' }}>
                        {fmtUsd(lv.threshold_usdt ?? 0, 0)} limite
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
window.ScreenHITL = ScreenHITL;
