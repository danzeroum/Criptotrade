/* ============================================================
   A2 — Conta & Perfil (self-service; só sessão autenticada).
   Perfil (nome, cargo, avatar por iniciais + cor derivada dos
   tokens — upload de imagem deferido), preferências (idioma,
   fuso pesquisável, formato regional ÚNICO para número+data,
   com preview ao vivo) e troca de senha (exige a atual; as
   outras sessões são desconectadas — integração A7).
   E-mail é somente leitura (mudança deferida). Tema fora de
   escopo (design system light-only).
   ============================================================ */
const { useState: useAccState, useEffect: useAccEffect } = React;

// Paleta 1:1 dos tokens do design system (styles.css) — ids, nunca hex novo.
const AVATAR_COLOR_VARS = {
  'ink':   'var(--ink)',
  'ink-2': 'var(--ink-2)',
  'info':  'var(--info)',
  'violet':'var(--violet)',
  'up':    'var(--up)',
  'down':  'var(--down)',
  'warn':  'var(--warn)',
};
window.AVATAR_COLOR_VARS = AVATAR_COLOR_VARS;

const TZ_COMMON = [
  'America/Sao_Paulo', 'UTC', 'America/New_York', 'Europe/Lisbon', 'Europe/London',
];

const initialsOf = (name, email) =>
  (name ?? email ?? '?').slice(0, 2).toUpperCase();

// Regional format: ONE control writing both backend fields (mixing number
// en-US with date pt-BR on purpose would recreate the C7 inconsistency).
const regionalOf = (prefs) =>
  (prefs.number_locale === prefs.date_locale && prefs.number_locale !== 'auto')
    ? prefs.number_locale : 'auto';

function AccountAvatar({ name, email, colorId, size = 56 }) {
  return (
    <div style={{
      width: size, height: size, borderRadius: '50%',
      background: AVATAR_COLOR_VARS[colorId] ?? 'var(--ink)',
      color: '#fff', display: 'grid', placeItems: 'center',
      fontWeight: 600, fontSize: size * 0.34, flexShrink: 0,
    }}>{initialsOf(name, email)}</div>
  );
}

