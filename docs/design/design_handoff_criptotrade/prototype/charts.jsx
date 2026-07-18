/* ============================================================
   Criptotrade — chart primitives (SVG / React)
   Exports to window: Sparkline, CandleChart, EquityChart,
   KellyCurve, Gauge, DonutProgress, MACDBars, BarChart,
   Scatter, Heatmap, MonteCarloHist, MiniBars
   ============================================================ */
const { useMemo: _useMemo } = React;

function _scale(v, dMin, dMax, rMin, rMax) {
  if (dMax === dMin) return (rMin + rMax) / 2;
  return rMin + (v - dMin) / (dMax - dMin) * (rMax - rMin);
}

/* ---------- Sparkline ---------- */
function Sparkline({ data, w = 120, h = 32, color = 'var(--ink)', fill = false, strokeW = 1.6 }) {
  const min = Math.min(...data), max = Math.max(...data);
  const pts = data.map((v, i) => [
    _scale(i, 0, data.length - 1, 2, w - 2),
    _scale(v, min, max, h - 3, 3),
  ]);
  const d = pts.map((p, i) => (i ? 'L' : 'M') + p[0].toFixed(1) + ' ' + p[1].toFixed(1)).join(' ');
  const area = d + ` L ${w - 2} ${h} L 2 ${h} Z`;
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} style={{ display: 'block' }}>
      {fill && <path d={area} fill={color} opacity="0.1" />}
      <path d={d} fill="none" stroke={color} strokeWidth={strokeW} strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

