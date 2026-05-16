const API = window.API_URL || "http://localhost:8765";
const SUPABASE_OK = !!(window.SUPABASE_URL && !window.SUPABASE_URL.includes("VOTRE-PROJET"));

const state = {
  formats: ["feed", "story", "banner"],
  selectedFormats: ["feed"],
  imageSource: "none",
  ads: [],
  analysis: null,
  history: [],
};

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

// ---------------------------------------------------------------------------
// Navigation
// ---------------------------------------------------------------------------
function showPage(name) {
  $$(".page").forEach(p => p.classList.toggle("active", p.id === `page-${name}`));
  $$("nav button").forEach(b => b.classList.toggle("active", b.dataset.page === name));
}

// ---------------------------------------------------------------------------
// Backend health check
// ---------------------------------------------------------------------------
async function checkHealth() {
  const dot = $("#health-dot");
  try {
    const r = await fetch(`${API}/`, { signal: AbortSignal.timeout(3000) });
    if (r.ok) {
      dot.className = "health-dot online";
      dot.title = "Backend actif";
    } else throw new Error();
  } catch {
    dot.className = "health-dot offline";
    dot.title = "Backend hors ligne";
  }
}

// ---------------------------------------------------------------------------
// LocalStorage persistence
// ---------------------------------------------------------------------------
const LS_KEY = "loops_brand_config";

function saveBrandConfig() {
  const cfg = {
    brand_name:      $("#brand-name").value,
    tagline:         $("#tagline").value,
    description:     $("#description").value,
    cta:             $("#cta").value,
    primary_color:   $("#primary-hex").value,
    secondary_color: $("#secondary-hex").value,
    sector:          $("#sector").value,
    selectedFormats: state.selectedFormats,
    imageSource:     state.imageSource,
  };
  localStorage.setItem(LS_KEY, JSON.stringify(cfg));
  if (SUPABASE_OK) scheduleBrandConfigDBSave();
}

function loadBrandConfig() {
  const raw = localStorage.getItem(LS_KEY);
  if (!raw) return;
  try { applyConfig(JSON.parse(raw)); } catch {}
}

function applyConfig(cfg) {
  if (cfg.brand_name)    $("#brand-name").value    = cfg.brand_name;
  if (cfg.tagline)       $("#tagline").value        = cfg.tagline;
  if (cfg.description)   $("#description").value    = cfg.description;
  if (cfg.cta)           $("#cta").value            = cfg.cta;
  if (cfg.sector)        $("#sector").value         = cfg.sector;
  if (cfg.primary_color || cfg.primary_colour) {
    const c = cfg.primary_color || cfg.primary_colour;
    $("#primary-hex").value   = c;
    $("#primary-color").value = c;
  }
  if (cfg.secondary_color || cfg.secondary_colour) {
    const c = cfg.secondary_color || cfg.secondary_colour;
    $("#secondary-hex").value   = c;
    $("#secondary-color").value = c;
  }
  if (cfg.selected_formats || cfg.selectedFormats) {
    state.selectedFormats = cfg.selected_formats || cfg.selectedFormats;
    initFormatButtons();
  }
  if (cfg.image_source || cfg.imageSource) {
    state.imageSource = cfg.image_source || cfg.imageSource;
    $$(".source-btn").forEach(b => b.classList.toggle("selected", b.dataset.source === state.imageSource));
  }
}

// ---------------------------------------------------------------------------
// DB debounce (Supabase brand config save)
// ---------------------------------------------------------------------------
let _dbSaveTimer = null;
function scheduleBrandConfigDBSave() {
  clearTimeout(_dbSaveTimer);
  _dbSaveTimer = setTimeout(() => {
    const cfg = getBrandConfig();
    dbSaveBrandConfig({
      brand_name:      cfg.brand_name,
      tagline:         cfg.tagline,
      description:     cfg.description,
      cta:             cfg.cta,
      primary_color:   cfg.primary_color,
      secondary_color: cfg.secondary_color,
      sector:          cfg.sector,
      selected_formats: state.selectedFormats,
      image_source:    state.imageSource,
    }).catch(console.error);
  }, 2000);
}

