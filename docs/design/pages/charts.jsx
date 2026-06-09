/* ============================================================
   Criptotrade — SVG Chart components
   CandleChart, EquityChart, KellyCurve, Gauge, Donut,
   MACDChart, BarChart, ScatterChart, Heatmap, MonteCarloChart
   ============================================================ */

const { useMemo } = React;

// ---- helpers ----
function _range(arr) {
  if (!arr || arr.length === 0) return { min: 0, max: 1 };
  return { min: Math.min(...arr), max: Math.max(...arr) };
}
function _scale(v, min, max, lo, hi) {
  if (max === min) return (lo + hi) / 2;
  return lo + ((v - min) / (max - min)) * (hi - lo);
}
function _fmt(n) {
  if (n === null || n === undefined) return '–';
  if (Math.abs(n) >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return n.toFixed(2);
}

// ---- CandleChart (OHLCV + optional Bollinger) ----
function CandleChart({ candles = [], bb = [], width = 680, height = 260 }) {
  const PAD = { t: 12, r: 16, b: 24, l: 54 };
  const w = width - PAD.l - PAD.r;
  const h = height - PAD.t - PAD.b;

  const visible = candles.slice(-70);
  const bbv = bb.slice(-70);

  const allPrices = visible.flatMap(c => [c.h || c.high, c.lo ?? c.l ?? c.low]);
  const bbPrices = bbv.flatMap(b => [b.up, b.low].filter(Boolean));
  const { min: pMin, max: pMax } = _range([...allPrices, ...bbPrices]);
  const pad = (pMax - pMin) * 0.05;
  const lo = pMin - pad, hi = pMax + pad;

  const cw = w / Math.max(visible.length, 1);
  const sx = (i) => PAD.l + (i + 0.5) * cw;
  const sy = (p) => PAD.t + _scale(p, hi, lo, 0, h);

  const bullColor = 'var(--up)';
  const bearColor = 'var(--down)';

  const gridYs = [0, 0.25, 0.5, 0.75, 1].map(f => lo + f * (hi - lo));

  return (
    <svg width="100%" viewBox={`0 0 ${width} ${height}`} style={{ display: 'block' }}>
      {gridYs.map((p, i) => (
        <g key={i}>
          <line x1={PAD.l} y1={sy(p)} x2={PAD.l + w} y2={sy(p)} stroke="var(--border)" strokeWidth="0.5" />
          <text x={PAD.l - 6} y={sy(p) + 4} fontSize="10" fill="var(--ink-4)" textAnchor="end">
            {Math.round(p).toLocaleString()}
          </text>
        </g>
      ))}

      {bbv.length > 1 && (
        <>
          <polyline fill="none" stroke="rgba(37,99,235,.25)" strokeWidth="1"
            points={bbv.map((b, i) => b.up ? `${sx(i)},${sy(b.up)}` : '').filter(Boolean).join(' ')} />
          <polyline fill="none" stroke="rgba(37,99,235,.25)" strokeWidth="1"
            points={bbv.map((b, i) => b.low ? `${sx(i)},${sy(b.low)}` : '').filter(Boolean).join(' ')} />
          <polyline fill="none" stroke="rgba(37,99,235,.5)" strokeWidth="1" strokeDasharray="3,2"
            points={bbv.map((b, i) => b.mid ? `${sx(i)},${sy(b.mid)}` : '').filter(Boolean).join(' ')} />
        </>
      )}

      {visible.map((c, i) => {
        const open = c.o !== undefined ? c.o : c.open;
        const close = c.c !== undefined ? c.c : c.close;
        const high = c.h !== undefined ? c.h : c.high;
        const low = c.lo !== undefined ? c.lo : c.l !== undefined ? c.l : c.low;
        const bull = close >= open;
        const color = bull ? bullColor : bearColor;
        const bodyY = sy(Math.max(open, close));
        const bodyH = Math.max(1, Math.abs(sy(open) - sy(close)));
        return (
          <g key={i}>
            <line x1={sx(i)} y1={sy(high)} x2={sx(i)} y2={sy(low)} stroke={color} strokeWidth="1" />
            <rect x={sx(i) - cw * 0.35} y={bodyY} width={cw * 0.7} height={bodyH}
              fill={color} rx="1" />
          </g>
        );
      })}
    </svg>
  );
}
window.CandleChart = CandleChart;

// ---- EquityChart (equity curve + drawdown area) ----
function EquityChart({ points = [], width = 680, height = 200 }) {
  if (!points.length) return null;
  const PAD = { t: 8, r: 16, b: 24, l: 60 };
  const w = width - PAD.l - PAD.r;
  const h = height - PAD.t - PAD.b;

  const equities = points.map(p => p.equity);
  const { min: eMin, max: eMax } = _range(equities);
  const eRange = eMax - eMin || 1;

  const sx = (i) => PAD.l + (i / Math.max(points.length - 1, 1)) * w;
  const sy = (v) => PAD.t + ((eMax - v) / eRange) * h;

  const polyPts = points.map((p, i) => `${sx(i)},${sy(p.equity)}`).join(' ');
  const areaPath = `M${sx(0)},${sy(eMin)} ` + points.map((p, i) => `${sx(i)},${sy(p.equity)}`).join(' ') + ` L${sx(points.length - 1)},${sy(eMin)} Z`;

  const labels = [eMin, (eMin + eMax) / 2, eMax].map(v =>
    `$${Math.round(v).toLocaleString()}`
  );

  return (
    <svg width="100%" viewBox={`0 0 ${width} ${height}`} style={{ display: 'block' }}>
      <defs>
        <linearGradient id="eq-grad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="var(--up)" stopOpacity="0.2" />
          <stop offset="100%" stopColor="var(--up)" stopOpacity="0" />
        </linearGradient>
      </defs>
      {[eMin, (eMin + eMax) / 2, eMax].map((v, i) => (
        <g key={i}>
          <line x1={PAD.l} y1={sy(v)} x2={PAD.l + w} y2={sy(v)} stroke="var(--border)" strokeWidth="0.5" />
          <text x={PAD.l - 4} y={sy(v) + 4} fontSize="10" fill="var(--ink-4)" textAnchor="end">{labels[i]}</text>
        </g>
      ))}
      <path d={areaPath} fill="url(#eq-grad)" />
      <polyline fill="none" stroke="var(--up)" strokeWidth="1.5" points={polyPts} />
    </svg>
  );
}
window.EquityChart = EquityChart;

// ---- Gauge (semicircle meter) ----
function Gauge({ value, min = 0, max = 100, label, unit = '', size = 120 }) {
  const pct = Math.max(0, Math.min(1, (value - min) / (max - min)));
  const angle = -180 + pct * 180;
  const r = size / 2 - 12;
  const cx = size / 2, cy = size / 2 + 8;
  const toXY = (deg) => {
    const rad = (deg * Math.PI) / 180;
    return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
  };
  const start = toXY(-180), end = toXY(angle);
  const large = angle - -180 > 180 ? 1 : 0;
  return (
    <svg width={size} height={size * 0.7} viewBox={`0 0 ${size} ${size * 0.7}`}>
      <path d={`M${toXY(-180).x},${toXY(-180).y} A${r},${r} 0 0,1 ${toXY(0).x},${toXY(0).y}`}
        fill="none" stroke="var(--surface-3)" strokeWidth="8" strokeLinecap="round" />
      <path d={`M${start.x},${start.y} A${r},${r} 0 ${large},1 ${end.x},${end.y}`}
        fill="none" stroke="var(--up)" strokeWidth="8" strokeLinecap="round" />
      <text x={cx} y={cy - 4} textAnchor="middle" fontSize="15" fontWeight="600" fill="var(--ink)"
        fontFamily="var(--mono)">{value}{unit}</text>
      {label && <text x={cx} y={cy + 10} textAnchor="middle" fontSize="10" fill="var(--ink-3)">{label}</text>}
    </svg>
  );
}
window.Gauge = Gauge;

// ---- Donut ----
function Donut({ segments = [], size = 100 }) {
  const cx = size / 2, cy = size / 2, r = size / 2 - 10;
  const total = segments.reduce((s, x) => s + (x.value || 0), 0) || 1;
  let angle = -90;
  const slices = segments.map(seg => {
    const sweep = (seg.value / total) * 360;
    const a1 = angle, a2 = angle + sweep;
    const large = sweep > 180 ? 1 : 0;
    const rad = d => (d * Math.PI) / 180;
    const x1 = cx + r * Math.cos(rad(a1)), y1 = cy + r * Math.sin(rad(a1));
    const x2 = cx + r * Math.cos(rad(a2)), y2 = cy + r * Math.sin(rad(a2));
    angle += sweep;
    return { ...seg, d: `M${cx},${cy} L${x1},${y1} A${r},${r} 0 ${large},1 ${x2},${y2} Z` };
  });
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      {slices.map((s, i) => <path key={i} d={s.d} fill={s.color || `hsl(${i * 60},65%,55%)`} />)}
      <circle cx={cx} cy={cy} r={r * 0.6} fill="var(--surface)" />
    </svg>
  );
}
window.Donut = Donut;

