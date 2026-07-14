/* ============================================================
   Criptotrade — Screen: Trading Journal
   ============================================================ */
const { useState, useEffect } = React;

const SETUPS = ['Grid · suporte', 'DCA · pullback', 'Mean reversion · RSI<30', 'Breakout triângulo', 'Double bottom', 'Outro'];

function EmotionEmoji({ value }) {
  if (value <= 3) return '😰';
  if (value <= 6) return '😐';
  return '😤';
}

function JournalEntryRow({ entry }) {
  const pnlColor = (entry.pnl ?? entry.pnl_pct ?? 0) >= 0 ? 'var(--up)' : 'var(--down)';
  const pnl = entry.pnl ?? entry.pnl_pct ?? 0;
  const before = entry.before ?? entry.emotion_before;
  const after  = entry.after  ?? entry.emotion_after;
  const stop   = entry.stopDefined ?? entry.stop_defined;
  const followed = entry.followed ?? entry.plan_followed;
  return (
    <tr>
      <td style={{ fontFamily: 'var(--mono)', fontSize: 11.5, color: 'var(--ink-3)' }}>
        {(entry.date ?? entry.created_at ?? '').substring(0, 10)}
      </td>
      <td style={{ fontSize: 12.5 }}>{entry.setup}</td>
      <td style={{ textAlign: 'center' }}>
        <span title={`Emoção: ${before}`}>
          <EmotionEmoji value={before} /> {before}
        </span>
      </td>
      <td style={{ textAlign: 'center' }}>
        {after != null ? (
          <span title={`Emoção: ${after}`}>
            <EmotionEmoji value={after} /> {after}
          </span>
        ) : '—'}
      </td>
      <td style={{ textAlign: 'center' }}>
        {stop ? <Badge variant="ok" dot={false}>✓</Badge> : <Badge variant="down" dot={false}>✗</Badge>}
      </td>
      <td style={{ textAlign: 'center' }}>
        {followed ? <Badge variant="ok" dot={false}>Sim</Badge> : <Badge variant="warn" dot={false}>Não</Badge>}
      </td>
      <td className="num" style={{ color: pnlColor, fontWeight: 500 }}>
        {pnl > 0 ? '+' : ''}{pnl?.toFixed(2)}%
      </td>
      <td style={{ fontSize: 11.5, color: 'var(--ink-3)', maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {entry.note}
      </td>
    </tr>
  );
}

function NewEntryForm({ onSave, onCancel }) {
  const [form, setForm] = useState({
    setup: SETUPS[0],
    emotion_before: 5,
    stop_defined: true,
    plan_followed: true,
    pnl_pct: '',
    note: '',
  });
  const [saving, setSaving] = useState(false);

  const update = (k, v) => setForm(prev => ({ ...prev, [k]: v }));

  const submit = async () => {
    setSaving(true);
    await onSave({
      ...form,
      pnl_pct: form.pnl_pct !== '' ? parseFloat(form.pnl_pct) : null,
    });
    setSaving(false);
  };

  return (
    <div className="card" style={{ marginBottom: 20 }}>
      <div className="card-head">
        <span className="card-title"><Icon name="plus" />Novo Registro</span>
        <Btn variant="ghost" size="sm" onClick={onCancel}><Icon name="x" size={14} /></Btn>
      </div>
      <div className="card-pad">
        <div className="grid" style={{ gridTemplateColumns: 'repeat(2, 1fr)', gap: 16, marginBottom: 16 }}>
          <div>
            <div className="label-xs" style={{ marginBottom: 8 }}>Setup / Estratégia</div>
            <select
              value={form.setup}
              onChange={e => update('setup', e.target.value)}
              className="input"
              style={{ width: '100%' }}
            >
              {SETUPS.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
          <div>
            <SliderField
              label={`Emoção antes do trade: ${form.emotion_before} — ${form.emotion_before <= 3 ? '😰 Baixa' : form.emotion_before <= 6 ? '😐 Neutra' : '😤 Alta'}`}
              value={form.emotion_before}
              min={1} max={10}
              onChange={v => update('emotion_before', v)}
            />
          </div>
          <div>
            <NumField
              label="P&L (%)"
              value={form.pnl_pct}
              onChange={v => update('pnl_pct', v)}
              step={0.01}
              unit="%"
            />
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12, paddingTop: 18 }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer' }}>
              <button
                className={`toggle${form.stop_defined ? ' on' : ''}`}
                onClick={() => update('stop_defined', !form.stop_defined)}
                type="button"
              />
              <span style={{ fontSize: 13 }}>Stop loss definido</span>
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer' }}>
              <button
                className={`toggle${form.plan_followed ? ' on' : ''}`}
                onClick={() => update('plan_followed', !form.plan_followed)}
                type="button"
              />
              <span style={{ fontSize: 13 }}>Plano seguido</span>
            </label>
          </div>
        </div>
        <div style={{ marginBottom: 14 }}>
          <div className="label-xs" style={{ marginBottom: 6 }}>Nota (opcional)</div>
          <textarea
            className="input"
            rows={2}
            value={form.note}
            onChange={e => update('note', e.target.value)}
            placeholder="O que aconteceu nesse trade?"
            style={{ resize: 'vertical' }}
          />
        </div>
        <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
          <Btn variant="ghost" size="sm" onClick={onCancel}>Cancelar</Btn>
          <Btn variant="primary" size="sm" onClick={submit} disabled={saving}>
            <Icon name="check" size={13} /> Salvar registro
          </Btn>
        </div>
      </div>
    </div>
  );
}

function ScreenJournal({ addToast }) {
  const mock = !!window.USE_MOCK_DATA;
  const mockEntries = CT.journal;
  const mockMetrics = CT.journalMetrics;

  const [entries,  setEntries]  = useState(mock ? mockEntries : null);
  const [metrics,  setMetrics]  = useState(mock ? mockMetrics : null);
  const [loading,  setLoading]  = useState(!mock);
  const [error,    setError]    = useState(null);
  const [showForm, setShowForm] = useState(false);

  const load = () => {
    if (mock) return;
    setLoading(true);
    Promise.all([CT_API.getJournal(), CT_API.getJournalMetrics()])
      .then(([e, m]) => {
        setEntries(Array.isArray(e) ? e : []);
        setMetrics(m);
        setLoading(false);
      })
      .catch(e => { setError(e); setLoading(false); });
  };

  useEffect(() => { load(); }, []);

  const save = async (entry) => {
    if (mock) {
      setEntries(prev => [{ id: Date.now(), date: new Date().toISOString().substring(0, 10), ...entry }, ...prev]);
      setShowForm(false);
      return;
    }
    try {
      await CT_API.addJournalEntry(entry);
      setShowForm(false);
      load();
      addToast?.('Entrada registrada no diário', 'check');
    } catch (e) {
      console.error('save journal entry', e);
      addToast?.('Erro ao salvar a entrada do diário', 'alert');
    }
  };

  if (loading) return <LoadingState label="Carregando diário…" />;
  if (error)   return <ErrorState message="Erro ao carregar diário" onRetry={() => { setError(null); load(); }} />;

  const allEntries = entries ?? [];
  const scatter = mock ? CT.journalScatter : allEntries.map(e => ({
    x: e.emotion_before ?? e.before,
    y: e.pnl_pct ?? e.pnl,
    followed: e.plan_followed ?? e.followed,
  }));
  const heatmap = mock ? CT.heatmap : null;
  const byEmotion = metrics?.byEmotion ?? metrics?.by_emotion ?? [];
  const planFollowedPnl = metrics?.planFollowedPnl ?? metrics?.plan_followed_pnl;
  const planDeviatedPnl = metrics?.planDeviatedPnl ?? metrics?.plan_deviated_pnl;
  const correlation = metrics?.disciplineCorrelation ?? metrics?.discipline_correlation;
  const realWinRate = metrics?.realWinRate ?? metrics?.real_win_rate;

  return (
    <div>
      <div className="page-head">
        <div>
          <h1 className="page-title">Diário Comportamental</h1>
          <div className="page-sub">Registro de emoções, disciplina e correlação com resultados</div>
        </div>
        <Btn variant="primary" size="sm" onClick={() => setShowForm(true)}>
          <Icon name="plus" size={13} /> Novo registro
        </Btn>
      </div>

      {showForm && <NewEntryForm onSave={save} onCancel={() => setShowForm(false)} />}

      {/* Metrics row */}
      {metrics && (
        <div className="grid" style={{ gridTemplateColumns: 'repeat(4, 1fr)', marginBottom: 20 }}>
          <div className="card">
            <KPI label="Win rate real" value={realWinRate != null ? realWinRate * 100 : null} format="pct_direct" icon="trending" />
          </div>
          <div className="card">
            <KPI label="PnL (plano seguido)" value={planFollowedPnl} format="pct_direct" delta={planFollowedPnl} icon="check" />
          </div>
          <div className="card">
            <KPI label="PnL (desviou)" value={planDeviatedPnl} format="pct_direct" delta={planDeviatedPnl} icon="x" />
          </div>
          <div className="card">
            <KPI label="Corr. disciplina" value={correlation != null ? correlation * 100 : null} format="pct_direct" icon="activity" />
          </div>
        </div>
      )}

      <div className="grid" style={{ gridTemplateColumns: '1fr 1fr', marginBottom: 20 }}>
        {/* Scatter: emoção × P&L */}
        <div className="card">
          <div className="card-head">
            <span className="card-title"><Icon name="activity" />Emoção × P&L</span>
          </div>
          <div className="card-pad">
            {scatter && scatter.length > 0 ? (
              <ScatterChart points={scatter} height={200} />
            ) : (
              <EmptyState label="Sem dados de dispersão" />
            )}
          </div>
        </div>

        {/* Heatmap win rate dia × hora */}
        <div className="card">
          <div className="card-head">
            <span className="card-title"><Icon name="clock" />Win rate por horário</span>
          </div>
          <div className="card-pad">
            {heatmap ? (
              <Heatmap data={heatmap} height={200} />
            ) : (
              <EmptyState label="Sem dados de heatmap" />
            )}
          </div>
        </div>
      </div>

      {/* By emotion bands */}
      {byEmotion.length > 0 && (
        <div className="card" style={{ marginBottom: 20 }}>
          <div className="card-head">
            <span className="card-title"><Icon name="bar" />Win rate por estado emocional</span>
          </div>
          <div className="card-pad">
            <div className="grid" style={{ gridTemplateColumns: 'repeat(3, 1fr)', gap: 20 }}>
              {byEmotion.map(b => (
                <div key={b.band} style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: 24 }}>
                    {b.band === '1–3' || b.band === '1-3' ? '😰' : b.band === '4–6' || b.band === '4-6' ? '😐' : '😤'}
                  </div>
                  <div style={{ fontSize: 12.5, color: 'var(--ink-2)', marginTop: 6 }}>Emoção {b.band}</div>
                  <div style={{ fontFamily: 'var(--mono)', fontSize: 22, fontWeight: 600, marginTop: 4 }}>
                    {((b.win_rate ?? b.winRate ?? 0) * 100).toFixed(0)}%
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--ink-3)' }}>{b.trades} trades</div>
                  <div style={{ marginTop: 8 }}>
                    <Meter value={(b.win_rate ?? b.winRate ?? 0) * 100} max={100} warn={50} crit={80} />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Journal entries table */}
      <div className="card">
        <div className="card-head">
          <span className="card-title"><Icon name="book" />Registros</span>
          <span style={{ fontSize: 12, color: 'var(--ink-3)' }}>{allEntries.length} entradas</span>
        </div>
        {allEntries.length === 0 ? (
          <EmptyState label="Nenhum registro ainda" sub="Adicione seu primeiro registro acima" />
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="tbl">
              <thead>
                <tr>
                  <th>Data</th>
                  <th>Setup</th>
                  <th className="th-num">Emo. antes</th>
                  <th className="th-num">Emo. depois</th>
                  <th style={{ textAlign: 'center' }}>Stop</th>
                  <th style={{ textAlign: 'center' }}>Plano</th>
                  <th className="th-num">P&L</th>
                  <th>Nota</th>
                </tr>
              </thead>
              <tbody>
                {allEntries.map((entry, i) => (
                  <JournalEntryRow key={entry.id ?? i} entry={entry} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
window.ScreenJournal = ScreenJournal;