/* ---------- Candle chart with overlays ---------- */
function CandleChart({ candles, bb, sr, fib, overlays = {}, height = 360 }) {
  const W = 920, H = height, padR = 64, padL = 8, padT = 14, padB = 22;
  const plotW = W - padR - padL, plotH = H - padT - padB;
  const lows = candles.map(c => c.low), highs = candles.map(c => c.high);
  let yMin = Math.min(...lows), yMax = Math.max(...highs);
  if (sr) { sr.support.concat(sr.resistance).forEach(s => { yMin = Math.min(yMin, s.price); yMax = Math.max(yMax, s.price); }); }
  const pad = (yMax - yMin) * 0.04; yMin -= pad; yMax += pad;
  const x = i => padL + _scale(i, 0, candles.length - 1, 6, plotW - 6);
  const y = v => padT + _scale(v, yMax, yMin, 0, plotH);
  const cw = Math.max(3, plotW / candles.length * 0.62);

  const last = candles[candles.length - 1];
  const gridLines = 5;
  const yTicks = Array.from({ length: gridLines }, (_, i) => yMin + (yMax - yMin) * i / (gridLines - 1));

  const bbUp = bb.filter(b => b.up != null);
  const bandPath = bbUp.map((b, i) => (i ? 'L' : 'M') + x(b.i) + ' ' + y(b.up)).join(' ')
    + ' ' + bbUp.slice().reverse().map(b => 'L' + x(b.i) + ' ' + y(b.low)).join(' ') + ' Z';
  const midPath = bbUp.map((b, i) => (i ? 'L' : 'M') + x(b.i) + ' ' + y(b.mid)).join(' ');

  return (
    <svg width="100%" viewBox={`0 0 ${W} ${H}`} style={{ display: 'block' }} preserveAspectRatio="xMidYMid meet">
      {/* grid */}
      {yTicks.map((t, i) => (
        <g key={i}>
          <line x1={padL} x2={W - padR} y1={y(t)} y2={y(t)} stroke="var(--border)" strokeWidth="1" />
          <text x={W - padR + 6} y={y(t) + 3.5} fontSize="10.5" fill="var(--ink-3)" fontFamily="var(--mono)">
            {Math.round(t).toLocaleString()}
          </text>
        </g>
      ))}

      {/* bollinger band */}
      {overlays.bb !== false && <>
        <path d={bandPath} fill="var(--info)" opacity="0.07" />
        <path d={midPath} fill="none" stroke="var(--info)" strokeWidth="1.1" strokeDasharray="3 3" opacity="0.6" />
      </>}

      {/* fib levels */}
      {overlays.fib && fib && fib.map((f, i) => (
        <g key={'f' + i}>
          <line x1={padL} x2={W - padR} y1={y(f.price)} y2={y(f.price)} stroke="var(--violet)" strokeWidth="0.8" opacity="0.4" strokeDasharray="2 4" />
          <text x={padL + 3} y={y(f.price) - 3} fontSize="9" fill="var(--violet)" fontFamily="var(--mono)" opacity="0.85">{f.level}%</text>
        </g>
      ))}

      {/* support / resistance zones */}
      {overlays.sr !== false && sr && <>
        {sr.resistance.map((s, i) => (
          <g key={'r' + i}>
            <line x1={padL} x2={W - padR} y1={y(s.price)} y2={y(s.price)} stroke="var(--down)" strokeWidth="1.3" opacity="0.55" />
            <rect x={W - padR} y={y(s.price) - 8} width={padR} height={16} fill="var(--down)" opacity="0.08" />
            <text x={padL + 4} y={y(s.price) - 4} fontSize="9.5" fill="var(--down)" fontWeight="600">R · força {s.strength}</text>
          </g>
        ))}
        {sr.support.map((s, i) => (
          <g key={'s' + i}>
            <line x1={padL} x2={W - padR} y1={y(s.price)} y2={y(s.price)} stroke="var(--up)" strokeWidth="1.3" opacity="0.55" />
            <text x={padL + 4} y={y(s.price) - 4} fontSize="9.5" fill="var(--up)" fontWeight="600">S · força {s.strength}</text>
          </g>
        ))}
      </>}

      {/* grid trading levels */}
      {overlays.grid && Array.from({ length: 10 }, (_, i) => {
        const gp = last.close - 760 + (1680 / 9) * i;
        return <line key={'g' + i} x1={padL} x2={W - padR} y1={y(gp)} y2={y(gp)} stroke="var(--ink-3)" strokeWidth="0.6" strokeDasharray="1 6" opacity="0.45" />;
      })}

      {/* candles */}
      {candles.map((c, i) => {
        const up = c.close >= c.open;
        const col = up ? 'var(--up)' : 'var(--down)';
        const bx = x(i);
        const oy = y(c.open), cy = y(c.close);
        return (
          <g key={i}>
            <line x1={bx} x2={bx} y1={y(c.high)} y2={y(c.low)} stroke={col} strokeWidth="1" />
            <rect x={bx - cw / 2} y={Math.min(oy, cy)} width={cw} height={Math.max(1.2, Math.abs(cy - oy))} fill={col} rx="0.5" />
          </g>
        );
      })}

      {/* last price line */}
      <line x1={padL} x2={W - padR} y1={y(last.close)} y2={y(last.close)} stroke="var(--ink)" strokeWidth="0.8" strokeDasharray="4 3" opacity="0.5" />
      <rect x={W - padR} y={y(last.close) - 9} width={padR} height={18} fill="var(--ink)" rx="3" />
      <text x={W - padR + padR / 2} y={y(last.close) + 4} fontSize="10.5" fill="#fff" fontFamily="var(--mono)" fontWeight="600" textAnchor="middle">{Math.round(last.close).toLocaleString()}</text>
    </svg>
  );
}

