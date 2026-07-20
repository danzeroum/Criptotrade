/* ============================================================
   A3 — Usuários & Permissões (admin only; nav filtered by
   manage_users and route-guarded in app.jsx). Users table with
   role/status/last-access, invite flow (create/resend/revoke),
   role & status changes, and the read-only permission matrix
   served by GET /v1/roles.
   ============================================================ */
const { useState: useUsersState, useEffect: useUsersEffect, useCallback: useUsersCallback } = React;

const ROLE_BADGE = { admin: 'violet', operador: 'info', visualizador: 'neutral' };
const STATUS_BADGE = { active: 'ok', pending: 'warn', suspended: 'down' };
const STATUS_LABEL = { active: 'Ativo', pending: 'Pendente', suspended: 'Suspenso' };

function InviteModal({ roles, onClose, onInvited, addToast }) {
  const [email, setEmail] = useUsersState('');
  const [role, setRole] = useUsersState('visualizador');
  const [busy, setBusy] = useUsersState(false);
  const [error, setError] = useUsersState(null);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true); setError(null);
    try {
      await CT_API.inviteUser({ email, role });
      addToast?.(`Convite enviado para ${email}.`, 'check');
      onInvited?.();
      onClose?.();
    } catch (err) {
      setError(err?.message ?? 'Não foi possível convidar.');
    } finally { setBusy(false); }
  };

  return (
    <div className="lock-overlay" role="dialog" aria-label="Convidar usuário" onClick={onClose}>
      <div className="auth-card" style={{ maxWidth: 380 }} onClick={e => e.stopPropagation()}>
        <h2 style={{ fontSize: 15, fontWeight: 600, marginBottom: 12 }}>Convidar usuário</h2>
        <form onSubmit={submit}>
          {error && <div className="auth-error" role="alert">{error}</div>}
          <label className="auth-field">
            <span className="label-xs">E-mail</span>
            <input className="auth-input" type="email" required value={email}
              onChange={e => setEmail(e.target.value)} />
          </label>
          <label className="auth-field">
            <span className="label-xs">Papel</span>
            <select className="auth-input" value={role} onChange={e => setRole(e.target.value)}>
              {roles.map(r => <option key={r.id} value={r.id}>{r.label}</option>)}
            </select>
          </label>
          <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
            <Btn variant="primary" size="sm" disabled={busy}>{busy ? '…' : 'Enviar convite'}</Btn>
            <Btn variant="ghost" size="sm" type="button" onClick={onClose}>Cancelar</Btn>
          </div>
        </form>
      </div>
    </div>
  );
}