// ---------------------------------------------------------------------------
// Color sync
// ---------------------------------------------------------------------------
function syncColor(colorInput, textInput) {
  colorInput.addEventListener("input", () => {
    textInput.value = colorInput.value;
    saveBrandConfig();
  });
  textInput.addEventListener("input", () => {
    if (/^#[0-9a-fA-F]{6}$/.test(textInput.value)) {
      colorInput.value = textInput.value;
      saveBrandConfig();
    }
  });
}

// ---------------------------------------------------------------------------
// Format selector
// ---------------------------------------------------------------------------
function initFormatButtons() {
  const grid = $("#format-grid");
  const defs = { feed: [40, 40], story: [23, 40], banner: [40, 21] };
  grid.innerHTML = "";
  state.formats.forEach((fmt) => {
    const btn = document.createElement("div");
    btn.className = "fmt-btn" + (state.selectedFormats.includes(fmt) ? " selected" : "");
    btn.dataset.fmt = fmt;
    const [w, h] = defs[fmt];
    btn.innerHTML = `<div class="fmt-thumb" style="width:${w}px;height:${h}px;"></div><span>${fmt}</span>`;
    btn.addEventListener("click", () => {
      if (state.selectedFormats.includes(fmt)) {
        if (state.selectedFormats.length === 1) return;
        state.selectedFormats = state.selectedFormats.filter((f) => f !== fmt);
      } else {
        state.selectedFormats.push(fmt);
      }
      btn.classList.toggle("selected");
      saveBrandConfig();
    });
    grid.appendChild(btn);
  });
}

// ---------------------------------------------------------------------------
// Source selector
// ---------------------------------------------------------------------------
function initSourceButtons() {
  $$(".source-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      $$(".source-btn").forEach((b) => b.classList.remove("selected"));
      btn.classList.add("selected");
      state.imageSource = btn.dataset.source;
      saveBrandConfig();
    });
  });
}

// ---------------------------------------------------------------------------
// Lightbox
// ---------------------------------------------------------------------------
function openLightbox(index) {
  const ad = state.ads[index];
  const lb = $("#lightbox");
  lb.querySelector("#lb-img").src = `data:image/png;base64,${ad.image_b64}`;
  lb.querySelector("#lb-label").textContent = `${ad.format.toUpperCase()} · ${ad.width}×${ad.height} · Variante ${ad.variant}`;
  lb.querySelector("#lb-dl").onclick = () => downloadAd(index);
  lb.classList.add("open");
  document.body.style.overflow = "hidden";
}

function closeLightbox() {
  $("#lightbox").classList.remove("open");
  document.body.style.overflow = "";
}

// ---------------------------------------------------------------------------
// Progress bar
// ---------------------------------------------------------------------------
function showProgress(container, total) {
  let wrap = container.querySelector(".progress-wrap");
  if (!wrap) {
    wrap = document.createElement("div");
    wrap.className = "progress-wrap";
    wrap.innerHTML = `<div class="progress-bar"><div class="progress-fill" style="width:0%"></div></div><div class="progress-label">Préparation…</div>`;
    container.appendChild(wrap);
  }
  wrap.style.display = "block";
  return {
    update(done, label) {
      wrap.querySelector(".progress-fill").style.width = `${Math.round((done / total) * 100)}%`;
      wrap.querySelector(".progress-label").textContent = label;
    },
    hide() { wrap.style.display = "none"; },
  };
}

