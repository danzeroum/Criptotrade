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

function PendingOrderCard({ order, onDecide, highlight = false }) {
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
      <div className="card-pad">
        <div className="grid" style={{ gridTemplateColumns: 'repeat(5, 1fr)', marginBottom: 12, gap: 0 }}>
          {[
            { label: 'Quantidade', value: String(order.quantity) },
            { label: 'Preço', value: `$${(order.price ?? 0).toLocaleString('en', { minimumFractionDigits: 2 })}` },
            { label: 'Nocional', value: `$${(order.notional ?? 0).toLocaleString('en', { minimumFractionDigits: 2 })}` },
            { label: 'Stop Loss', value: order.stop_loss ? `$${order.stop_loss.toLocaleString('en', { minimumFractionDigits: 2 })}` : '—', color: 'var(--down)' },
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

        <ConfidenceBreakdown breakdown={CT.confidenceBreakdown} />

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
      </div>
    </div>
  );
}

function ScreenHITL({ addToast }) {
  const mock = !!window.USE_MOCK_DATA;

  const mockConfig = {
    current_level: CT.hitl.level,
    threshold_usdt: CT.hitl.threshold,
    level_description: CT.hitl.levels[CT.hitl.level]?.desc ?? '',
    pending_orders_count: CT.pendingOrders.length,
    human_approved_today: CT.hitl.approvedToday,
    human_rejected_today: CT.hitl.rejectedToday,
    levels: CT.hitl.levels.map(l => ({
      level: l.level,
      threshold_usdt: l.threshold,
      description: l.desc,
    })),
  };
  const mockOrders = CT.pendingOrders.map(o => ({
    ...o,
    stop_loss: o.stop,
    take_profit: o.takeProfit,
    position_size_pct: o.sizePct,
  }));

  const [config, setConfig] = useState(mock ? mockConfig : null);
  const [orders, setOrders] = useState(mock ? mockOrders : []);
  const [loading, setLoading] = useState(!mock);
  const [error, setError] = useState(null);
  // M2: pair handed over by Mercado's "Ver no HITL" — highlight its orders once.
  const [focusPair] = useState(() => {
    try {
      const p = sessionStorage.getItem('ct.hitl.focus');
      if (p) sessionStorage.removeItem('ct.hitl.focus');
      return p || null;
    } catch (_) { return null; }
  });

  const load = useCallback(() => {
    if (mock) return;
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
  }, [mock]);

  useEffect(() => { load(); }, [load]);

  const decide = async (orderId, action, note) => {
    if (mock) {
      setOrders(prev => prev.filter(o => o.id !== orderId));
      return;
    }
    try {
      await CT_API.decideOrder(orderId, {
        action,
        operator_note: note || undefined,
        operator_id: 'operator',
      });
      load();
      addToast?.(action === 'approved' ? 'Ordem aprovada' : 'Ordem rejeitada', 'check');
    } catch (e) {
      console.error('decide error', e);
      addToast?.('Erro ao processar a ordem', 'alert');
    }
  };

  const setLevel = async (level) => {
    if (mock) {
      setConfig(prev => ({
        ...prev,
        current_level: level,
        level_description: prev.levels[level]?.description ?? '',
      }));
      return;
    }
    try {
      const updated = await CT_API.patchHITL({
        level,
        reason: 'Alterado via console',
        operator: 'operator',
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
          {pending.length === 0 ? (
            <EmptyState label="Nenhuma ordem pendente" sub="Todas as ordens foram processadas" />
          ) : (
            pending.map(order => (
              <PendingOrderCard key={order.id} order={order} onDecide={decide}
                highlight={focusPair != null && order.pair === focusPair} />
            ))
          )}
        </div>

        <div className="card">
          <div className="card-head">
            <span className="card-title"><Icon name="shield" />Nível de Autonomia</span>
          </div>
          <div className="card-pad">
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {(config?.levels ?? []).map(lv => {
                const active = config?.current_level === lv.level;
                return (
                  <button
                    key={lv.level}
                    onClick={() => setLevel(lv.level)}
                    style={{
                      display: 'flex', alignItems: 'flex-start', gap: 10,
                      padding: '10px 12px', borderRadius: 'var(--r-sm)',
                      border: `1.5px solid ${active ? 'var(--accent)' : 'var(--border)'}`,
                      background: active ? 'var(--surface-2)' : 'transparent',
                      cursor: 'pointer', textAlign: 'left', width: '100%',
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
                        ${(lv.threshold_usdt ?? 0).toLocaleString('en')} limite
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
