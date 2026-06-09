/* ============================================================
   Criptotrade — Design Tweaks Panel (local state only)
   ============================================================ */
const { useState } = React;

function TweaksPanel({ onClose }) {
  const [accent, setAccent] = useState('default');
  const [density, setDensity] = useState('normal');
  const [colorMode, setColorMode] = useState('green');

  const applyAccent = (v) => {
    setAccent(v);
    const map = {
      default: '#14181C',
      blue:    '#2563EB',
      violet:  '#7C5CFC',
    };
    document.documentElement.style.setProperty('--accent', map[v] ?? map.default);
    document.documentElement.style.setProperty('--accent-ink', '#FFFFFF');
  };

  const applyDensity = (v) => {
    setDensity(v);
    const app = document.querySelector('.app');
    if (app) app.dataset.density = v === 'normal' ? '' : v;
  };

  const applyColorMode = (v) => {
    setColorMode(v);
    if (v === 'inverted') {
      document.documentElement.style.setProperty('--up',      '#2563EB');
      document.documentElement.style.setProperty('--up-bg',   '#E7EEFD');
      document.documentElement.style.setProperty('--up-line', '#C9D8FA');
      document.documentElement.style.setProperty('--down',    '#0E9D6E');
      document.documentElement.style.setProperty('--down-bg', '#E7F6EF');
      document.documentElement.style.setProperty('--down-line','#B7E6D2');
    } else {
      document.documentElement.style.setProperty('--up',      '#0E9D6E');
      document.documentElement.style.setProperty('--up-bg',   '#E7F6EF');
      document.documentElement.style.setProperty('--up-line', '#B7E6D2');
      document.documentElement.style.setProperty('--down',    '#DC2B2B');
      document.documentElement.style.setProperty('--down-bg', '#FCEAEA');
      document.documentElement.style.setProperty('--down-line','#F3C9C9');
    }
  };

  return (
    <>
      <div className="drawer-scrim" onClick={onClose} />
      <div className="drawer" style={{ width: 320, maxWidth: '92vw' }}>
        <div className="card-head">
          <span className="card-title"><Icon name="settings" />Design Tweaks</span>
          <Btn variant="ghost" size="sm" onClick={onClose}>
            <Icon name="x" size={14} />
          </Btn>
        </div>
        <div style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 24 }}>
          <div>
            <div className="label-xs" style={{ marginBottom: 10 }}>Cor de acento</div>
            <Seg
              options={[
                { value: 'default', label: 'Preto' },
                { value: 'blue',    label: 'Azul' },
                { value: 'violet',  label: 'Violeta' },
              ]}
              value={accent}
              onChange={applyAccent}
            />
          </div>
          <div>
            <div className="label-xs" style={{ marginBottom: 10 }}>Densidade</div>
            <Seg
              options={[
                { value: 'normal',  label: 'Normal' },
                { value: 'compact', label: 'Compacto' },
              ]}
              value={density}
              onChange={applyDensity}
            />
          </div>
          <div>
            <div className="label-xs" style={{ marginBottom: 10 }}>Cores compra/venda</div>
            <Seg
              options={[
                { value: 'green',    label: 'Verde/Verm' },
                { value: 'inverted', label: 'Azul/Verde' },
              ]}
              value={colorMode}
              onChange={applyColorMode}
            />
          </div>
          <div style={{ paddingTop: 12, borderTop: '1px solid var(--border)' }}>
            <div style={{ fontSize: 12, color: 'var(--ink-3)', lineHeight: 1.5 }}>
              Tweaks são puramente visuais e não afetam dados ou configurações do sistema.
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
window.TweaksPanel = TweaksPanel;