// ---------------------------------------------------------------------------
// Form values
// ---------------------------------------------------------------------------
function getBrandConfig() {
  return {
    brand_name:      $("#brand-name").value.trim()  || "My Brand",
    tagline:         $("#tagline").value.trim()      || "Your tagline here",
    description:     $("#description").value.trim() || "Short product description.",
    cta:             $("#cta").value.trim()          || "Shop Now",
    primary_color:   $("#primary-hex").value,
    secondary_color: $("#secondary-hex").value,
    sector:          $("#sector").value,
  };
}

// ---------------------------------------------------------------------------
// Status helper
// ---------------------------------------------------------------------------
function setStatus(el, msg, type) {
  el.style.display = msg ? "block" : "none";
  el.className = "status " + (type || "");
  el.textContent = msg;
}

// ---------------------------------------------------------------------------
// Toast notification
// ---------------------------------------------------------------------------
function notify(msg, type = "loading") {
  let toast = $("#toast");
  if (!toast) {
    toast = document.createElement("div");
    toast.id = "toast";
    document.body.appendChild(toast);
  }
  toast.className = `toast toast-${type}`;
  toast.textContent = msg;
  toast.style.opacity = "1";
  clearTimeout(toast._timer);
  toast._timer = setTimeout(() => { toast.style.opacity = "0"; }, 4000);
}

