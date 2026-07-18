/* ============================================================
   Criptotrade — Screen: Configurações
   ============================================================ */
const { useState: _useS } = React;

const SETTINGS_SECTIONS = [
  { id: 'general', label: 'Geral', icon: 'settings' },
  { id: 'risk', label: 'Risco', icon: 'risk' },
  { id: 'strategies', label: 'Estratégias', icon: 'target' },
  { id: 'journal', label: 'Diário', icon: 'journal' },
  { id: 'backtest', label: 'Backtest', icon: 'backtest' },
  { id: 'alerts', label: 'Alertas', icon: 'bell' },
];

function SettingRow({ title, desc, children }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 20, padding: '16px 0', borderBottom: '1px solid var(--border)' }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 13.5, fontWeight: 500 }}>{title}</div>
        {desc && <div className="muted" style={{ fontSize: 12, marginTop: 2, lineHeight: 1.4 }}>{desc}</div>}
      </div>
      <div style={{ width: 220, flexShrink: 0 }}>{children}</div>
    </div>
  );
}

function SettingsScreen({ toast }) {
  const [sec, setSec] = _useS('general');
  const [s, setS] = _useS({
    autonomy: 2, interval: 60, dryRun: true, exchange: 'binance', initialCapital: 10000,
    kellyFraction: 0.25, minPos: 0.5, maxPos: 5, ddDaily: 3, ddWeekly: 6, ddMonthly: 15,
    emotionScale: 10, customFields: true, requireStopNote: true,
    commission: 0.1, slippage: 5, wfWindow: 252, mcSims: 1000,
    revengeSize: 50, euphoriaSize: 20, overconfGap: 15, riskOfRuin: 5,
  });
  const set = (k, v) => setS(o => ({ ...o, [k]: v }));

  return (
    <div className="content-inner screen-enter">
      <div className="page-head">
        <div>
          <div className="page-title">Configurações</div>
          <div className="page-sub">Todos os parâmetros do sistema · alterações registradas no ledger</div>
        </div>
      </div>

      <div className="grid" style={{ gridTemplateColumns: '210px 1fr', gap: 18, alignItems: 'start' }}>
        {/* section nav */}
        <div className="card" style={{ padding: 8, position: 'sticky', top: 0 }}>
          {SETTINGS_SECTIONS.map(sx => (
            <div key={sx.id} className={'nav-item' + (sec === sx.id ? ' active' : '')} data-tip={`Configurações de ${sx.label}.`} onClick={() => setSec(sx.id)}>
              <Icon name={sx.icon} size={16} className="ico" />{sx.label}
            </div>
          ))}
        </div>

        {/* content */}
        <div className="card">
          <CardHead title={SETTINGS_SECTIONS.find(x => x.id === sec).label}
            right={<Btn kind="primary" sm icon="check" data-tip="Salva as alterações desta seção (registradas no ledger de auditoria)." onClick={() => toast('Configurações salvas')}>Salvar alterações</Btn>} />
          <div className="card-pad" style={{ paddingTop: 4 }}>

            {sec === 'general' && <>
              <SettingRow title="Nível de autonomia (HITL)" desc="Threshold de auto-aprovação de ordens por notional (0–3)">
                <Seg options={[{ value: 0, label: '0' }, { value: 1, label: '1' }, { value: 2, label: '2' }, { value: 3, label: '3' }]} value={s.autonomy} onChange={v => set('autonomy', v)} />
              </SettingRow>
              <SettingRow title="Modo dry-run" desc="Mercado sintético, zero conexão real com a exchange">
                <div style={{ display: 'flex', justifyContent: 'flex-end' }}><Toggle on={s.dryRun} onChange={v => set('dryRun', v)} /></div>
              </SettingRow>
              <SettingRow title="Intervalo do loop" desc="Frequência do ciclo do orquestrador (validado 10–3600s)">
                <NumField value={s.interval} onChange={v => set('interval', v)} step={10} min={10} max={3600} suffix="s" />
              </SettingRow>
              <SettingRow title="Exchange" desc="Usada apenas quando dry-run está desligado">
                <div className="input-wrap"><select className="input" value={s.exchange} onChange={e => set('exchange', e.target.value)} style={{ fontFamily: 'var(--sans)' }}><option value="binance">Binance</option><option value="bybit">Bybit</option><option value="kraken">Kraken</option></select></div>
              </SettingRow>
              <SettingRow title="Capital inicial" desc="Capital base que dimensiona quantidade e métricas">
                <NumField value={s.initialCapital} onChange={v => set('initialCapital', v)} step={1000} min={100} suffix="$" />
              </SettingRow>
            </>}

            {sec === 'risk' && <>
              <SettingRow title="Fração Kelly" desc="Quanto do Kelly completo aplicar (padrão 0.25×)">
                <NumField value={s.kellyFraction} onChange={v => set('kellyFraction', v)} step={0.05} min={0.05} max={1} suffix="×" decimals={2} />
              </SettingRow>
              <SettingRow title="Tamanho mínimo de posição" desc="Piso por posição (padrão 0.5%)">
                <NumField value={s.minPos} onChange={v => set('minPos', v)} step={0.1} min={0.1} max={5} suffix="%" decimals={1} />
              </SettingRow>
              <SettingRow title="Tamanho máximo de posição" desc="Teto do guardrail (padrão 5%)">
                <NumField value={s.maxPos} onChange={v => set('maxPos', v)} step={0.5} min={1} max={20} suffix="%" decimals={1} />
              </SettingRow>
              <SettingRow title="Drawdown diário" desc="Pausa o trading pelo dia">
                <NumField value={s.ddDaily} onChange={v => set('ddDaily', v)} step={0.5} min={1} max={10} suffix="%" decimals={1} />
              </SettingRow>
              <SettingRow title="Drawdown semanal" desc="Reduz posições à metade">
                <NumField value={s.ddWeekly} onChange={v => set('ddWeekly', v)} step={0.5} min={2} max={20} suffix="%" decimals={1} />
              </SettingRow>
              <SettingRow title="Drawdown mensal" desc="Suspende e exige revisão">
                <NumField value={s.ddMonthly} onChange={v => set('ddMonthly', v)} step={1} min={5} max={40} suffix="%" />
              </SettingRow>
            </>}

            {sec === 'strategies' && <>
              <div style={{ fontSize: 12.5, color: 'var(--ink-2)', padding: '12px 0', display: 'flex', gap: 8, alignItems: 'center' }}>
                <Icon name="info" size={15} style={{ color: 'var(--ink-3)' }} />Parâmetros detalhados por estratégia ficam em <b style={{ marginLeft: 2 }}>Agentes & Estratégias</b>. Aqui ficam os defaults por regime.
              </div>
              <SettingRow title="Grid — ativo em" desc="Regime que ativa o Grid Trading"><Badge kind="info">lateral</Badge></SettingRow>
              <SettingRow title="DCA — ativo em" desc="Regimes que ativam o DCA otimizado"><div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end' }}><Badge kind="info">lateral</Badge><Badge kind="info">alta forte</Badge></div></SettingRow>
              <SettingRow title="Mean Reversion" desc="Reversão à média sob demanda"><Badge kind="neutral">manual</Badge></SettingRow>
              <SettingRow title="Bloquear em regime caótico" desc="Sem trading em volatilidade extrema"><div style={{ display: 'flex', justifyContent: 'flex-end' }}><Toggle on={true} onChange={() => {}} /></div></SettingRow>
            </>}

            {sec === 'journal' && <>
              <SettingRow title="Escala emocional" desc="Amplitude da escala de estado emocional">
                <Seg options={[{ value: 5, label: '1–5' }, { value: 10, label: '1–10' }]} value={s.emotionScale} onChange={v => set('emotionScale', v)} />
              </SettingRow>
              <SettingRow title="Campos personalizados" desc="Permite adicionar campos próprios ao registro">
                <div style={{ display: 'flex', justifyContent: 'flex-end' }}><Toggle on={s.customFields} onChange={v => set('customFields', v)} /></div>
              </SettingRow>
              <SettingRow title="Exigir nota de plano" desc="Texto livre obrigatório sobre seguir/desviar do plano">
                <div style={{ display: 'flex', justifyContent: 'flex-end' }}><Toggle on={s.requireStopNote} onChange={v => set('requireStopNote', v)} /></div>
              </SettingRow>
              <SettingRow title="Campos do registro" desc="Setup · emoção antes/depois · stop definido · plano seguido · P&L">
                <div style={{ textAlign: 'right' }}><span className="chip">5 campos padrão</span></div>
              </SettingRow>
            </>}

            {sec === 'backtest' && <>
              <SettingRow title="Capital inicial" desc="Capital base da simulação">
                <NumField value={s.initialCapital} onChange={v => set('initialCapital', v)} step={1000} min={100} suffix="$" />
              </SettingRow>
              <SettingRow title="Comissão" desc="Custo por trade (padrão 0.1%)">
                <NumField value={s.commission} onChange={v => set('commission', v)} step={0.05} min={0} max={2} suffix="%" decimals={2} />
              </SettingRow>
              <SettingRow title="Slippage" desc="Derrapagem simulada (padrão 5 bps)">
                <NumField value={s.slippage} onChange={v => set('slippage', v)} step={1} min={0} max={50} suffix="bps" />
              </SettingRow>
              <SettingRow title="Janela walk-forward" desc="Tamanho da janela treino/teste (padrão 252 candles)">
                <NumField value={s.wfWindow} onChange={v => set('wfWindow', v)} step={1} min={30} suffix="candles" />
              </SettingRow>
              <SettingRow title="Simulações Monte Carlo" desc="Número de simulações (padrão 1.000)">
                <NumField value={s.mcSims} onChange={v => set('mcSims', v)} step={100} min={100} max={10000} />
              </SettingRow>
            </>}

            {sec === 'alerts' && <>
              <div style={{ fontSize: 12.5, color: 'var(--ink-2)', padding: '12px 0', display: 'flex', gap: 8, alignItems: 'center' }}>
                <Icon name="info" size={15} style={{ color: 'var(--ink-3)' }} />
                <span><b>PATCH /v1/alerts/config</b> é write-only — sem GET de read-back. Os campos abaixo mostram os <b>defaults</b>.</span>
                <span style={{ marginLeft: 'auto' }}><GapTag>sem GET</GapTag></span>
              </div>
              <SettingRow title="Revenge trading" desc="Alerta se tamanho ficar X% maior após 2 perdas">
                <NumField value={s.revengeSize} onChange={v => set('revengeSize', v)} step={5} min={10} max={200} suffix="%" />
              </SettingRow>
              <SettingRow title="Euforia" desc="Alerta se tamanho ficar X% maior após 3 vitórias">
                <NumField value={s.euphoriaSize} onChange={v => set('euphoriaSize', v)} step={5} min={5} max={100} suffix="%" />
              </SettingRow>
              <SettingRow title="Overconfidence" desc="Alerta se confiança exceder o win rate real em X pontos">
                <NumField value={s.overconfGap} onChange={v => set('overconfGap', v)} step={1} min={5} max={50} suffix="pts" />
              </SettingRow>
              <SettingRow title="Risco de ruína" desc="Alerta crítico se probabilidade ultrapassar o limite">
                <NumField value={s.riskOfRuin} onChange={v => set('riskOfRuin', v)} step={0.5} min={1} max={20} suffix="%" decimals={1} />
              </SettingRow>
            </>}

          </div>
        </div>
      </div>
    </div>
  );
}

window.SettingsScreen = SettingsScreen;
