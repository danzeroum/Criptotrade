/* ============================================================
   A1 auth screens: Login (generic error — never reveals whether the
   e-mail exists), 2FA (TOTP or backup code), Forgot, Reset (deep link
   #reset/<token>), and the inactivity LockScreen (overlay; React state
   behind it is preserved). onAuthed(me-like) tells App to re-probe.
   ============================================================ */
const { useState: useAuthState } = React;

function LoginScreen({ onAuthed, resetToken }) {
  const [stage, setStage] = useAuthState(resetToken ? 'reset' : 'login');
  const [email, setEmail] = useAuthState('');
  const [password, setPassword] = useAuthState('');
  const [remember, setRemember] = useAuthState(false);
  const [challenge, setChallenge] = useAuthState(null);
  const [code, setCode] = useAuthState('');
  const [newPassword, setNewPassword] = useAuthState('');
  const [error, setError] = useAuthState(null);
  const [info, setInfo] = useAuthState(null);
  const [busy, setBusy] = useAuthState(false);

  const run = async (fn) => {
    setBusy(true); setError(null); setInfo(null);
    try { await fn(); } catch (e) {
      setError(e?.message ?? 'Não foi possível completar a ação.');
    } finally { setBusy(false); }
  };

  const doLogin = () => run(async () => {
    const data = await CT_API.login({ email, password, remember });
    if (data.two_factor_required) { setChallenge(data.challenge); setStage('2fa'); setCode(''); }
    else onAuthed?.();
  });

  const doVerify = () => run(async () => {
    const data = await CT_API.verify2FA({ challenge, code, remember });
    if (data.backup_code_used) {
      setInfo(`Código de backup usado — restam ${data.remaining}.`);
    }
    onAuthed?.();
  });

  const doForgot = () => run(async () => {
    const data = await CT_API.forgotPassword(email);
    setInfo(data.message ?? 'Se o e-mail existir, enviamos instruções.');
  });

  const doReset = () => run(async () => {
    await CT_API.resetPassword({ token: resetToken, new_password: newPassword });
    setInfo('Senha redefinida. Faça login.');
    setStage('login');
    window.location.hash = '';
  });

  const submit = (e) => {
    e.preventDefault();
    if (stage === 'login') doLogin();
    else if (stage === '2fa') doVerify();
    else if (stage === 'forgot') doForgot();
    else if (stage === 'reset') doReset();
  };

  const titles = {
    login: ['Entrar', 'Acesse o console de trading.'],
    '2fa': ['Verificação em duas etapas', 'Digite o código do seu autenticador ou um código de backup.'],
    forgot: ['Recuperar acesso', 'Enviaremos um link de redefinição por e-mail.'],
    reset: ['Nova senha', 'Defina a nova senha da sua conta.'],
  };

  return (
    <AuthLayout title={titles[stage][0]} sub={titles[stage][1]}>
      <form onSubmit={submit} data-testid="auth-form">
        {error && <div className="auth-error" role="alert">{error}</div>}
        {info && <div className="auth-info" role="status">{info}</div>}

        {(stage === 'login' || stage === 'forgot') && (
          <label className="auth-field">
            <span className="label-xs">E-mail</span>
            <input className="auth-input" type="email" autoComplete="email" required
              value={email} onChange={e => setEmail(e.target.value)} />
          </label>
        )}

        {stage === 'login' && (
          <>
            <PasswordField value={password} onChange={setPassword} />
            <label style={{ display: 'flex', gap: 7, alignItems: 'center', fontSize: 12.5,
              color: 'var(--ink-2)', margin: '2px 0 12px', cursor: 'pointer' }}>
              <input type="checkbox" checked={remember} onChange={e => setRemember(e.target.checked)} />
              Lembrar deste dispositivo
            </label>
          </>
        )}

        {stage === '2fa' && (
          <div className="auth-field">
            <span className="label-xs">Código</span>
            <OtpInput value={code} onChange={setCode} />
          </div>
        )}

        {stage === 'reset' && (
          <PasswordField label="Nova senha" value={newPassword}
            onChange={setNewPassword} autoComplete="new-password" />
        )}

        <Btn variant="primary" size="md" disabled={busy}
          style={{ width: '100%', justifyContent: 'center', marginTop: 4 }}>
          {busy ? '…' : titles[stage][0]}
        </Btn>
      </form>

      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 14, fontSize: 12 }}>
        {stage === 'login' && (
          <a className="auth-link" onClick={() => { setStage('forgot'); setError(null); }}>
            Esqueci a senha
          </a>
        )}
        {stage !== 'login' && (
          <a className="auth-link" onClick={() => { setStage('login'); setError(null); }}>
            ← Voltar ao login
          </a>
        )}
      </div>
    </AuthLayout>
  );
}
window.LoginScreen = LoginScreen;

/* Inactivity lock (A1): overlay ABOVE the shell — screen state survives.
   Only ever mounted for kind==='user' (never in the public demo). */
function LockScreen({ user, onUnlocked, onLogout }) {
  const [password, setPassword] = useAuthState('');
  const [error, setError] = useAuthState(null);
  const [busy, setBusy] = useAuthState(false);

  const unlock = async (e) => {
    e.preventDefault();
    setBusy(true); setError(null);
    try {
      await CT_API.login({ email: user?.email, password });
      onUnlocked?.();
    } catch (_) {
      setError('Senha incorreta.');
    } finally { setBusy(false); }
  };

  return (
    <div className="lock-overlay" role="dialog" aria-label="Sessão bloqueada">
      <div className="auth-card" style={{ maxWidth: 360 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
          <Icon name="lock" size={18} />
          <div style={{ fontWeight: 600 }}>Sessão bloqueada por inatividade</div>
        </div>
        <p style={{ fontSize: 12.5, color: 'var(--ink-2)', marginBottom: 12 }}>
          {user?.email} — digite sua senha para continuar de onde parou.
        </p>
        <form onSubmit={unlock}>
          {error && <div className="auth-error" role="alert">{error}</div>}
          <PasswordField value={password} onChange={setPassword} />
          <Btn variant="primary" size="md" disabled={busy}
            style={{ width: '100%', justifyContent: 'center' }}>
            {busy ? '…' : 'Desbloquear'}
          </Btn>
        </form>
        <a className="auth-link" style={{ display: 'block', marginTop: 12, fontSize: 12 }}
          onClick={onLogout}>Sair e voltar ao login</a>
      </div>
    </div>
  );
}
window.LockScreen = LockScreen;