// ---------------------------------------------------------------------------
// Generate
// ---------------------------------------------------------------------------
async function generateAds() {
  const btn = $("#btn-generate");
  const status = $("#gen-status");
  const grid = $("#ads-grid");

  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Génération…';
  setStatus(status, "Génération des visuels en cours…", "loading");
  grid.innerHTML = "";
  $("#btn-download-all").style.display = "none";

  const config = getBrandConfig();
  saveBrandConfig();
  const payload = {
    ...config,
    formats: state.selectedFormats,
    variants_per_format: 2,
    image_source: state.imageSource,
  };

  const isAI = state.imageSource === "ai";
  const totalAds = state.selectedFormats.length * 2;
  const timeoutMs = isAI ? totalAds * 55000 : 30000;

  let progress = null;
  let progressInterval = null;
  if (isAI) {
    progress = showProgress(btn.closest(".card"), totalAds);
    let elapsed = 0;
    const est = totalAds * 22;
    progressInterval = setInterval(() => {
      elapsed++;
      const pct = Math.min(0.9, elapsed / est);
      progress.update(pct * totalAds, `Génération IA… ~${Math.max(0, est - elapsed)}s restantes`);
    }, 1000);
  }

  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    const res = await fetch(`${API}/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: controller.signal,
    });
    clearTimeout(timer);
    if (!res.ok) throw new Error(await res.text());

    const data = await res.json();
    state.ads = data.ads.map((ad) => ({ ...ad, source: state.imageSource }));
    pushHistory(state.ads, config);
    renderAds(state.ads);
    setStatus(status, "", "");
    $("#btn-download-all").style.display = state.ads.length > 1 ? "inline-flex" : "none";
    if (progress) { progress.update(totalAds, "Terminé !"); setTimeout(() => progress.hide(), 2000); }

    if (SUPABASE_OK) dbSaveAds(state.ads, config).catch(console.error);
  } catch (err) {
    const msg = err.name === "AbortError"
      ? "Timeout dépassé — essaie avec moins de formats."
      : `Erreur : ${err.message}. Le backend est-il démarré ?`;
    setStatus(status, msg, "error");
    if (progress) progress.hide();
    checkHealth();
  } finally {
    if (progressInterval) clearInterval(progressInterval);
    btn.disabled = false;
    btn.textContent = "Générer les publicités";
  }
}

// ---------------------------------------------------------------------------
// Render ads
// ---------------------------------------------------------------------------
const SOURCE_LABELS = { none: "Couleurs", stock: "Stock", ai: "IA" };

function renderAds(ads) {
  const grid = $("#ads-grid");
  if (!ads.length) {
    grid.innerHTML = `<div class="empty-state"><p>Aucun visuel généré.</p></div>`;
    return;
  }
  grid.innerHTML = "";
  ads.forEach((ad, i) => {
    const sourceLabel = SOURCE_LABELS[ad.source] || "";
    const card = document.createElement("div");
    card.className = "ad-card";
    card.innerHTML = `
      <div class="ad-img-wrap">
        <img src="data:image/png;base64,${ad.image_b64}" alt="${ad.format} v${ad.variant}" loading="lazy" />
        <span class="source-badge src-${ad.source}">${sourceLabel}</span>
        <button class="ad-zoom-btn" title="Aperçu plein écran">⤢</button>
      </div>
      <div class="ad-meta">
        <div class="ad-label">
          <strong>${ad.format}</strong>
          ${ad.width}×${ad.height} · V${ad.variant}
        </div>
        <button class="btn btn-secondary btn-sm" title="Télécharger" onclick="downloadAd(${i})">↓</button>
      </div>`;
    card.querySelector(".ad-zoom-btn").addEventListener("click", () => openLightbox(i));
    card.querySelector("img").addEventListener("click", () => openLightbox(i));
    grid.appendChild(card);
  });
}

function downloadAd(index) {
  const ad = state.ads[index];
  const a = document.createElement("a");
  a.href = `data:image/png;base64,${ad.image_b64}`;
  a.download = `loops-${ad.format}-v${ad.variant}.png`;
  a.click();
}

function downloadAll() {
  state.ads.forEach((_, i) => {
    setTimeout(() => downloadAd(i), i * 300);
  });
}

// ---------------------------------------------------------------------------
// In-memory session history
// ---------------------------------------------------------------------------
function pushHistory(ads, config) {
  state.history.unshift({ ads, config, source: state.imageSource, ts: Date.now() });
  if (state.history.length > 3) state.history.pop();
  renderHistory();
}

function renderHistory() {
  const section = $("#history-section");
  if (!state.history.length) { section.style.display = "none"; return; }
  section.style.display = "block";

  const list = $("#history-list");
  list.innerHTML = "";
  state.history.forEach((session, si) => {
    const time = new Date(session.ts).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
    const row = document.createElement("div");
    row.className = "history-row";
    const thumbs = session.ads.slice(0, 3).map((ad) =>
      `<img class="history-thumb" src="data:image/png;base64,${ad.image_b64}" title="${ad.format}" />`
    ).join("");
    row.innerHTML = `
      <div class="history-meta">
        <strong>${session.config.brand_name}</strong>
        <span>${time} · ${SOURCE_LABELS[session.source]}</span>
      </div>
      <div class="history-thumbs">${thumbs}</div>
      <button class="btn btn-secondary btn-sm" onclick="restoreSession(${si})">Restaurer</button>`;
    list.appendChild(row);
  });
}

function restoreSession(index) {
  const session = state.history[index];
  state.ads = session.ads;
  renderAds(state.ads);
  $("#btn-download-all").style.display = state.ads.length > 1 ? "inline-flex" : "none";
  showPage("generate");
}

// ---------------------------------------------------------------------------
// DB history (Supabase — chargé au login)
// ---------------------------------------------------------------------------
function renderDBHistory(dbAds) {
  if (!dbAds.length) return;
  const section = $("#history-section");
  section.style.display = "block";

  const list = $("#history-list");

  const sep = document.createElement("div");
  sep.className = "section-header";
  sep.style.cssText = "margin-top:20px;padding-top:16px;border-top:1px solid var(--border);";
  sep.innerHTML = `<h2 style="font-size:0.85rem;color:var(--text-muted);">Créations sauvegardées</h2>`;
  list.appendChild(sep);

  dbAds.forEach(ad => {
    const date = new Date(ad.created_at).toLocaleDateString("fr-FR", {
      day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit",
    });
    const row = document.createElement("div");
    row.className = "history-row";
    row.innerHTML = `
      <div class="history-meta">
        <strong>${ad.brand_name || "Sans nom"}</strong>
        <span>${date} · ${SOURCE_LABELS[ad.source] || ad.source} · ${ad.format}</span>
      </div>
      <img class="history-thumb" src="${ad.image_url}" alt="${ad.format}" />
      <a href="${ad.image_url}" download="${ad.brand_name || "loops"}-${ad.format}.png"
         class="btn btn-secondary btn-sm">↓</a>`;
    list.appendChild(row);
  });
}

// ---------------------------------------------------------------------------
// Analysis
// ---------------------------------------------------------------------------
async function loadAnalysis() {
  const status = $("#analyze-status");
  const container = $("#analysis-container");
  const config = getBrandConfig();

  setStatus(status, "Analyse du secteur en cours…", "loading");
  container.innerHTML = "";

  try {
    const res = await fetch(`${API}/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(config),
    });
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    state.analysis = data;
    renderAnalysis(data);
    setStatus(status, "", "");
  } catch (err) {
    setStatus(status, `Erreur : ${err.message}. Le backend est-il démarré ?`, "error");
    checkHealth();
  }
}