/* ---------- Equity / drawdown chart ---------- */
function EquityChart({ data, height = 200, showDrawdown = true, color = 'var(--ink)' }) {
  const W = 760, H = height, padR = 52, padL = 6, padT = 10, padB = 18;
  const plotW = W - padR - padL, plotH = H - padT - padB;
  const eq = data.map(d => d.equity);
  const yMin = Math.min(...eq) * 0.998, yMax = Math.max(...eq) * 1.002;
  const x = i => padL + _scale(i, 0, data.length - 1, 0, plotW);
  const y = v => padT + _scale(v, yMax, yMin, 0, plotH);
  const line = data.map((d, i) => (i ? 'L' : 'M') + x(i).toFixed(1) + ' ' + y(d.equity).toFixed(1)).join(' ');
  const area = line + ` L ${x(data.length - 1)} ${padT + plotH} L ${x(0)} ${padT + plotH} Z`;
  const ddMin = Math.min(...data.map(d => d.dd));
  const ddH = 38;
  const yd = v => (H - padB) - _scale(v, ddMin, 0, 0, ddH);
  const yTicks = Array.from({ length: 4 }, (_, i) => yMin + (yMax - yMin) * i / 3);
  return (
    <svg width="100%" viewBox={`0 0 ${W} ${H}`} style={{ display: 'block' }} preserveAspectRatio="xMidYMid meet">
      <defs>
        <linearGradient id="eqg" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor={color} stopOpacity="0.16" />
          <stop offset="1" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      {yTicks.map((t, i) => (
        <g key={i}>
          <line x1={padL} x2={W - padR} y1={y(t)} y2={y(t)} stroke="var(--border)" strokeWidth="1" />
          <text x={W - padR + 5} y={y(t) + 3.5} fontSize="10" fill="var(--ink-3)" fontFamily="var(--mono)">${(t / 1000).toFixed(1)}k</text>
        </g>
      ))}
      <path d={area} fill="url(#eqg)" />
      <path d={line} fill="none" stroke={color} strokeWidth="1.8" strokeLinejoin="round" />
      {showDrawdown && data.map((d, i) => (
        <line key={i} x1={x(i)} x2={x(i)} y1={H - padB} y2={yd(d.dd)} stroke="var(--down)" strokeWidth={plotW / data.length * 0.7} opacity="0.18" />
      ))}
    </svg>
  );
}

/* ---------- Kelly growth curve ---------- */
function KellyCurve({ fullKelly, fraction, height = 150 }) {
  const W = 360, H = height, padL = 10, padR = 10, padT = 14, padB = 22;
  const plotW = W - padL - padR, plotH = H - padT - padB;
  const g = f => { const edge = 0.586 * Math.log(1 + f * 1.75) + 0.414 * Math.log(1 - f * 1.0); return isFinite(edge) ? edge : -1; };
  const xs = Array.from({ length: 60 }, (_, i) => i / 59 * 0.6);
  const gv = xs.map(g);
  const gMax = Math.max(...gv), gMin = Math.min(...gv.filter(isFinite), -0.05);
  const x = f => padL + _scale(f, 0, 0.6, 0, plotW);
  const y = v => padT + _scale(v, gMax, gMin, 0, plotH);
  const line = xs.map((f, i) => (i ? 'L' : 'M') + x(f).toFixed(1) + ' ' + y(gv[i]).toFixed(1)).join(' ');
  return (
    <svg width="100%" viewBox={`0 0 ${W} ${H}`} style={{ display: 'block' }} preserveAspectRatio="xMidYMid meet">
      <line x1={padL} x2={W - padR} y1={y(0)} y2={y(0)} stroke="var(--border-2)" strokeWidth="1" />
      <path d={line} fill="none" stroke="var(--ink)" strokeWidth="1.8" />
      {/* full kelly marker */}
      <line x1={x(fullKelly)} x2={x(fullKelly)} y1={padT} y2={H - padB} stroke="var(--warn)" strokeWidth="1.2" strokeDasharray="3 3" />
      <text x={x(fullKelly)} y={padT - 3} fontSize="9.5" fill="var(--warn)" textAnchor="middle" fontWeight="600">f*</text>
      {/* fractional marker */}
      <line x1={x(fraction)} x2={x(fraction)} y1={padT} y2={H - padB} stroke="var(--up)" strokeWidth="1.4" />
      <circle cx={x(fraction)} cy={y(g(fraction))} r="3.5" fill="var(--up)" stroke="#fff" strokeWidth="1.5" />
      <text x={x(fraction)} y={H - padB + 13} fontSize="9.5" fill="var(--up)" textAnchor="middle" fontWeight="600">usado</text>
      <text x={padL} y={H - 4} fontSize="9" fill="var(--ink-3)" fontFamily="var(--mono)">0%</text>
      <text x={W - padR} y={H - 4} fontSize="9" fill="var(--ink-3)" fontFamily="var(--mono)" textAnchor="end">60%</text>
    </svg>
  );
}

