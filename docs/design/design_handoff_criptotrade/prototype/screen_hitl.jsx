/* ============================================================
   Criptotrade — Screen: Console HITL
   ============================================================ */
const { useState: _useH } = React;

function AutonomyCard({ lvl, active, onClick }) {
  return (
    <button onClick={onClick} data-tip={`Nível ${lvl.level}: define até que valor a IA aprova ordens sozinha. Clique para ativar este nível.`} className="card card-pad" style={{
      textAlign: 'left', cursor: 'pointer',
      border: active ? '2px solid var(--accent)' : '1px solid var(--border)',
      background: active ? 'var(--surface)' : 'var(--surface-2)',
      boxShadow: active ? 'var(--sh)' : 'none', position: 'relative',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <span className="mono" style={{ fontSize: 13, fontWeight: 600 }}>Nível {lvl.level}</span>
        {active && <Badge kind="solid">ativo</Badge>}
      </div>
      <div className="mono" style={{ fontSize: 18, fontWeight: 500 }}>{lvl.threshold === 0 ? 'Manual' : fmtUsd(lvl.threshold, 0)}</div>
      <div className="muted" style={{ fontSize: 11, marginTop: 6, lineHeight: 1.4 }}>{lvl.desc}</div>
    </button>
  );
}

function ConfidenceBreakdown() {
  return (
    <div>
      <div className="label-xs" style={{ marginBottom: 10 }}>Breakdown da confiança · 5 fatores</div>
      {CT.confidenceBreakdown.map((f, i) => (
        <div key={i} style={{ marginBottom: 9 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 4 }}>
            <span style={{ color: 'var(--ink-2)' }}>{f.key} <span className="muted mono" style={{ fontSize: 10.5 }}>· peso {Math.round(f.weight * 100)}%</span></span>
            <span className="mono" style={{ fontWeight: 600 }}>{Math.round(f.score * 100)}%</span>
          </div>
          <Meter value={f.score * 100} color={f.score > 0.7 ? 'var(--up)' : f.score > 0.5 ? 'var(--ink)' : 'var(--warn)'} height={5} />
        </div>
      ))}
    </div>
  );
}

function PendingOrderCard({ o, threshold, onDecide }) {
  const [expanded, setExpanded] = _useH(false);
  const [note, setNote] = _useH('');
  const [rejecting, setRejecting] = _useH(false);
  const auto = o.notional <= threshold && !o.critical;
  return (
    <div className="card" style={{ marginBottom: 14 }}>
      <div className="card-pad">
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 14 }}>
          <DonutProgress value={o.confidence} size={58} stroke={7} label={Math.round(o.confidence * 100) + '%'} color="var(--accent)" />
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 9, flexWrap: 'wrap' }}>
              <Badge kind={o.side === 'buy' ? 'ok' : 'down'} dot>{o.side === 'buy' ? 'COMPRA' : 'VENDA'}</Badge>
              <b style={{ fontSize: 15 }}>{o.pair}</b>
              <span className="chip">{o.strategy}</span>
              {o.critical && <Badge kind="down"><Icon name="warn" size={12} />crítica</Badge>}
              <Badge kind={auto ? 'info' : 'warn'}>{auto ? 'auto-elegível' : 'exige humano'}</Badge>
              <span className="mono muted" style={{ fontSize: 11, marginLeft: 'auto' }}>{o.created_at.slice(11)}</span>
            </div>
            <div style={{ fontSize: 12.5, color: 'var(--ink-2)', marginTop: 8, lineHeight: 1.5 }}>{o.reason}</div>
          </div>
        </div>

        {/* metrics strip */}
        <div style={{ display: 'flex', gap: 0, marginTop: 14, border: '1px solid var(--border)', borderRadius: 8, overflow: 'hidden' }}>
          {[
            ['Qtd', fmtNum(o.quantity, 4)], ['Preço', fmtUsd(o.price)],
            ['Notional', fmtUsd(o.notional), o.notional > threshold ? 'var(--warn)' : 'var(--ink)'],
            ['Tamanho', fmtPct(o.sizePct)], ['Stop', fmtUsd(o.stop), 'var(--down)'],
            ['Take profit', fmtUsd(o.takeProfit), 'var(--up)'], ['R/R', o.rr + '×', o.rr >= 2.5 ? 'var(--up)' : 'var(--warn)'],
          ].map(([k, v, c], i) => (
            <div key={i} style={{ padding: '8px 12px', flex: 1, borderRight: i < 6 ? '1px solid var(--border)' : 'none', background: 'var(--surface-2)', minWidth: 70 }}>
              <div className="label-xs" style={{ fontSize: 9.5 }}>{k}</div>
              <div className="mono" style={{ fontSize: 13, fontWeight: 500, marginTop: 3, color: c || 'var(--ink)' }}>{v}</div>
            </div>
          ))}
        </div>

        {expanded && (
          <div className="grid" style={{ gridTemplateColumns: '1fr 1fr', gap: 24, marginTop: 16, paddingTop: 16, borderTop: '1px solid var(--border)' }}>
            <ConfidenceBreakdown />
            <div>
              <div className="label-xs" style={{ marginBottom: 10 }}>Guardrails (Risk Agent)</div>
              {CT.guardrails.map((g, i) => (
                <div key={i} className="stat-row" style={{ padding: '6px 0' }}>
                  <span style={{ display: 'flex', gap: 7, alignItems: 'center', fontSize: 12 }}>
                    <Icon name={g.ok ? 'check' : 'x'} size={14} style={{ color: g.ok ? 'var(--up)' : 'var(--down)' }} />{g.key}
                  </span>
                  <span className="mono" style={{ fontSize: 11.5 }}><span className="muted">{g.limit}</span> · <b>{g.value}</b></span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* actions */}
        {!rejecting ? (
          <div style={{ display: 'flex', gap: 9, marginTop: 14, alignItems: 'center' }}>
            <Btn kind="up" icon="check" data-tip="Aprova a ordem: ela sai de pendente e segue para execução (paper)." onClick={() => onDecide(o.id, 'approve')}>Aprovar</Btn>
            <Btn kind="down" icon="x" data-tip="Rejeita a ordem. Você registra o motivo antes de confirmar." onClick={() => setRejecting(true)}>Rejeitar</Btn>
            <button className="btn btn-ghost btn-sm" onClick={() => setExpanded(e => !e)} style={{ marginLeft: 'auto' }}>
              {expanded ? 'Ocultar detalhes' : 'Ver breakdown & guardrails'}
              <Icon name="chevronDown" size={14} style={{ transform: expanded ? 'rotate(180deg)' : 'none', transition: 'transform .15s' }} />
            </button>
          </div>
        ) : (
          <div style={{ marginTop: 14, padding: 14, background: 'var(--down-bg)', borderRadius: 9, border: '1px solid var(--down-line)' }}>
            <div className="field-label" style={{ marginBottom: 7 }}>Nota da rejeição <span className="muted">(obrigatória)</span></div>
            <textarea className="input" rows={2} value={note} onChange={e => setNote(e.target.value)} placeholder="Ex.: volatilidade alta antes de evento macro" style={{ fontFamily: 'var(--sans)', resize: 'vertical' }} />
            <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
              <Btn kind="down" icon="x" disabled={!note.trim()} onClick={() => onDecide(o.id, 'reject', note)}>Confirmar rejeição</Btn>
              <Btn onClick={() => { setRejecting(false); setNote(''); }}>Cancelar</Btn>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function HitlScreen({ toast, setPendingCount }) {
  const [level, setLevel] = _useH(CT.hitl.level);
  const [pending, setPending] = _useH(CT.pendingOrders);
  const [approved, setApproved] = _useH(CT.hitl.approvedToday);
  const [rejected, setRejected] = _useH(CT.hitl.rejectedToday);
  const threshold = CT.hitl.levels[level].threshold;

  const decide = (id, decision, note) => {
    setPending(p => {
      const next = p.filter(o => o.id !== id);
      setPendingCount(next.length);
      return next;
    });
    if (decision === 'approve') { setApproved(a => a + 1); toast('Ordem aprovada — enviada para execução'); }
    else { setRejected(r => r + 1); toast('Ordem rejeitada'); }
  };

  const changeLevel = (l) => { setLevel(l); toast(`Autonomia alterada para Nível ${l}`); };

  return (
    <div className="content-inner screen-enter">
      <div className="page-head">
        <div>
          <div className="page-title">Console HITL</div>
          <div className="page-sub">Human-in-the-loop · aprovação de ordens · timeout {CT.hitl.decisionTimeout}s (fail-closed)</div>
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
          <span className="chip"><Icon name="check" size={13} style={{ color: 'var(--up)' }} />{approved} aprovadas hoje</span>
          <span className="chip"><Icon name="x" size={13} style={{ color: 'var(--down)' }} />{rejected} rejeitadas hoje</span>
        </div>
      </div>

      {/* autonomy levels */}
      <div className="card" style={{ marginBottom: 22 }}>
        <CardHead icon="zap" title="Nível de autonomia" sub="threshold de auto-aprovação por notional" />
        <div className="card-pad">
          <div className="grid" style={{ gridTemplateColumns: 'repeat(4,1fr)' }}>
            {CT.hitl.levels.map(l => <AutonomyCard key={l.level} lvl={l} active={level === l.level} onClick={() => changeLevel(l.level)} />)}
          </div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginTop: 14, fontSize: 12, color: 'var(--ink-2)' }}>
            <Icon name="info" size={15} style={{ color: 'var(--ink-3)' }} />
            Ordens ≤ <b className="mono">{threshold === 0 ? '$0' : fmtUsd(threshold, 0)}</b> e não-críticas são auto-aprovadas (<span className="mono">pending → filled</span>). Acima disso, exigem sua decisão.
          </div>
        </div>
      </div>

      {/* pending queue */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, margin: '4px 0 14px' }}>
        <Icon name="hitl" size={15} style={{ color: 'var(--ink-3)' }} />
        <h3 style={{ fontSize: 14 }}>Fila de aprovação</h3>
        <Badge kind={pending.length ? 'warn' : 'ok'}>{`${pending.length} pendente${pending.length !== 1 ? 's' : ''}`}</Badge>
      </div>

      {pending.length ? pending.map(o => (
        <PendingOrderCard key={o.id} o={o} threshold={threshold} onDecide={decide} />
      )) : (
        <div className="card card-pad" style={{ display: 'grid', placeItems: 'center', minHeight: 220, textAlign: 'center', gap: 10 }}>
          <div style={{ width: 46, height: 46, borderRadius: 99, background: 'var(--up-bg)', display: 'grid', placeItems: 'center', color: 'var(--up)' }}><Icon name="check" size={24} /></div>
          <div style={{ fontWeight: 600 }}>Fila limpa</div>
          <div className="muted" style={{ fontSize: 13 }}>Nenhuma ordem aguardando aprovação. O loop continua operando.</div>
        </div>
      )}
    </div>
  );
}

window.HitlScreen = HitlScreen;
window.ConfidenceBreakdown = ConfidenceBreakdown;
