// Supabase auth module — exposes getUser(), getSB(), initAuth(), authSignIn(), authSignUp(), authSignOut()

const _sb = (() => {
  if (!window.SUPABASE_URL || window.SUPABASE_URL.includes("VOTRE-PROJET")) return null;
  return window.supabase.createClient(window.SUPABASE_URL, window.SUPABASE_ANON_KEY);
})();

let _currentUser = null;

function getUser() { return _currentUser; }
function getSB()   { return _sb; }

async function initAuth(onAuth, onGuest) {
  if (!_sb) { onGuest(); return; }
  const { data: { session } } = await _sb.auth.getSession();
  _currentUser = session?.user ?? null;
  _currentUser ? onAuth(_currentUser) : onGuest();

  _sb.auth.onAuthStateChange((_ev, session) => {
    _currentUser = session?.user ?? null;
    _currentUser ? onAuth(_currentUser) : onGuest();
  });
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
