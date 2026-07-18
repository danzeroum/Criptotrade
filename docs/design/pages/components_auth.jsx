/* ============================================================
   Auth building blocks (A1): AuthLayout (centered card outside the
   shell), PasswordField, OtpInput, DemoBanner. Classic-scripts app:
   everything registers on window.*.
   ============================================================ */
const { useState } = React;

function AuthLayout({ title, sub, children }) {
  return (
    <div className="auth-wrap">
      <div className="auth-card">
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 18 }}>
          <span className="brand-mark">C</span>
          <div>
            <div style={{ fontWeight: 700, fontSize: 15 }}>Criptotrade</div>
            <div style={{ fontSize: 11, color: 'var(--ink-3)', fontFamily: 'var(--mono)' }}>Console v1</div>
          </div>
        </div>
        {title && <h1 style={{ fontSize: 18, fontWeight: 600, marginBottom: 4 }}>{title}</h1>}
        {sub && <p style={{ fontSize: 12.5, color: 'var(--ink-2)', marginBottom: 16 }}>{sub}</p>}
        {children}
      </div>
    </div>
  );
}
window.AuthLayout = AuthLayout;

function PasswordField({ label = 'Senha', value, onChange, autoComplete = 'current-password' }) {
  const [show, setShow] = useState(false);
  return (
    <label className="auth-field">
      <span className="label-xs">{label}</span>
      <div style={{ position: 'relative' }}>
        <input
          type={show ? 'text' : 'password'} value={value} autoComplete={autoComplete}
          onChange={e => onChange(e.target.value)} className="auth-input"
        />
        <button type="button" className="auth-eye" aria-label={show ? 'Ocultar senha' : 'Mostrar senha'}
          onClick={() => setShow(s => !s)}>
          <Icon name="eye" size={14} />
        </button>
      </div>
    </label>
  );
}
window.PasswordField = PasswordField;

function OtpInput({ value, onChange, placeholder = '000000' }) {
  return (
    <input
      className="auth-input" style={{ fontFamily: 'var(--mono)', letterSpacing: 4, textAlign: 'center' }}
      inputMode="numeric" autoComplete="one-time-code" maxLength={10}
      placeholder={placeholder} value={value}
      onChange={e => onChange(e.target.value.replace(/[^0-9a-z-]/gi, ''))}
    />
  );
}
window.OtpInput = OtpInput;

function DemoBanner() {
  return (
    <div className="demo-banner" role="status">
      <Icon name="info" size={13} />
      Ambiente de demonstração — somente leitura. As ações ficam desabilitadas; no produto real elas operam de verdade.
    </div>
  );
}
window.DemoBanner = DemoBanner;