// ---- MACDChart ----
function MACDChart({ macdLine = [], signalLine = [], hist = [], width = 400, height = 100 }) {
  if (!hist.length) return null;
  const PAD = { t: 4, r: 8, b: 16, l: 40 };
  const w = width - PAD.l - PAD.r;
  const h = height - PAD.t - PAD.b;
  const all = [...macdLine, ...signalLine, ...hist].filter(v => v !== null);
  const { min, max } = _range(all);
  const range = max - min || 1;
  const sx = (i) => PAD.l + (i / Math.max(hist.length - 1, 1)) * w;
  const sy = (v) => PAD.t + ((max - v) / range) * h;
  const barW = w / hist.length;
  return (
    <svg width="100%" viewBox={`0 0 ${width} ${height}`} style={{ display: 'block' }}>
      <line x1={PAD.l} y1={sy(0)} x2={PAD.l + w} y2={sy(0)} stroke="var(--border)" strokeWidth="0.5" />
      {hist.map((v, i) => (
        <rect key={i} x={sx(i) - barW * 0.4} y={v >= 0 ? sy(v) : sy(0)}
          width={barW * 0.8} height={Math.abs(sy(v) - sy(0))}
          fill={v >= 0 ? 'var(--up)' : 'var(--down)'} opacity="0.7" />
      ))}
      {macdLine.length > 1 && (
        <polyline fill="none" stroke="var(--info)" strokeWidth="1.2"
          points={macdLine.map((v, i) => v !== null ? `${sx(i)},${sy(v)}` : '').filter(Boolean).join(' ')} />
      )}
      {signalLine.length > 1 && (
        <polyline fill="none" stroke="var(--warn)" strokeWidth="1.2"
          points={signalLine.map((v, i) => v !== null ? `${sx(i)},${sy(v)}` : '').filter(Boolean).join(' ')} />
      )}
    </svg>
  );
}
window.MACDChart = MACDChart;

