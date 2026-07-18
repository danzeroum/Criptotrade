/* ============================================================
   Criptotrade — Screen: Ordens (lifecycle)
   ============================================================ */
const { useState: _useO } = React;

const ORDER_STATUS = {
  pending:   { label: 'Pendente', kind: 'warn', icon: 'clock' },
  approved:  { label: 'Aprovada', kind: 'info', icon: 'check' },
  filled:    { label: 'Executada', kind: 'ok', icon: 'check' },
  rejected:  { label: 'Rejeitada', kind: 'down', icon: 'x' },
  cancelled: { label: 'Cancelada', kind: 'neutral', icon: 'x' },
};

function OrderDrawer({ o, onClose }) {
  if (!o) return null;
  const s = ORDER_STATUS[o.status];
  const steps = ['pending', o.status === 'rejected' ? 'rejected' : o.status === 'cancelled' ? 'cancelled' : 'approved', 'filled'];
  const reached = { pending: true, approved: ['approved', 'filled'].includes(o.status), filled: o.status === 'filled', rejected: o.status === 'rejected', cancelled: o.status === 'cancelled' };
  return (
    <>
      <div className="drawer-scrim" onClick={onClose} />
      <div className="drawer">
        <div className="card-head" style={{ borderRadius: 0 }}>
          <div className="card-title"><span className="mono">{o.id}</span></div>
          <button className="btn btn-ghost" style={{ padding: 6 }} onClick={onClose}><Icon name="x" size={18} /></button>
        </div>
        <div style={{ overflowY: 'auto', padding: 18 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
            <Badge kind={o.side === 'buy' ? 'ok' : 'down'} dot>{o.side === 'buy' ? 'COMPRA' : 'VENDA'}</Badge>
            <b style={{ fontSize: 18 }}>{o.pair}</b>
            <Badge kind={s.kind}>{s.label}</Badge>
            {o.auto_approved && <span className="chip">auto</span>}
          </div>

          {/* lifecycle stepper */}
          <div className="label-xs" style={{ marginBottom: 10 }}>Lifecycle</div>
          <div style={{ display: 'flex', alignItems: 'center', marginBottom: 20 }}>
            {steps.map((st, i) => (
              <React.Fragment key={i}>
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 5 }}>
                  <div style={{ width: 26, height: 26, borderRadius: 99, display: 'grid', placeItems: 'center',
                    background: reached[st] ? (ORDER_STATUS[st].kind === 'down' ? 'var(--down)' : ORDER_STATUS[st].kind === 'neutral' ? 'var(--ink-3)' : 'var(--accent)') : 'var(--surface-3)',
                    color: reached[st] ? '#fff' : 'var(--ink-4)' }}>
                    <Icon name={ORDER_STATUS[st].icon} size={14} />
                  </div>
                  <span style={{ fontSize: 10.5, color: reached[st] ? 'var(--ink)' : 'var(--ink-4)', fontWeight: reached[st] ? 600 : 400 }}>{ORDER_STATUS[st].label}</span>
                </div>
                {i < steps.length - 1 && <div style={{ flex: 1, height: 2, background: reached[steps[i + 1]] ? 'var(--accent)' : 'var(--border-2)', margin: '0 6px', marginBottom: 18 }} />}
              </React.Fragment>
            ))}
          </div>

          <div className="card" style={{ marginBottom: 14 }}>
            <div className="card-pad">
              <StatRow k="Quantidade" v={fmtNum(o.quantity, 4)} />
              <StatRow k="Preço de entrada" v={fmtUsd(o.price)} />
              <StatRow k="Notional" v={fmtUsd(o.notional)} />
              <StatRow k="Tamanho de posição" v={fmtPct(o.sizePct)} />
              <StatRow k="Stop loss" v={fmtUsd(o.stop)} vColor="var(--down)" />
              <StatRow k="Take profit" v={fmtUsd(o.takeProfit)} vColor="var(--up)" />
              <StatRow k="Risk / Reward" v={o.rr + '×'} vColor={o.rr >= 2.5 ? 'var(--up)' : 'var(--warn)'} />
              <StatRow k="Confiança" v={Math.round(o.confidence * 100) + '%'} />
              <StatRow k="Estratégia" v={o.strategy} />
              <StatRow k="Agente" v={o.agent_id} />
            </div>
          </div>

          <div className="label-xs" style={{ marginBottom: 8 }}>Justificativa do agente</div>
          <div className="card card-pad" style={{ fontSize: 13, lineHeight: 1.55, color: 'var(--ink-2)', marginBottom: 14 }}>
            <Icon name="brain" size={15} style={{ color: 'var(--ink-3)', float: 'left', marginRight: 8 }} />{o.reason}
          </div>

          {o.operatorNote && (<>
            <div className="label-xs" style={{ marginBottom: 8 }}>Nota do operador</div>
            <div className="card card-pad" style={{ fontSize: 13, lineHeight: 1.5, marginBottom: 14, borderLeft: '3px solid var(--down)' }}>{o.operatorNote}</div>
          </>)}

          <div className="muted mono" style={{ fontSize: 11 }}>Criada em {o.created_at}</div>
        </div>
      </div>
    </>
  );
}

