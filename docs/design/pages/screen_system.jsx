/* ============================================================
   A9 — System pages: 404 (unknown deep-link), 403 (coherent with
   the RBAC envelope from require_perm), maintenance (API down) and
   the fatal-error page used by the global boundary. All built on
   the EmptyState/ErrorState visual language (per the handoff spec:
   no backend — pure UI states).
   ============================================================ */

function SystemPage({ icon, title, sub, children }) {
  return (
    <div style={{ display: 'grid', placeItems: 'center', minHeight: '60vh', padding: 24 }}>
      <div style={{ textAlign: 'center', maxWidth: 440 }}>
        <Icon name={icon} size={34} style={{ color: 'var(--ink-3)', margin: '0 auto 14px' }} />
        <h1 style={{ fontSize: 18, fontWeight: 600, marginBottom: 6 }}>{title}</h1>
        {sub && <p style={{ fontSize: 13, color: 'var(--ink-2)', lineHeight: 1.6, marginBottom: 16 }}>{sub}</p>}
        {children}
      </div>
    </div>
  );
}
window.SystemPage = SystemPage;

function NotFoundScreen({ navigate }) {
  return (
    <SystemPage icon="info" title="Página não encontrada"
      sub="Este endereço não corresponde a nenhuma tela do console. O link pode estar desatualizado.">
      <Btn variant="primary" size="sm" onClick={() => navigate?.('overview')}>
        Voltar ao início
      </Btn>
    </SystemPage>
  );
}
window.NotFoundScreen = NotFoundScreen;

function ForbiddenScreen({ navigate, requiredPermission, role }) {
  return (
    <SystemPage icon="shield" title="Sem permissão"
      sub={`Seu perfil${role ? ` (${role})` : ''} não tem acesso a esta área.`}>
      {requiredPermission && (
        <div className="chip" style={{ marginBottom: 14 }}>
          requer <b style={{ fontFamily: 'var(--mono)' }}>{requiredPermission}</b>
        </div>
      )}
      <div>
        <Btn variant="primary" size="sm" onClick={() => navigate?.('overview')}>
          Voltar ao início
        </Btn>
      </div>
    </SystemPage>
  );
}
window.ForbiddenScreen = ForbiddenScreen;

function MaintenanceScreen({ onRetry }) {
  return (
    <div className="auth-wrap">
      <div className="auth-card" style={{ textAlign: 'center' }}>
        <Icon name="clock" size={30} style={{ color: 'var(--warn)', margin: '0 auto 12px' }} />
        <h1 style={{ fontSize: 17, fontWeight: 600, marginBottom: 6 }}>Em manutenção</h1>
        <p style={{ fontSize: 12.5, color: 'var(--ink-2)', lineHeight: 1.6, marginBottom: 14 }}>
          O backend não está respondendo. Tentaremos reconectar automaticamente
          a cada 10 segundos.
        </p>
        <Btn variant="primary" size="sm" onClick={onRetry}>
          <Icon name="refresh" size={13} /> Tentar agora
        </Btn>
      </div>
    </div>
  );
}
window.MaintenanceScreen = MaintenanceScreen;

function FatalErrorScreen({ errorId, message }) {
  return (
    <div className="auth-wrap">
      <div className="auth-card" style={{ textAlign: 'center' }}>
        <Icon name="alert" size={30} style={{ color: 'var(--down)', margin: '0 auto 12px' }} />
        <h1 style={{ fontSize: 17, fontWeight: 600, marginBottom: 6 }}>Algo quebrou</h1>
        <p style={{ fontSize: 12.5, color: 'var(--ink-2)', lineHeight: 1.6, marginBottom: 8 }}>
          Um erro inesperado derrubou o console. Recarregue para continuar; se
          persistir, informe o código abaixo ao suporte.
        </p>
        {message && (
          <p style={{ fontSize: 11.5, fontFamily: 'var(--mono)', color: 'var(--ink-3)', marginBottom: 10 }}>
            {message}
          </p>
        )}
        <div className="chip" data-testid="error-id" style={{ marginBottom: 14 }}>
          erro <b style={{ fontFamily: 'var(--mono)' }}>{errorId}</b>
        </div>
        <div>
          <Btn variant="primary" size="sm" onClick={() => window.location.reload()}>
            <Icon name="refresh" size={13} /> Recarregar
          </Btn>
        </div>
      </div>
    </div>
  );
}
window.FatalErrorScreen = FatalErrorScreen;
