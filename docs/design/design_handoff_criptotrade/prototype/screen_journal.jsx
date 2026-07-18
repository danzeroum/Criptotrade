/* ============================================================
   Criptotrade — Screen: Diário Comportamental
   ============================================================ */
const { useState: _useJ } = React;

function EmotionDots({ value }) {
  return (
    <span style={{ display: 'inline-flex', gap: 2 }}>
      {Array.from({ length: 10 }, (_, i) => (
        <span key={i} style={{ width: 6, height: 6, borderRadius: 99, background: i < value ? (value <= 3 ? 'var(--up)' : value <= 6 ? 'var(--warn)' : 'var(--down)') : 'var(--surface-3)' }} />
      ))}
    </span>
  );
}

function JournalScreen() {
  const m = CT.journalMetrics;
  const barData = m.byEmotion.map(b => ({ label: b.label, label2: b.band, value: Math.round(b.winRate * 100), color: b.winRate > 0.6 ? 'var(--up)' : b.winRate > 0.45 ? 'var(--warn)' : 'var(--down)' }));

  return (
    <div className="content-inner screen-enter">
      <div className="page-head">
        <div>
          <div className="page-title">Diário Comportamental</div>
          <div className="page-sub">Disciplina × resultado · {CT.journal.length} registros · calibra Kelly e overconfidence guard</div>
        </div>
        <Btn kind="primary" icon="plus" data-tip="Adiciona um registro ao diário: emoção, contexto e lição do trade.">Novo registro</Btn>
      </div>

      {/* metrics */}
      <div className="grid" style={{ gridTemplateColumns: 'repeat(4,1fr)', marginBottom: 16 }}>
        <KPI label="Win rate real" icon="target" value={fmtPct(m.realWinRate * 100)} sub="usado p/ calibrar Kelly" />
        <KPI label="P&L · plano seguido" icon="check" value={'+' + fmtPct(m.planFollowedPnl)} accent="var(--up)" sub="média por trade" />
        <KPI label="P&L · desviou do plano" icon="x" value={fmtPct(m.planDeviatedPnl)} accent="var(--down)" sub="média por trade" />
        <KPI label="Correlação disciplina" icon="pulse" value={fmtNum(m.disciplineCorrelation, 2)} sub="seguir plano × lucro" />
      </div>

      {/* charts */}
      <div className="grid" style={{ gridTemplateColumns: '1fr 1fr 1fr', gap: 16, marginBottom: 16 }}>
        <div className="card">
          <CardHead icon="market" title="Win rate por estado emocional" />
          <div className="card-pad" style={{ paddingTop: 4 }}>
            <BarChart data={barData} height={186} fmt={v => v + '%'} max={100} />
            <div className="muted" style={{ fontSize: 11, textAlign: 'center', marginTop: 2 }}>Estado emocional antes da entrada (escala 1–10)</div>
          </div>
        </div>
        <div className="card">
          <CardHead icon="pulse" title="Estado emocional × P&L" right={<span style={{ display: 'flex', gap: 8, fontSize: 10.5, color: 'var(--ink-3)' }}><span style={{ display: 'flex', gap: 3, alignItems: 'center' }}><span style={{ width: 7, height: 7, borderRadius: 99, background: 'var(--accent)' }} />seguiu</span><span style={{ display: 'flex', gap: 3, alignItems: 'center' }}><span style={{ width: 7, height: 7, borderRadius: 99, border: '1.5px solid var(--ink-4)' }} />desviou</span></span>} />
          <div className="card-pad" style={{ paddingTop: 6 }}>
            <Scatter data={CT.journalScatter} height={186} xLabel="estado emocional (1–10)" yLabel="P&L %" />
          </div>
        </div>
        <div className="card">
          <CardHead icon="grid" title="Heatmap · dia × hora" sub="taxa de acerto" />
          <div className="card-pad" style={{ paddingTop: 10 }}>
            <Heatmap days={CT.heatmap.days} data={CT.heatmap.data} height={186} />
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, justifyContent: 'center', marginTop: 6, fontSize: 10.5, color: 'var(--ink-3)' }}>
              <span>baixa</span>
              <span style={{ width: 60, height: 8, borderRadius: 99, background: 'linear-gradient(90deg, rgba(220,43,43,.6), var(--surface-3), rgba(14,157,110,.85))' }} />
              <span>alta</span>
            </div>
          </div>
        </div>
      </div>

      {/* journal table */}
      <div className="card">
        <CardHead icon="journal" title="Registros de operação" sub={CT.journal.length + ' trades'} />
        <table className="tbl">
          <thead>
            <tr>
              <th>Data</th><th>Setup</th><th>Emoção antes</th><th>Emoção depois</th>
              <th>Stop?</th><th>Plano seguido?</th><th className="th-num">P&L</th>
            </tr>
          </thead>
          <tbody>
            {CT.journal.map(j => (
              <tr key={j.id}>
                <td className="mono" style={{ fontSize: 12 }}>{j.date}</td>
                <td><span className="chip">{j.setup}</span></td>
                <td><div style={{ display: 'flex', gap: 8, alignItems: 'center' }}><EmotionDots value={j.before} /><span className="mono muted" style={{ fontSize: 11 }}>{j.before}</span></div></td>
                <td><div style={{ display: 'flex', gap: 8, alignItems: 'center' }}><EmotionDots value={j.after} /><span className="mono muted" style={{ fontSize: 11 }}>{j.after}</span></div></td>
                <td>{j.stopDefined ? <Icon name="check" size={15} style={{ color: 'var(--up)' }} /> : <Icon name="x" size={15} style={{ color: 'var(--down)' }} />}</td>
                <td>{j.followed ? <Badge kind="ok">sim</Badge> : <Badge kind="down">não</Badge>}</td>
                <td className="num" style={{ color: j.pnl >= 0 ? 'var(--up)' : 'var(--down)', fontWeight: 600 }}>{j.pnl >= 0 ? '+' : ''}{fmtNum(j.pnl, 2)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

window.JournalScreen = JournalScreen;