function renderAnalysis(data) {
  const container = $("#analysis-container");
  const hooksHtml    = data.top_hooks.map((h) => `<span class="tag">${h}</span>`).join("");
  const ctasHtml     = data.top_ctas.map((c) => `<span class="tag">${c}</span>`).join("");
  const insightsHtml = data.insights.map((i) => `<li>${i}</li>`).join("");
  const compsHtml    = data.competitor_ads.map((c) => `
    <tr>
      <td>${c.brand}</td>
      <td>${c.hook}</td>
      <td>${c.cta}</td>
      <td class="roas-cell">${c.roas}x</td>
    </tr>`).join("");

  container.innerHTML = `
    <div class="insights-grid">
      <div class="insight-card">
        <h4>ROAS moyen secteur</h4>
        <div class="roas-badge">× ${data.avg_roas}</div>
      </div>
      <div class="insight-card">
        <h4>Hooks qui convertissent</h4>
        <div class="tag-list">${hooksHtml}</div>
      </div>
      <div class="insight-card">
        <h4>CTAs performants</h4>
        <div class="tag-list">${ctasHtml}</div>
      </div>
      <div class="insight-card">
        <h4>Insights clés</h4>
        <ul class="insight-text">${insightsHtml}</ul>
      </div>
    </div>
    <div class="card" style="margin-top:20px;">
      <h3>Publicités concurrentes actives</h3>
      <table class="comp-table">
        <thead><tr><th>Marque</th><th>Hook</th><th>CTA</th><th>ROAS estimé</th></tr></thead>
        <tbody>${compsHtml}</tbody>
      </table>
    </div>`;
}

// ---------------------------------------------------------------------------
// Suggest copy
// ---------------------------------------------------------------------------
async function suggestCopy() {
  const config = getBrandConfig();
  try {
    const res = await fetch(`${API}/suggest`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(config),
    });
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    $("#tagline").value = data.suggested_tagline;
    $("#cta").value = data.suggested_cta;
    saveBrandConfig();
    if (data.tip) notify("Conseil : " + data.tip, "info");
  } catch (err) {
    notify("Erreur : " + err.message, "error");
    checkHealth();
  }
}

// ---------------------------------------------------------------------------
// Auth UI helpers
// ---------------------------------------------------------------------------
function showApp(user) {
  $("#auth-overlay").style.display = "none";
  $("#app-root").style.display = "";

  const userEl = $("#header-user");
  userEl.innerHTML = `
    <span class="user-email">${user.email}</span>
    <button class="btn btn-secondary btn-sm" id="btn-logout">Déconnexion</button>`;
  $("#btn-logout").addEventListener("click", async () => {
    await authSignOut();
  });

  if (!window._appInitialized) {
    window._appInitialized = true;
    initApp();
  }
}

function showAuthOverlay() {
  $("#auth-overlay").style.display = "flex";
  $("#app-root").style.display = "none";
}

