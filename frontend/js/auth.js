// Supabase auth module — exposes getUser(), getSB(), initAuth(), authSignIn(), authSignUp(), authSignOut(), authResetPassword(), authUpdatePassword()

const _sb = (() => {
  if (!window.SUPABASE_URL || window.SUPABASE_URL.includes("VOTRE-PROJET")) return null;
  return window.supabase.createClient(window.SUPABASE_URL, window.SUPABASE_ANON_KEY);
})();

let _currentUser = null;

function getUser() { return _currentUser; }
function getSB()   { return _sb; }

async function initAuth(onAuth, onGuest, onRecovery) {
  if (!_sb) { onGuest(); return; }

  let _isRecovery = false;

  _sb.auth.onAuthStateChange((_ev, session) => {
    _currentUser = session?.user ?? null;
    if (_ev === "PASSWORD_RECOVERY") {
      _isRecovery = true;
      if (onRecovery) onRecovery(_currentUser);
      return;
    }
    if (_isRecovery) {
      _isRecovery = false;
      _currentUser ? onAuth(_currentUser) : onGuest();
      return;
    }
    _currentUser ? onAuth(_currentUser) : onGuest();
  });

  const { data: { session } } = await _sb.auth.getSession();
  _currentUser = session?.user ?? null;
  if (!_isRecovery) {
    _currentUser ? onAuth(_currentUser) : onGuest();
  }
}

async function authSignIn(email, password) {
  const { data, error } = await _sb.auth.signInWithPassword({ email, password });
  if (error) throw error;
  return data.user;
}

async function authSignUp(email, password) {
  const { data, error } = await _sb.auth.signUp({ email, password });
  if (error) throw error;
  return data;
}

async function authSignOut() {
  if (_sb) await _sb.auth.signOut();
}

async function authResetPassword(email) {
  const { error } = await _sb.auth.resetPasswordForEmail(email, {
    redirectTo: window.location.origin + window.location.pathname,
  });
  if (error) throw error;
}

async function authUpdatePassword(newPassword) {
  const { error } = await _sb.auth.updateUser({ password: newPassword });
  if (error) throw error;
}