function ScreenAccount({ addToast }) {
  const [profile, setProfile] = useAccState(null);
  const [prefs, setPrefs] = useAccState(null);
  const [loading, setLoading] = useAccState(true);
  const [error, setError] = useAccState(null);

  // drafts
  const [pDraft, setPDraft] = useAccState(null);
  const [fDraft, setFDraft] = useAccState(null);
  const [pw, setPw] = useAccState({ current: '', next: '', confirm: '' });
  const [busy, setBusy] = useAccState(null);  // 'profile' | 'prefs' | 'password'

  const load = () => {
    setLoading(true);
    Promise.all([CT_API.getAccountProfile(), CT_API.getPreferences()])
      .then(([p, f]) => {
        setProfile(p); setPrefs(f);
        setPDraft({ name: p.name ?? '', job_title: p.job_title ?? '',
                    avatar_color: p.avatar_color ?? 'ink' });
        setFDraft({ locale: f.locale, timezone: f.timezone, regional: regionalOf(f) });
        setLoading(false); setError(null);
      })
      .catch(e => { setError(e); setLoading(false); });
  };

  useAccEffect(() => { load(); }, []);

  const tzList = (() => {
    try {
      const all = Intl.supportedValuesOf('timeZone');
      return [...TZ_COMMON, ...all.filter(t => !TZ_COMMON.includes(t))];
    } catch (_) { return TZ_COMMON; }
  })();

  if (loading || !pDraft || !fDraft) return <LoadingState label="Carregando conta…" />;
  if (error) return <ErrorState message="Erro ao carregar a conta" onRetry={load} />;

  // Live preview computed from the DRAFT (before saving): the acceptance made
  // visible — numbers and dates as the whole console will render them.
  const previewNumLocale = fDraft.regional === 'auto' ? 'en' : fDraft.regional;
  const previewDateLocale = fDraft.regional === 'auto' ? 'pt-BR' : fDraft.regional;
  let previewTz = {};
  if (fDraft.timezone && fDraft.timezone !== 'auto') {
    try {
      new Date().toLocaleString('en', { timeZone: fDraft.timezone });
      previewTz = { timeZone: fDraft.timezone };
    } catch (_) { previewTz = {}; }
  }
  const preview = `$${(1234.56).toLocaleString(previewNumLocale, {
    minimumFractionDigits: 2, maximumFractionDigits: 2,
  })} · ${new Date('2026-07-18T17:30:00Z').toLocaleString(previewDateLocale, previewTz)}`;

  const saveProfile = async (e) => {
    e.preventDefault();
    setBusy('profile');
    try {
      const out = await CT_API.patchAccountProfile({
        name: pDraft.name || null, job_title: pDraft.job_title || null,
        avatar_color: pDraft.avatar_color,
      });
      setProfile(out);
      CT_AUTH.load();  // refresh header chip (name/color)
      addToast?.('Perfil atualizado.', 'check');
    } catch (err) { addToast?.(err?.message ?? 'Falha ao salvar o perfil.', 'alert'); }
    finally { setBusy(null); }
  };

  const savePrefs = async (e) => {
    e.preventDefault();
    const body = {
      locale: fDraft.locale,
      timezone: fDraft.timezone || 'auto',
      number_locale: fDraft.regional,
      date_locale: fDraft.regional,
    };
    setBusy('prefs');
    try {
      const out = await CT_API.patchPreferences(body);
      setPrefs(out);
      CT_PREFS.apply(out);  // the WHOLE console re-formats from here
      addToast?.('Preferências salvas — formatos aplicados ao console.', 'check');
    } catch (err) { addToast?.(err?.message ?? 'Falha ao salvar preferências.', 'alert'); }
    finally { setBusy(null); }
  };

  const savePassword = async (e) => {
    e.preventDefault();
    if (pw.next !== pw.confirm) {
      addToast?.('A confirmação não confere com a nova senha.', 'alert');
      return;
    }
    setBusy('password');
    try {
      const out = await CT_API.changePassword({
        current_password: pw.current, new_password: pw.next,
      });
      setPw({ current: '', next: '', confirm: '' });
      addToast?.(`Senha alterada. ${out.other_sessions_revoked} outra(s) sessão(ões) desconectada(s).`, 'check');
    } catch (err) { addToast?.(err?.message ?? 'Falha ao trocar a senha.', 'alert'); }
    finally { setBusy(null); }
  };

  return (
    <div>
      <div className="page-head">
        <div>
          <h1 className="page-title">Conta & Perfil</h1>
          <div className="page-sub">Seus dados, preferências de formato e senha</div>
        </div>
      </div>

      {/* ---------------------------------------------------------- profile */}
      <form className="card" style={{ marginBottom: 16 }} onSubmit={saveProfile}>
        <div className="card-head">
          <span className="card-title"><Icon name="user" />Perfil</span>
        </div>
        <div className="card-pad">
          <div style={{ display: 'flex', gap: 16, alignItems: 'flex-start', flexWrap: 'wrap' }}>
            <AccountAvatar name={pDraft.name} email={profile.email}
              colorId={pDraft.avatar_color} />
            <div style={{ flex: 1, minWidth: 260 }}>
              <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                <label className="auth-field" style={{ flex: 1, minWidth: 180 }}>
                  <span className="label-xs">Nome</span>
                  <input className="auth-input" maxLength={80} value={pDraft.name}
                    onChange={e => setPDraft(d => ({ ...d, name: e.target.value }))} />
                </label>
                <label className="auth-field" style={{ flex: 1, minWidth: 180 }}>
                  <span className="label-xs">Cargo</span>
                  <input className="auth-input" maxLength={80} value={pDraft.job_title}
                    placeholder="ex.: Operador"
                    onChange={e => setPDraft(d => ({ ...d, job_title: e.target.value }))} />
                </label>
              </div>
              <label className="auth-field">
                <span className="label-xs">E-mail (identidade de login — não editável)</span>
                <input className="auth-input" value={profile.email} disabled
                  data-tip="Mudança de e-mail exige re-verificação — planejada para uma fase futura" />
              </label>
              <div className="auth-field">
                <span className="label-xs">Cor do avatar</span>
                <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
                  {Object.entries(AVATAR_COLOR_VARS).map(([id, v]) => (
                    <button key={id} type="button" aria-label={`Cor ${id}`}
                      onClick={() => setPDraft(d => ({ ...d, avatar_color: id }))}
                      style={{
                        width: 26, height: 26, borderRadius: '50%', background: v,
                        cursor: 'pointer',
                        border: pDraft.avatar_color === id
                          ? '2px solid var(--ink)' : '2px solid var(--surface)',
                        outline: '1px solid var(--border-2)',
                      }} />
                  ))}
                </div>
              </div>
              <Btn variant="primary" size="sm" disabled={busy === 'profile'}>
                {busy === 'profile' ? '…' : 'Salvar perfil'}
              </Btn>
            </div>
          </div>
        </div>
      </form>

      {/* ------------------------------------------------------ preferences */}
      <form className="card" style={{ marginBottom: 16 }} onSubmit={savePrefs}>
        <div className="card-head">
          <span className="card-title"><Icon name="settings" />Preferências</span>
          <span className="chip" data-testid="prefs-preview">Exemplo: {preview}</span>
        </div>
        <div className="card-pad" style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'flex-end' }}>
          <label className="auth-field" style={{ margin: 0, minWidth: 150 }}>
            <span className="label-xs">Idioma</span>
            <select className="auth-input" value={fDraft.locale} aria-label="Idioma"
              onChange={e => setFDraft(d => ({ ...d, locale: e.target.value }))}>
              <option value="pt-BR">Português (Brasil)</option>
              <option value="en">English</option>
            </select>
          </label>
          <label className="auth-field" style={{ margin: 0, minWidth: 220 }}>
            <span className="label-xs">Fuso horário (digite para buscar)</span>
            <input className="auth-input" list="ct-tz-list" value={fDraft.timezone}
              aria-label="Fuso horário"
              onChange={e => setFDraft(d => ({ ...d, timezone: e.target.value }))} />
            <datalist id="ct-tz-list">
              <option value="auto">Automático (fuso do navegador)</option>
              {tzList.map(tz => <option key={tz} value={tz} />)}
            </datalist>
          </label>
          <label className="auth-field" style={{ margin: 0, minWidth: 170 }}>
            <span className="label-xs">Formato regional (números e datas)</span>
            <select className="auth-input" value={fDraft.regional} aria-label="Formato regional"
              onChange={e => setFDraft(d => ({ ...d, regional: e.target.value }))}>
              <option value="auto">Automático (padrão atual)</option>
              <option value="en-US">en-US · 1,234.56</option>
              <option value="pt-BR">pt-BR · 1.234,56</option>
            </select>
          </label>
          <Btn variant="primary" size="sm" disabled={busy === 'prefs'}>
            {busy === 'prefs' ? '…' : 'Salvar preferências'}
          </Btn>
        </div>
      </form>

      {/* --------------------------------------------------------- password */}
      <form className="card" onSubmit={savePassword}>
        <div className="card-head">
          <span className="card-title"><Icon name="lock" />Trocar senha</span>
        </div>
        <div className="card-pad">
          <p style={{ fontSize: 12.5, color: 'var(--ink-2)', margin: '0 0 10px' }}>
            Ao trocar a senha, todas as <b>outras</b> sessões são desconectadas —
            esta permanece ativa.
          </p>
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'flex-end' }}>
            <label className="auth-field" style={{ margin: 0, minWidth: 180 }}>
              <span className="label-xs">Senha atual</span>
              <input className="auth-input" type="password" required value={pw.current}
                onChange={e => setPw(s => ({ ...s, current: e.target.value }))} />
            </label>
            <label className="auth-field" style={{ margin: 0, minWidth: 180 }}>
              <span className="label-xs">Nova senha (mín. 8)</span>
              <input className="auth-input" type="password" required minLength={8}
                value={pw.next}
                onChange={e => setPw(s => ({ ...s, next: e.target.value }))} />
            </label>
            <label className="auth-field" style={{ margin: 0, minWidth: 180 }}>
              <span className="label-xs">Confirmar nova senha</span>
              <input className="auth-input" type="password" required value={pw.confirm}
                onChange={e => setPw(s => ({ ...s, confirm: e.target.value }))} />
            </label>
            <Btn variant="primary" size="sm" disabled={busy === 'password'}>
              {busy === 'password' ? '…' : 'Trocar senha'}
            </Btn>
          </div>
        </div>
      </form>
    </div>
  );
}
window.ScreenAccount = ScreenAccount;
