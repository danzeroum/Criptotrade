/* ============================================================
   A7 — Segurança & Sessões (self-service; só sessão autenticada).
   Sessões ativas com a atual marcada + encerrar uma/todas as
   outras; verificação em duas etapas (ativar/desativar/regenerar
   códigos de backup — sempre reconfirmando a senha); histórico de
   logins do PRÓPRIO e-mail (o servidor nunca amplia o escopo —
   a visão de todos é a Trilha de Auditoria, A4).
   Allowlist de IP: deferida nesta fase (declarada no PR).
   ============================================================ */
const { useState: useSecState, useEffect: useSecEffect, useCallback: useSecCallback } = React;

// Nota 3 da revisão: heurística simples, sem dependência nova.
function parseUA(ua) {
  if (!ua) return '—';
  const browser =
    /Edg\//.test(ua) ? 'Edge'
    : /Chrome\//.test(ua) ? 'Chrome'
    : /Firefox\//.test(ua) ? 'Firefox'
    : /Safari\//.test(ua) ? 'Safari'
    : 'Navegador';
  const os =
    /Windows/.test(ua) ? 'Windows'
    : /Mac OS X|Macintosh/.test(ua) ? 'macOS'
    : /Android/.test(ua) ? 'Android'
    : /iPhone|iPad|iOS/.test(ua) ? 'iOS'
    : /Linux/.test(ua) ? 'Linux'
    : '';
  return os ? `${browser} · ${os}` : browser;
}
window.parseUA = parseUA;

// A2: timestamps go through the central locale/timezone-aware helper.
const fmtSecTs = (ts) => window.fmtDateTime(ts);

// Password re-confirmation modal (disable 2FA / regenerate backup codes).
function PasswordConfirmModal({ title, cta, onConfirm, onClose }) {
  const [password, setPassword] = useSecState('');
  const [busy, setBusy] = useSecState(false);
  const [error, setError] = useSecState(null);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true); setError(null);
    try { await onConfirm(password); }
    catch (err) { setError(err?.message ?? 'Senha incorreta.'); setBusy(false); }
  };

  return (
    <div className="lock-overlay" role="dialog" aria-label={title} onClick={onClose}>
      <div className="auth-card" style={{ maxWidth: 380 }} onClick={e => e.stopPropagation()}>
        <h2 style={{ fontSize: 15, fontWeight: 600, marginBottom: 12 }}>{title}</h2>
        <form onSubmit={submit}>
          {error && <div className="auth-error" role="alert">{error}</div>}
          <label className="auth-field">
            <span className="label-xs">Confirme sua senha</span>
            <input className="auth-input" type="password" required autoFocus
              value={password} onChange={e => setPassword(e.target.value)} />
          </label>
          <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
            <Btn variant="primary" size="sm" disabled={busy}>{busy ? '…' : cta}</Btn>
            <Btn variant="ghost" size="sm" type="button" onClick={onClose}>Cancelar</Btn>
          </div>
        </form>
      </div>
    </div>
  );
}

// One-time display of freshly minted backup codes.
function BackupCodesModal({ codes, onClose }) {
  return (
    <div className="lock-overlay" role="dialog" aria-label="Códigos de backup" onClick={onClose}>
      <div className="auth-card" style={{ maxWidth: 420 }} onClick={e => e.stopPropagation()}>
        <h2 style={{ fontSize: 15, fontWeight: 600, marginBottom: 6 }}>Códigos de backup</h2>
        <p style={{ fontSize: 12.5, color: 'var(--ink-2)', lineHeight: 1.5, marginBottom: 12 }}>
          Guarde estes códigos em local seguro — eles aparecem <b>uma única vez</b> e
          os anteriores deixaram de funcionar.
        </p>
        <div data-testid="backup-codes" style={{
          display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6,
          fontFamily: 'var(--mono)', fontSize: 13, marginBottom: 14,
        }}>
          {codes.map(c => <span key={c}>{c}</span>)}
        </div>
        <Btn variant="primary" size="sm" onClick={onClose}>Guardei os códigos</Btn>
      </div>
    </div>
  );
}