/* ---------- Semicircle gauge (RSI / Stoch) ---------- */
function Gauge({ value, min = 0, max = 100, zones = [], label, size = 132 }) {
  const W = size, H = size * 0.62, cx = W / 2, cy = H, r = W / 2 - 8;
  const a = v => Math.PI - (v - min) / (max - min) * Math.PI;
  const pt = (v, rr) => [cx + rr * Math.cos(a(v)), cy - rr * Math.sin(a(v))];
  const arc = (v0, v1, rr) => {
    const [x0, y0] = pt(v0, rr), [x1, y1] = pt(v1, rr);
    const large = (a(v0) - a(v1)) > Math.PI ? 1 : 0;
    return `M ${x0} ${y0} A ${rr} ${rr} 0 ${large} 1 ${x1} ${y1}`;
  };
  const [nx, ny] = pt(value, r - 2);
  return (
    <svg width={W} height={H + 22} viewBox={`0 0 ${W} ${H + 22}`} style={{ display: 'block' }}>
      <path d={arc(min, max, r)} fill="none" stroke="var(--surface-3)" strokeWidth="9" strokeLinecap="round" />
      {zones.map((z, i) => (
        <path key={i} d={arc(z.from, z.to, r)} fill="none" stroke={z.color} strokeWidth="9" opacity="0.75" />
      ))}
      <line x1={cx} y1={cy} x2={nx} y2={ny} stroke="var(--ink)" strokeWidth="2.4" strokeLinecap="round" />
      <circle cx={cx} cy={cy} r="4" fill="var(--ink)" />
      <text x={cx} y={cy - 14} fontSize="22" fontFamily="var(--mono)" fontWeight="500" textAnchor="middle" fill="var(--ink)">{value.toFixed(1)}</text>
      {label && <text x={cx} y={H + 16} fontSize="11" textAnchor="middle" fill="var(--ink-3)">{label}</text>}
    </svg>
  );
}

/* ---------- Donut progress (confidence, risk of ruin) ---------- */
function DonutProgress({ value, size = 120, stroke = 11, color = 'var(--ink)', label, sub, track = 'var(--surface-3)' }) {
  const r = (size - stroke) / 2, c = 2 * Math.PI * r;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{ display: 'block' }}>
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={track} strokeWidth={stroke} />
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth={stroke}
        strokeDasharray={`${c * value} ${c}`} strokeLinecap="round"
        transform={`rotate(-90 ${size / 2} ${size / 2})`} style={{ transition: 'stroke-dasharray .5s ease' }} />
      <text x="50%" y="48%" fontSize={size * 0.24} fontFamily="var(--mono)" fontWeight="500" textAnchor="middle" dominantBaseline="middle" fill="var(--ink)">{label}</text>
      {sub && <text x="50%" y="64%" fontSize={size * 0.1} textAnchor="middle" fill="var(--ink-3)">{sub}</text>}
    </svg>
  );
}

/* ---------- MACD histogram ---------- */
function MACDBars({ data, height = 56 }) {
  const W = 220, H = height; const max = Math.max(...data.map(Math.abs));
  const bw = W / data.length * 0.7; const zero = H / 2;
  return (
    <svg width="100%" viewBox={`0 0 ${W} ${H}`} style={{ display: 'block' }} preserveAspectRatio="none">
      <line x1="0" x2={W} y1={zero} y2={zero} stroke="var(--border-2)" strokeWidth="1" />
      {data.map((v, i) => {
        const h = Math.abs(v) / max * (H / 2 - 2);
        const xx = _scale(i, 0, data.length - 1, bw, W - bw);
        return <rect key={i} x={xx - bw / 2} y={v >= 0 ? zero - h : zero} width={bw} height={h} fill={v >= 0 ? 'var(--up)' : 'var(--down)'} rx="0.5" />;
      })}
    </svg>
  );
}