async function loadUserData() {
  try {
    const cfg = await dbLoadBrandConfig();
    if (cfg) applyConfig(cfg);
  } catch (e) { console.error("[db] load config:", e); }

  try {
    const recentAds = await dbLoadRecentAds();
    if (recentAds.length) renderDBHistory(recentAds);
  } catch (e) { console.error("[db] load ads:", e); }
}

function setupAuthForm() {
  let mode = "login";

  $$(".auth-tab").forEach(tab => {
    tab.addEventListener("click", () => {
      mode = tab.dataset.tab;
      $$(".auth-tab").forEach(t => t.classList.toggle("active", t.dataset.tab === mode));
      $("#auth-submit").textContent = mode === "login" ? "Se connecter" : "Créer un compte";
      $("#auth-error").textContent = "";
    });
  });

  $("#auth-submit").addEventListener("click", async () => {
    const email    = $("#auth-email").value.trim();
    const password = $("#auth-password").value;
    const errEl    = $("#auth-error");
    const btn      = $("#auth-submit");

    if (!email || !password) { errEl.textContent = "Email et mot de passe requis."; return; }

    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span>';
    errEl.textContent = "";

    try {
      if (mode === "login") {
        await authSignIn(email, password);
      } else {
        const result = await authSignUp(email, password);
        if (!result.session) {
          errEl.style.color = "#4ade80";
          errEl.textContent = "Compte créé ! Vérifiez votre email pour confirmer.";
          btn.disabled = false;
          btn.textContent = "Créer un compte";
          return;
        }
      }
    } catch (err) {
      errEl.style.color = "#f87171";
      errEl.textContent = err.message;
      btn.disabled = false;
      btn.textContent = mode === "login" ? "Se connecter" : "Créer un compte";
    }
  });

  ["auth-email", "auth-password"].forEach(id => {
    $(`#${id}`).addEventListener("keydown", e => {
      if (e.key === "Enter") $("#auth-submit").click();
    });
  });
}

// ---------------------------------------------------------------------------
// Core app init (called after auth)
// ---------------------------------------------------------------------------
function initApp() {
  loadBrandConfig();
  initFormatButtons();
  checkHealth();
  setInterval(checkHealth, 30000);

  ["brand-name", "tagline", "description", "cta"].forEach(id => {
    $(`#${id}`).addEventListener("input", saveBrandConfig);
  });
  $("#sector").addEventListener("change", saveBrandConfig);

  $$("nav button").forEach(btn => {
    btn.addEventListener("click", () => {
      showPage(btn.dataset.page);
      if (btn.dataset.page === "analyze") loadAnalysis();
    });
  });

  $("#btn-generate").addEventListener("click", generateAds);
  $("#btn-suggest").addEventListener("click", suggestCopy);
  $("#btn-download-all").addEventListener("click", downloadAll);
  $("#btn-analyze-refresh").addEventListener("click", loadAnalysis);

  $("#lightbox").addEventListener("click", e => {
    if (e.target === $("#lightbox") || e.target.id === "lb-close") closeLightbox();
  });
  document.addEventListener("keydown", e => { if (e.key === "Escape") closeLightbox(); });

  showPage("generate");
}

// ---------------------------------------------------------------------------
// Bootstrap
// ---------------------------------------------------------------------------
document.addEventListener("DOMContentLoaded", () => {
  initFormatButtons();
  syncColor($("#primary-color"), $("#primary-hex"));
  syncColor($("#secondary-color"), $("#secondary-hex"));
  initSourceButtons();

  if (SUPABASE_OK) {
    setupAuthForm();
    initAuth(
      async (user) => {
        showApp(user);
        await loadUserData();
      },
      () => showAuthOverlay()
    );
  } else {
    // Pas de Supabase configuré — mode sans auth
    $("#auth-overlay").style.display = "none";
    $("#app-root").style.display = "";
    window._appInitialized = true;
    initApp();
  }
});