// 2FA enable flow: secret → TOTP code → backup codes.
function Enable2FAModal({ onDone, onClose }) {
  const [setup, setSetup] = useSecState(null);
  const [code, setCode] = useSecState('');
  const [busy, setBusy] = useSecState(false);
  const [error, setError] = useSecState(null);

  useSecEffect(() => {
    CT_API.setup2FA().then(setSetup).catch(e => setError(e?.message ?? 'Falha no setup.'));
  }, []);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true); setError(null);
    try {
      const r = await CT_API.enable2FA(code);
      onDone?.(r.backup_codes ?? []);
    } catch (err) {
      setError(err?.message ?? 'Código inválido.');
      setBusy(false);
    }
  };

  return (
    <div className="lock-overlay" role="dialog" aria-label="Ativar duas etapas" onClick={onClose}>
      <div className="auth-card" style={{ maxWidth: 420 }} onClick={e => e.stopPropagation()}>
        <h2 style={{ fontSize: 15, fontWeight: 600, marginBottom: 6 }}>Ativar verificação em duas etapas</h2>
        {!setup ? (error
          ? <div className="auth-error" role="alert">{error}</div>
          : <LoadingState label="Gerando segredo…" />) : (
          <form onSubmit={submit}>
            <p style={{ fontSize: 12.5, color: 'var(--ink-2)', lineHeight: 1.5, marginBottom: 10 }}>
              Adicione a chave abaixo no seu app autenticador (Google Authenticator,
              Aegis, 1Password…) e confirme com o código de 6 dígitos.
            </p>
            <div style={{
              fontFamily: 'var(--mono)', fontSize: 13, background: 'var(--bg)',
              border: '1px solid var(--border)', borderRadius: 'var(--r)',
              padding: '8px 10px', marginBottom: 12, wordBreak: 'break-all',
            }}>{setup.secret}</div>
            {error && <div className="auth-error" role="alert">{error}</div>}
            <label className="auth-field">
              <span className="label-xs">Código do app</span>
              <input className="auth-input" inputMode="numeric" pattern="[0-9]*"
                maxLength={6} required autoFocus value={code}
                onChange={e => setCode(e.target.value.replace(/\D/g, ''))} />
            </label>
            <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
              <Btn variant="primary" size="sm" disabled={busy || code.length !== 6}>
                {busy ? '…' : 'Ativar'}
              </Btn>
              <Btn variant="ghost" size="sm" type="button" onClick={onClose}>Cancelar</Btn>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}

function ScreenSecurity({ addToast }) {
  const mock = !!window.USE_MOCK_DATA;
  const [sessions, setSessions] = useSecState(mock ? (CT.securitySessions ?? []) : null);
  const [logins, setLogins] = useSecState(mock ? (CT.securityLogins ?? []) : null);
  const [loading, setLoading] = useSecState(!mock);
  const [error, setError] = useSecState(null);
  const [modal, setModal] = useSecState(null);  // 'enable' | 'disable' | 'regen'
  const [codes, setCodes] = useSecState(null);
  const [totpOn, setTotpOn] = useSecState(!!CT_AUTH.state()?.user?.totp_enabled);

  const load = useSecCallback(() => {
    if (mock) return;
    setLoading(true);
    Promise.all([CT_API.getSessions(), CT_API.getLoginHistory(20)])
      .then(([s, l]) => {
        setSessions(s ?? []);
        setLogins(l?.data ?? []);
        setLoading(false); setError(null);
      })
      .catch(e => { setError(e); setLoading(false); });
  }, [mock]);

  useSecEffect(() => { load(); }, [load]);

  const act = async (fn, okMsg) => {
    if (mock) { addToast?.('Modo demo: ação não aplicada.', 'info'); return; }
    try { await fn(); addToast?.(okMsg, 'check'); load(); }
    catch (e) { addToast?.(e?.message ?? 'Falha na ação.', 'alert'); }
  };

  if (loading) return <LoadingState label="Carregando segurança…" />;
  if (error) return <ErrorState message="Erro ao carregar segurança" onRetry={load} />;

  const others = (sessions ?? []).filter(s => !s.current).length;

  return (
    <div>
      <div className="page-head">
        <div>
          <h1 className="page-title">Segurança & Sessões</h1>
          <div className="page-sub">Suas sessões, verificação em duas etapas e histórico de acesso</div>
        </div>
        <Btn variant="ghost" size="sm" onClick={load}><Icon name="refresh" size={13} /></Btn>
      </div>

      {/* -------------------------------------------------- active sessions */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-head">
          <span className="card-title"><Icon name="eye" />Sessões ativas</span>
          <Btn variant="ghost" size="sm" disabled={others === 0}
            onClick={() => act(() => CT_API.revokeOtherSessions(),
              'Outras sessões encerradas.')}>
            Encerrar outras sessões
          </Btn>
        </div>
        <div style={{ overflowX: 'auto' }}>
          <table className="tbl">
            <thead>
              <tr>
                <th style={{ textAlign: 'left' }}>Dispositivo</th>
                <th style={{ textAlign: 'left' }}>IP</th>
                <th style={{ textAlign: 'left' }}>Último uso</th>
                <th style={{ textAlign: 'left' }}>Início</th>
                <th style={{ textAlign: 'right' }}>Ações</th>
              </tr>
            </thead>
            <tbody>
              {(sessions ?? []).map(s => (
                <tr key={s.id}>
                  <td>
                    <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span style={{ fontWeight: 500 }}>{parseUA(s.user_agent)}</span>
                      {s.current && <Badge variant="ok" dot={false}>Atual</Badge>}
                      {s.remember && <Badge variant="neutral" dot={false}>lembrado</Badge>}
                    </span>
                  </td>
                  <td style={{ fontFamily: 'var(--mono)', fontSize: 12 }}>{s.ip ?? '—'}</td>
                  <td style={{ fontFamily: 'var(--mono)', fontSize: 12 }}>{fmtSecTs(s.last_seen_at)}</td>
                  <td style={{ fontFamily: 'var(--mono)', fontSize: 12 }}>{fmtSecTs(s.created_at)}</td>
                  <td style={{ textAlign: 'right' }}>
                    <Btn variant="ghost" size="sm"
                      data-tip={s.current ? 'Encerra a sessão atual (faz logout)' : undefined}
                      onClick={() => act(() => CT_API.revokeSession(s.id).then(r => {
                        if (r?.current) CT_AUTH.load();
                      }), 'Sessão encerrada.')}>
                      Encerrar
                    </Btn>
                  </td>
                </tr>
              ))}
              {(sessions ?? []).length === 0 && (
                <tr><td colSpan={5}><EmptyState label="Nenhuma sessão ativa" /></td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* --------------------------------------------------------- 2FA card */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-head">
          <span className="card-title"><Icon name="shield" />Verificação em duas etapas</span>
          <Badge variant={totpOn ? 'ok' : 'warn'} dot={false}>
            {totpOn ? 'Ativa' : 'Inativa'}
          </Badge>
        </div>
        <div className="card-pad" style={{ display: 'flex', flexWrap: 'wrap', gap: 10, alignItems: 'center' }}>
          <p style={{ fontSize: 12.5, color: 'var(--ink-2)', lineHeight: 1.5, flex: 1, minWidth: 260, margin: 0 }}>
            {totpOn
              ? 'O login pede um código do seu app autenticador. Os códigos de backup cobrem a perda do dispositivo — regenerar invalida todos os anteriores.'
              : 'Proteja a conta exigindo um código do app autenticador a cada login.'}
          </p>
          {totpOn ? (
            <span style={{ display: 'flex', gap: 8 }}>
              <Btn variant="ghost" size="sm" onClick={() =>
                mock ? addToast?.('Modo demo: ação não aplicada.', 'info') : setModal('regen')}>
                Regenerar códigos de backup
              </Btn>
              <Btn variant="ghost" size="sm" onClick={() =>
                mock ? addToast?.('Modo demo: ação não aplicada.', 'info') : setModal('disable')}>
                Desativar
              </Btn>
            </span>
          ) : (
            <Btn variant="primary" size="sm" onClick={() =>
              mock ? addToast?.('Modo demo: ação não aplicada.', 'info') : setModal('enable')}>
              Ativar 2FA
            </Btn>
          )}
        </div>
      </div>

      {/* -------------------------------------------------- login history */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-head">
          <span className="card-title"><Icon name="clock" />Histórico de logins</span>
          <Badge variant="neutral" dot={false}>somente o seu e-mail</Badge>
        </div>
        <div style={{ overflowX: 'auto' }}>
          <table className="tbl">
            <thead>
              <tr>
                <th style={{ textAlign: 'left' }}>Quando</th>
                <th style={{ textAlign: 'left' }}>IP</th>
                <th style={{ textAlign: 'left' }}>Dispositivo</th>
                <th style={{ textAlign: 'left' }}>Resultado</th>
              </tr>
            </thead>
            <tbody>
              {(logins ?? []).map(e => (
                <tr key={e.id}>
                  <td style={{ fontFamily: 'var(--mono)', fontSize: 12 }}>{fmtSecTs(e.ts)}</td>
                  <td style={{ fontFamily: 'var(--mono)', fontSize: 12 }}>{e.ip ?? '—'}</td>
                  <td style={{ fontSize: 12 }}>{parseUA(e.ua)}</td>
                  <td>
                    <Badge variant={e.success ? 'ok' : 'down'} dot={false}>
                      {e.success ? 'sucesso' : 'falha'}
                    </Badge>
                  </td>
                </tr>
              ))}
              {(logins ?? []).length === 0 && (
                <tr><td colSpan={4}><EmptyState label="Nenhum login registrado" /></td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Deferido e declarado: allowlist de IP fica para uma fase futura. */}
      <div className="card">
        <div className="card-pad" style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <Icon name="info" size={15} style={{ color: 'var(--ink-3)', flexShrink: 0 }} />
          <p style={{ fontSize: 12.5, color: 'var(--ink-3)', margin: 0 }}>
            Restrição de acesso por IP (allowlist) está planejada para uma fase futura.
          </p>
        </div>
      </div>

      {modal === 'enable' && (
        <Enable2FAModal
          onClose={() => setModal(null)}
          onDone={(backup) => { setModal(null); setTotpOn(true); setCodes(backup); CT_AUTH.load(); }} />
      )}
      {modal === 'disable' && (
        <PasswordConfirmModal title="Desativar verificação em duas etapas" cta="Desativar"
          onClose={() => setModal(null)}
          onConfirm={async (password) => {
            await CT_API.disable2FA(password);
            setModal(null); setTotpOn(false); CT_AUTH.load();
            addToast?.('Verificação em duas etapas desativada.', 'check');
          }} />
      )}
      {modal === 'regen' && (
        <PasswordConfirmModal title="Regenerar códigos de backup" cta="Regenerar"
          onClose={() => setModal(null)}
          onConfirm={async (password) => {
            const r = await CT_API.regenerateBackupCodes(password);
            setModal(null); setCodes(r.backup_codes ?? []);
          }} />
      )}
      {codes && <BackupCodesModal codes={codes} onClose={() => setCodes(null)} />}
    </div>
  );
}
window.ScreenSecurity = ScreenSecurity;