function ScreenUsers({ addToast }) {
  const [users, setUsers] = useUsersState(null);
  const [roles, setRoles] = useUsersState([]);
  const [loading, setLoading] = useUsersState(true);
  const [error, setError] = useUsersState(null);
  const [inviting, setInviting] = useUsersState(false);

  const load = useUsersCallback(() => {
    setLoading(true);
    Promise.all([CT_API.getUsers(), CT_API.getRoles()])
      .then(([u, r]) => { setUsers(u); setRoles(r); setLoading(false); setError(null); })
      .catch(e => { setError(e); setLoading(false); });
  }, []);

  useUsersEffect(() => { load(); }, [load]);

  const act = async (fn, okMsg) => {
    try { await fn(); addToast?.(okMsg, 'check'); load(); }
    catch (e) { addToast?.(e?.message ?? 'Falha na ação.', 'alert'); }
  };

  if (loading) return <LoadingState label="Carregando usuários…" />;
  if (error) return <ErrorState message="Erro ao carregar usuários" onRetry={load} />;

  const myEmail = CT_AUTH.state()?.user?.email;

  return (
    <div>
      <div className="page-head">
        <div>
          <h1 className="page-title">Usuários & Permissões</h1>
          <div className="page-sub">RBAC · papéis Visualizador, Operador e Admin</div>
        </div>
        <Btn variant="primary" size="sm" onClick={() => setInviting(true)}>
          <Icon name="plus" size={13} /> Convidar
        </Btn>
      </div>

      <div className="card" style={{ marginBottom: 20 }}>
        <div className="card-head">
          <span className="card-title"><Icon name="user" />Usuários</span>
          <Badge variant="neutral" dot={false}>{(users ?? []).length} conta(s)</Badge>
        </div>
        <div style={{ overflowX: 'auto' }}>
          <table className="tbl">
            <thead>
              <tr>
                <th style={{ textAlign: 'left' }}>Usuário</th>
                <th style={{ textAlign: 'left' }}>Papel</th>
                <th style={{ textAlign: 'left' }}>Status</th>
                <th style={{ textAlign: 'left' }}>Último acesso</th>
                <th style={{ textAlign: 'right' }}>Ações</th>
              </tr>
            </thead>
            <tbody>
              {(users ?? []).map(u => (
                <tr key={u.id}>
                  <td>
                    <div style={{ fontWeight: 500 }}>{u.name ?? '—'}</div>
                    <div style={{ fontSize: 11.5, color: 'var(--ink-3)', fontFamily: 'var(--mono)' }}>{u.email}</div>
                  </td>
                  <td>
                    {u.status === 'pending' ? (
                      <Badge variant={ROLE_BADGE[u.role] ?? 'neutral'}>{u.role}</Badge>
                    ) : (
                      <select className="auth-input" style={{ width: 'auto', padding: '4px 8px', fontSize: 12 }}
                        value={u.role} disabled={u.email === myEmail}
                        onChange={e => act(() => CT_API.patchUserRole(u.id, e.target.value),
                          `Papel de ${u.email} atualizado.`)}>
                        {roles.map(r => <option key={r.id} value={r.id}>{r.label}</option>)}
                      </select>
                    )}
                  </td>
                  <td><Badge variant={STATUS_BADGE[u.status] ?? 'neutral'}>{STATUS_LABEL[u.status] ?? u.status}</Badge></td>
                  <td style={{ fontFamily: 'var(--mono)', fontSize: 12, color: 'var(--ink-2)' }}>
                    {u.last_login_at ? fmtDateTime(u.last_login_at) : '—'}
                  </td>
                  <td style={{ textAlign: 'right', whiteSpace: 'nowrap' }}>
                    {u.status === 'pending' && u.invite_id && (
                      <>
                        <Btn variant="ghost" size="sm"
                          onClick={() => act(() => CT_API.resendInvite(u.invite_id), 'Convite reenviado.')}>
                          Reenviar
                        </Btn>
                        <Btn variant="ghost" size="sm"
                          onClick={() => act(() => CT_API.revokeInvite(u.invite_id), 'Convite revogado.')}>
                          Revogar
                        </Btn>
                      </>
                    )}
                    {u.status === 'active' && u.email !== myEmail && (
                      <Btn variant="ghost" size="sm"
                        onClick={() => act(() => CT_API.patchUserStatus(u.id, 'suspended'),
                          `${u.email} suspenso.`)}>
                        Suspender
                      </Btn>
                    )}
                    {u.status === 'suspended' && (
                      <Btn variant="ghost" size="sm"
                        onClick={() => act(() => CT_API.patchUserStatus(u.id, 'active'),
                          `${u.email} reativado.`)}>
                        Reativar
                      </Btn>
                    )}
                  </td>
                </tr>
              ))}
              {(users ?? []).length === 0 && (
                <tr><td colSpan={5}><EmptyState label="Nenhum usuário" /></td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card">
        <div className="card-head">
          <span className="card-title"><Icon name="shield" />Matriz de permissões</span>
          <Badge variant="neutral" dot={false}>somente leitura</Badge>
        </div>
        <div className="card-pad" style={{ overflowX: 'auto' }}>
          <div className="grid grid-3" style={{ gap: 12 }}>
            {roles.map(r => (
              <div key={r.id} style={{ border: '1px solid var(--border)', borderRadius: 'var(--r)', padding: 12 }}>
                <Badge variant={ROLE_BADGE[r.id] ?? 'neutral'}>{r.label}</Badge>
                <ul style={{ margin: '10px 0 0', paddingLeft: 16, fontSize: 12.5, color: 'var(--ink-2)' }}>
                  {r.permissions.length === 0 && <li>somente leitura</li>}
                  {r.permissions.map(p => <li key={p} style={{ fontFamily: 'var(--mono)' }}>{p}</li>)}
                </ul>
              </div>
            ))}
          </div>
        </div>
      </div>

      {inviting && (
        <InviteModal roles={roles} addToast={addToast}
          onClose={() => setInviting(false)} onInvited={load} />
      )}
    </div>
  );
}
window.ScreenUsers = ScreenUsers;