// ---- BarChart ----
function BarChart({ data = [], labelKey = 'label', valueKey = 'value', color = 'var(--up)', width = 300, height = 160 }) {
  if (!data.length) return null;
  const PAD = { t: 8, r: 8, b: 28, l: 40 };
  const w = width - PAD.l - PAD.r;
  const h = height - PAD.t - PAD.b;
  const vals = data.map(d => d[valueKey] || 0);
  const maxV = Math.max(...vals) || 1;
  const barW = w / data.length - 4;

  return (
    <svg width="100%" viewBox={`0 0 ${width} ${height}`} style={{ display: 'block' }}>
      {data.map((d, i) => {
        const v = d[valueKey] || 0;
        const bh = (v / maxV) * h;
        const x = PAD.l + i * (w / data.length) + 2;
        return (
          <g key={i}>
            <rect x={x} y={PAD.t + h - bh} width={barW} height={bh} fill={color} rx="2" />
            <text x={x + barW / 2} y={height - 4} textAnchor="middle" fontSize="9" fill="var(--ink-4)">
              {String(d[labelKey]).substring(0, 5)}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
window.BarChart = BarChart;

// ---- ScatterChart ----
function ScatterChart({ points = [], xKey = 'x', yKey = 'y', width = 300, height = 200 }) {
  if (!points.length) return null;
  const PAD = 28;
  const xs = points.map(p => p[xKey] || 0), ys = points.map(p => p[yKey] || 0);
  const xr = _range(xs), yr = _range(ys);
  const sx = (v) => PAD + _scale(v, xr.min, xr.max, 0, width - PAD * 2);
  const sy = (v) => (height - PAD) - _scale(v, yr.min, yr.max, 0, height - PAD * 2);
  return (
    <svg width="100%" viewBox={`0 0 ${width} ${height}`} style={{ display: 'block' }}>
      <line x1={PAD} y1={height - PAD} x2={width - PAD} y2={height - PAD} stroke="var(--border)" strokeWidth="0.5" />
      <line x1={PAD} y1={PAD} x2={PAD} y2={height - PAD} stroke="var(--border)" strokeWidth="0.5" />
      {points.map((p, i) => (
        <circle key={i} cx={sx(p[xKey] || 0)} cy={sy(p[yKey] || 0)} r="4"
          fill={p.color || 'var(--info)'} opacity="0.7" />
      ))}
    </svg>
  );
}
window.ScatterChart = ScatterChart;

// ---- Heatmap (day × hour) ----
function Heatmap({ data = [], width = 360, height = 120 }) {
  if (!data.length) return null;
  const rows = [...new Set(data.map(d => d.row))].sort();
  const cols = [...new Set(data.map(d => d.col))].sort((a, b) => a - b);
  const cellW = width / (cols.length || 1);
  const cellH = height / (rows.length || 1);
  const vals = data.map(d => d.value);
  const { min: vMin, max: vMax } = _range(vals);

  const cellColor = (v) => {
    const t = vMax > vMin ? (v - vMin) / (vMax - vMin) : 0.5;
    const r = Math.round(220 - t * 80), g = Math.round(60 + t * 100), b = Math.round(60);
    return `rgb(${r},${g},${b})`;
  };

  return (
    <svg width="100%" viewBox={`0 0 ${width} ${height}`} style={{ display: 'block' }}>
      {data.map((d, i) => {
        const ci = cols.indexOf(d.col), ri = rows.indexOf(d.row);
        return (
          <rect key={i} x={ci * cellW} y={ri * cellH} width={cellW - 1} height={cellH - 1}
            fill={cellColor(d.value)} rx="2" opacity="0.85" />
        );
      })}
      {rows.map((r, i) => (
        <text key={i} x={-3} y={i * cellH + cellH / 2 + 4} fontSize="8" fill="var(--ink-4)" textAnchor="end">{r}</text>
      ))}
    </svg>
  );
}
window.Heatmap = Heatmap;

// ---- MonteCarloChart (fan + histogram) ----
function MonteCarloChart({ mc, width = 400, height = 140 }) {
  if (!mc) return null;
  const { p5, p50, p95, profitable_pct, histogram = [] } = mc;
  const PAD = { t: 8, r: 8, b: 24, l: 44 };
  const w = width - PAD.l - PAD.r;
  const h = height - PAD.t - PAD.b;

  if (!histogram.length) {
    return (
      <div style={{ fontSize: 12, color: 'var(--ink-2)', textAlign: 'center', padding: 20 }}>
        p5: {p5?.toFixed(2)}%  p50: {p50?.toFixed(2)}%  p95: {p95?.toFixed(2)}%
      </div>
    );
  }

  const maxH = Math.max(...histogram) || 1;
  const barW = w / histogram.length;

  return (
    <svg width="100%" viewBox={`0 0 ${width} ${height}`} style={{ display: 'block' }}>
      {histogram.map((v, i) => (
        <rect key={i} x={PAD.l + i * barW} y={PAD.t + h - (v / maxH) * h}
          width={barW - 1} height={(v / maxH) * h}
          fill={i < histogram.length * 0.05 ? 'var(--down)' : 'var(--up)'} opacity="0.7" rx="1" />
      ))}
      <line x1={PAD.l} y1={PAD.t + h} x2={PAD.l + w} y2={PAD.t + h} stroke="var(--border)" strokeWidth="0.5" />
    </svg>
  );
}
window.MonteCarloChart = MonteCarloChart;

// ---- KellyCurve ----
function KellyCurve({ kelly, width = 300, height = 120 }) {
  if (!kelly) return null;
  const { win_rate = 0.55, avg_win_pct = 3, avg_loss_pct = 1, fractional_kelly = 0 } = kelly;
  const PAD = { t: 8, r: 8, b: 24, l: 40 };
  const w = width - PAD.l - PAD.r, h = height - PAD.t - PAD.b;
  const pts = [];
  for (let f = 0; f <= 1; f += 0.02) {
    const b = avg_win_pct / avg_loss_pct;
    const g = (1 + b * f) ** win_rate * (1 - f) ** (1 - win_rate) - 1;
    pts.push([f, g]);
  }
  const ys = pts.map(([, y]) => y);
  const { min, max } = _range(ys);
  const range = max - min || 1;
  const sx = (f) => PAD.l + f * w;
  const sy = (v) => PAD.t + ((max - v) / range) * h;
  return (
    <svg width="100%" viewBox={`0 0 ${width} ${height}`} style={{ display: 'block' }}>
      <line x1={PAD.l} y1={sy(0)} x2={PAD.l + w} y2={sy(0)} stroke="var(--border)" strokeWidth="0.5" strokeDasharray="3,2" />
      <polyline fill="none" stroke="var(--up)" strokeWidth="1.5"
        points={pts.map(([f, v]) => `${sx(f)},${sy(v)}`).join(' ')} />
      {fractional_kelly > 0 && (
        <line x1={sx(fractional_kelly)} y1={PAD.t} x2={sx(fractional_kelly)} y2={PAD.t + h}
          stroke="var(--warn)" strokeWidth="1" strokeDasharray="3,2" />
      )}
    </svg>
  );
}
window.KellyCurve = KellyCurve;