/* ---------- mini volume bars ---------- */
function MiniBars({ data, height = 40, color = 'var(--ink-3)' }) {
  const W = 220, H = height; const max = Math.max(...data); const bw = W / data.length * 0.66;
  return (
    <svg width="100%" viewBox={`0 0 ${W} ${H}`} style={{ display: 'block' }} preserveAspectRatio="none">
      {data.map((v, i) => {
        const h = v / max * (H - 2); const xx = _scale(i, 0, data.length - 1, bw, W - bw);
        return <rect key={i} x={xx - bw / 2} y={H - h} width={bw} height={h} fill={color} opacity="0.55" rx="0.5" />;
      })}
    </svg>
  );
}

/* ---------- generic vertical bar chart ---------- */
function BarChart({ data, height = 160, fmt = v => v, max: maxOverride }) {
  const W = 320, H = height, padB = 30, padT = 16;
  const max = maxOverride != null ? maxOverride : Math.max(...data.map(d => d.value));
  const bw = (W - 20) / data.length * 0.5;
  const x = i => 16 + _scale(i, 0, data.length - 1 || 1, bw, W - 16 - bw);
  return (
    <svg width="100%" viewBox={`0 0 ${W} ${H}`} style={{ display: 'block' }} preserveAspectRatio="xMidYMid meet">
      {data.map((d, i) => {
        const h = (d.value / max) * (H - padB - padT);
        return (
          <g key={i}>
            <rect x={x(i) - bw / 2} y={H - padB - h} width={bw} height={h} fill={d.color || 'var(--ink)'} rx="3" />
            <text x={x(i)} y={H - padB - h - 5} fontSize="11" fontFamily="var(--mono)" fontWeight="600" textAnchor="middle" fill="var(--ink)">{fmt(d.value)}</text>
            <text x={x(i)} y={H - padB + 14} fontSize="10.5" textAnchor="middle" fill="var(--ink-3)">{d.label}</text>
            {d.label2 && <text x={x(i)} y={H - padB + 26} fontSize="9.5" textAnchor="middle" fill="var(--ink-4)" fontFamily="var(--mono)">{d.label2}</text>}
          </g>
        );
      })}
    </svg>
  );
}

/* ---------- Scatter (emotion x pnl) ---------- */
function Scatter({ data, height = 200, xLabel, yLabel }) {
  const W = 360, H = height, padL = 34, padR = 12, padT = 12, padB = 28;
  const plotW = W - padL - padR, plotH = H - padT - padB;
  const x = v => padL + _scale(v, 1, 10, 0, plotW);
  const ys = data.map(d => d.y); const yMin = Math.min(...ys, -1), yMax = Math.max(...ys, 1);
  const y = v => padT + _scale(v, yMax, yMin, 0, plotH);
  return (
    <svg width="100%" viewBox={`0 0 ${W} ${H}`} style={{ display: 'block' }} preserveAspectRatio="xMidYMid meet">
      <line x1={padL} x2={W - padR} y1={y(0)} y2={y(0)} stroke="var(--border-2)" strokeWidth="1" />
      <line x1={padL} x2={padL} y1={padT} y2={H - padB} stroke="var(--border)" strokeWidth="1" />
      {[2, 4, 6, 8, 10].map(t => (
        <text key={t} x={x(t)} y={H - padB + 14} fontSize="9.5" textAnchor="middle" fill="var(--ink-3)" fontFamily="var(--mono)">{t}</text>
      ))}
      {data.map((d, i) => (
        <circle key={i} cx={x(d.x)} cy={y(d.y)} r="4.5" fill={d.y >= 0 ? 'var(--up)' : 'var(--down)'} opacity={d.followed ? 0.85 : 0.4} stroke={d.followed ? 'none' : (d.y >= 0 ? 'var(--up)' : 'var(--down)')} strokeWidth="1" />
      ))}
      {xLabel && <text x={padL + plotW / 2} y={H - 2} fontSize="9.5" textAnchor="middle" fill="var(--ink-4)">{xLabel}</text>}
      {yLabel && <text x={9} y={padT + plotH / 2} fontSize="9.5" textAnchor="middle" fill="var(--ink-4)" transform={`rotate(-90 9 ${padT + plotH / 2})`}>{yLabel}</text>}
    </svg>
  );
}