function OrdersScreen() {
  const [filter, setFilter] = _useO('all');
  const [sel, setSel] = _useO(null);
  const [pair] = useCurrentPair();
  const scoped = pair === 'ALL' ? CT.orders : CT.orders.filter(o => o.pair === pair);
  const counts = scoped.reduce((a, o) => { a[o.status] = (a[o.status] || 0) + 1; return a; }, {});
  const rows = filter === 'all' ? scoped : scoped.filter(o => o.status === filter);

  return (
    <div className="content-inner screen-enter">
      <div className="page-head">
        <div>
          <div className="page-title">Ordens</div>
          <div className="page-sub">Lifecycle completo · {scoped.length} {pair === 'ALL' ? 'ordens no ledger' : `ordens de ${pair}`}</div>
        </div>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <PairSelect allowAll />
          <Btn icon="plus" disabled title="POST /v1/orders — sem superfície no client (gap)">Nova ordem</Btn>
        </div>
      </div>

      {/* summary tiles */}
      <div className="grid" style={{ gridTemplateColumns: 'repeat(5,1fr)', marginBottom: 16 }}>
        {Object.entries(ORDER_STATUS).map(([k, v]) => (
          <button key={k} data-tip={`Filtrar apenas ordens com status "${v.label}". Clique de novo para limpar.`} onClick={() => setFilter(filter === k ? 'all' : k)} className="card kpi" style={{ textAlign: 'left', cursor: 'pointer', border: filter === k ? '2px solid var(--accent)' : '1px solid var(--border)' }}>
            <div className="kpi-label"><Icon name={v.icon} size={13} />{v.label}</div>
            <div className="kpi-value" style={{ fontSize: 24 }}>{counts[k] || 0}</div>
          </button>
        ))}
      </div>

      <div className="card">
        <CardHead icon="orders" title="Histórico de ordens"
          right={<div style={{ display: 'flex', gap: 8 }}>
            <Seg options={[{ value: 'all', label: 'Todas' }, { value: 'filled', label: 'Executadas' }, { value: 'pending', label: 'Pendentes' }, { value: 'rejected', label: 'Rejeitadas' }]} value={filter} onChange={setFilter} />
          </div>} />
        {rows.length === 0 ? <EmptyState min={200} message="Sem ordens" hint="Nenhuma ordem para o par e filtro selecionados." /> : (
        <table className="tbl">
          <thead>
            <tr>
              <th>ID</th><th>Par</th><th>Lado</th><th className="th-num">Qtd</th><th className="th-num">Notional</th>
              <th>Estratégia</th><th className="th-num">Confiança</th><th>Status</th><th>Criada</th><th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map(o => {
              const s = ORDER_STATUS[o.status];
              return (
                <tr key={o.id} style={{ cursor: 'pointer' }} onClick={() => setSel(o)}>
                  <td className="mono" style={{ fontSize: 12, color: 'var(--ink-2)' }}>{o.id}</td>
                  <td><b>{o.pair}</b></td>
                  <td><span style={{ color: o.side === 'buy' ? 'var(--up)' : 'var(--down)', fontWeight: 600, fontSize: 12 }}>{o.side === 'buy' ? 'COMPRA' : 'VENDA'}</span></td>
                  <td className="num">{fmtNum(o.quantity, 4)}</td>
                  <td className="num">{fmtUsd(o.notional)}</td>
                  <td><span className="chip">{o.strategy}</span></td>
                  <td className="num">{Math.round(o.confidence * 100)}%</td>
                  <td><Badge kind={s.kind} dot>{s.label}</Badge>{o.auto_approved && <span className="chip" style={{ marginLeft: 6, fontSize: 10 }}>auto</span>}</td>
                  <td className="mono" style={{ fontSize: 11.5, color: 'var(--ink-3)' }}>{o.created_at.slice(11)}</td>
                  <td><Icon name="chevron" size={15} style={{ color: 'var(--ink-4)' }} /></td>
                </tr>
              );
            })}
          </tbody>
        </table>
        )}
      </div>

      <OrderDrawer o={sel} onClose={() => setSel(null)} />
    </div>
  );
}

window.OrdersScreen = OrdersScreen;