/* ---------- Heatmap (day x hour) ---------- */
function Heatmap({ days, data, height = 200 }) {
  const hours = [...new Set(data.map(d => d.hour))].sort((a, b) => a - b);
  const cw = 100 / hours.length, ch = 100 / days.length;
  const col = v => {
    // white -> ink, with green/red tint based on >0.5
    const t = v;
    const r0 = 14, g0 = 157, b0 = 110; // green
    const r1 = 220, g1 = 43, b1 = 43; // red
    if (t >= 0.5) { const k = (t - 0.5) * 2; return `rgba(${r0},${g0},${b0},${0.12 + k * 0.78})`; }
    const k = (0.5 - t) * 2; return `rgba(${r1},${g1},${b1},${0.10 + k * 0.55})`;
  };
  return (
    <svg width="100%" viewBox="0 0 320 180" style={{ display: 'block' }} preserveAspectRatio="xMidYMid meet">
      <g transform="translate(34, 6)">
        {data.map((d, i) => {
          const dayIdx = days.indexOf(d.dayLabel); const hi = hours.indexOf(d.hour);
          return <rect key={i} x={hi * (276 / hours.length)} y={dayIdx * (150 / days.length)} width={276 / hours.length - 1.5} height={150 / days.length - 1.5} fill={col(d.winRate)} rx="1.5" />;
        })}
        {days.map((d, i) => (
          <text key={d} x={-6} y={i * (150 / days.length) + (150 / days.length) / 2 + 3} fontSize="9" textAnchor="end" fill="var(--ink-3)">{d}</text>
        ))}
        {hours.filter((_, i) => i % 2 === 0).map((h) => {
          const hi = hours.indexOf(h);
          return <text key={h} x={hi * (276 / hours.length) + (276 / hours.length) / 2} y={163} fontSize="8" textAnchor="middle" fill="var(--ink-4)" fontFamily="var(--mono)">{h}h</text>;
        })}
      </g>
    </svg>
  );
}

/* ---------- Monte Carlo distribution histogram ---------- */
function MonteCarloHist({ mc, height = 180 }) {
  const { hist, lo, hi, p5, p50, p95 } = mc;
  const W = 720, H = height, padL = 8, padR = 8, padT = 12, padB = 26;
  const plotW = W - padL - padR, plotH = H - padT - padB;
  const max = Math.max(...hist); const bw = plotW / hist.length;
  const xv = v => padL + _scale(v, lo, hi, 0, plotW);
  const zeroX = xv(0);
  return (
    <svg width="100%" viewBox={`0 0 ${W} ${H}`} style={{ display: 'block' }} preserveAspectRatio="xMidYMid meet">
      {hist.map((v, i) => {
        const h = v / max * plotH; const bx = padL + i * bw;
        const center = lo + (hi - lo) * (i + 0.5) / hist.length;
        return <rect key={i} x={bx + 0.6} y={padT + plotH - h} width={bw - 1.2} height={h} fill={center < 0 ? 'var(--down)' : 'var(--up)'} opacity="0.4" rx="1" />;
      })}
      {/* zero line */}
      <line x1={zeroX} x2={zeroX} y1={padT} y2={padT + plotH} stroke="var(--ink)" strokeWidth="1.2" strokeDasharray="3 2" />
      <text x={zeroX} y={padT + plotH + 16} fontSize="9.5" textAnchor="middle" fill="var(--ink)" fontFamily="var(--mono)" fontWeight="600">0</text>
      {/* percentile markers */}
      {[['p5', p5, 'var(--down)'], ['p50', p50, 'var(--ink-2)'], ['p95', p95, 'var(--up)']].map(([k, v, c]) => (
        <g key={k}>
          <line x1={xv(v)} x2={xv(v)} y1={padT - 4} y2={padT + plotH} stroke={c} strokeWidth="1.4" />
          <text x={xv(v)} y={padT - 6} fontSize="9.5" textAnchor="middle" fill={c} fontWeight="600">{k}</text>
        </g>
      ))}
    </svg>
  );
}

Object.assign(window, {
  Sparkline, CandleChart, EquityChart, KellyCurve, Gauge,
  DonutProgress, MACDBars, MiniBars, BarChart, Scatter, Heatmap, MonteCarloHist,
});
