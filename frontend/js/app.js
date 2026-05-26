const API = window.API_URL || "http://localhost:8765";
const SUPABASE_OK = !!(window.SUPABASE_URL && !window.SUPABASE_URL.includes("VOTRE-PROJET"));

const state = {
  formats: ["feed", "story", "banner"],
  selectedFormats: ["feed"],
  imageSource: "none",
  aiModel: "flux",
  stylePreset: "",
  fontFamily: "",
  variantsPerFormat: 1,
  mockMode: false,
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
  dot.className = "health-dot";
  dot.title = "Connexion au serveur…";
  try {
    const r = await fetch(`${API}/`, { signal: AbortSignal.timeout(10000) });
    if (r.ok) {
      dot.className = "health-dot online";
      dot.title = "Serveur actif";
    } else throw new Error();
  } catch {
    dot.className = "health-dot offline";
    dot.title = "Serveur indisponible";
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
    selectedFormats:    state.selectedFormats,
    imageSource:        state.imageSource,
    aiModel:            state.aiModel,
    stylePreset:        state.stylePreset,
    fontFamily:         state.fontFamily,
    variantsPerFormat:  state.variantsPerFormat,
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
    updateModelFieldVisibility();
  }
  if (cfg.aiModel) {
    state.aiModel = cfg.aiModel;
    $$(".model-btn").forEach(b => b.classList.toggle("selected", b.dataset.model === state.aiModel));
  }
  if (cfg.stylePreset !== undefined) {
    state.stylePreset = cfg.stylePreset;
    $$(".style-btn").forEach(b => b.classList.toggle("selected", b.dataset.style === state.stylePreset));
  }
  if (cfg.variantsPerFormat) {
    state.variantsPerFormat = cfg.variantsPerFormat;
    const sl = $("#variants-slider");
    if (sl) { sl.value = state.variantsPerFormat; $("#variants-label").textContent = state.variantsPerFormat; }
  }
  if (cfg.fontFamily !== undefined) {
    state.fontFamily = cfg.fontFamily;
    $$(".font-btn").forEach(b => b.classList.toggle("selected", b.dataset.font === state.fontFamily));
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
    updateColorPreview();
  });
  textInput.addEventListener("input", () => {
    if (/^#[0-9a-fA-F]{6}$/.test(textInput.value)) {
      colorInput.value = textInput.value;
      saveBrandConfig();
      updateColorPreview();
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
function updateModelFieldVisibility() {
  const f = $("#model-field");
  if (f) f.style.display = state.imageSource === "ai" ? "block" : "none";
}

function initSourceButtons() {
  $$(".source-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      $$(".source-btn").forEach((b) => b.classList.remove("selected"));
      btn.classList.add("selected");
      state.imageSource = btn.dataset.source;
      updateModelFieldVisibility();
      saveBrandConfig();
    });
  });
}

// ---------------------------------------------------------------------------
// Model selector
// ---------------------------------------------------------------------------
const MODELS = [
  { key: "flux",         icon: "⚡", label: "Schnell",  desc: "Rapide" },
  { key: "flux-pro",     icon: "✦",  label: "Pro",      desc: "Qualité" },
  { key: "flux-realism", icon: "📸", label: "Réaliste", desc: "Photo" },
  { key: "turbo",        icon: "🚀", label: "Turbo",    desc: "Ultra" },
];

function initModelButtons() {
  const grid = $("#model-grid");
  if (!grid) return;
  grid.innerHTML = "";
  MODELS.forEach(({ key, icon, label, desc }) => {
    const btn = document.createElement("div");
    btn.className = "model-btn" + (state.aiModel === key ? " selected" : "");
    btn.dataset.model = key;
    btn.innerHTML = `<span class="model-icon">${icon}</span><span class="model-label">${label}</span><span class="model-desc">${desc}</span>`;
    btn.addEventListener("click", () => {
      $$(".model-btn").forEach(b => b.classList.remove("selected"));
      btn.classList.add("selected");
      state.aiModel = key;
      saveBrandConfig();
    });
    grid.appendChild(btn);
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
    container.appendChild(wrap);
  }
  wrap.innerHTML = `<div class="progress-bar"><div class="progress-fill" style="width:0%"></div></div><div class="progress-label">Préparation…</div>`;
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
  state.ads = [];
  $("#btn-download-all").style.display = "none";
  $("#btn-download-zip").style.display = "none";
  $("#btn-mock-toggle").style.display = "none";

  const config = getBrandConfig();
  saveBrandConfig();
  const payload = {
    ...config,
    formats: state.selectedFormats,
    variants_per_format: state.variantsPerFormat,
    image_source: state.imageSource,
    ai_model: state.aiModel,
    style_preset: state.stylePreset,
    font_family: state.fontFamily || "",
    logo_b64: uploads.logo.b64 || "",
    product_b64: uploads.product.b64 || "",
  };

  const isAI = state.imageSource === "ai";
  const totalAds = state.selectedFormats.length * state.variantsPerFormat;
  const MODEL_TIMES = { "flux": 8, "flux-pro": 18, "flux-realism": 12, "turbo": 5 };
  const secPerAd = MODEL_TIMES[state.aiModel] || 15;
  const timeoutMs = isAI ? totalAds * secPerAd * 2000 + 30000 : 60000;

  const progress = showProgress(btn.closest(".card"), totalAds);

  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);

    const res = await fetch(`${API}/generate/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: controller.signal,
    });
    if (!res.ok) throw new Error(await res.text());

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const chunks = buffer.split("\n\n");
      buffer = chunks.pop();
      for (const chunk of chunks) {
        if (!chunk.startsWith("data: ")) continue;
        const raw = chunk.slice(6).trim();
        if (raw === "[DONE]") break;
        try {
          const ad = JSON.parse(raw);
          if (ad.error) { console.warn("[stream]", ad.error); continue; }
          ad.source = state.imageSource;
          state.ads.push(ad);
          appendAd(ad, state.ads.length - 1);
          progress.update(ad.done, `${ad.done} / ${ad.total} visuel${ad.done > 1 ? "s" : ""} généré${ad.done > 1 ? "s" : ""}`);
        } catch {}
      }
    }
    clearTimeout(timer);

    if (!state.ads.length) throw new Error("Aucun visuel généré.");
    pushHistory(state.ads, config);
    setStatus(status, "", "");
    const hasMany = state.ads.length > 1;
    $("#btn-download-all").style.display = hasMany ? "inline-flex" : "none";
    $("#btn-download-zip").style.display = hasMany ? "inline-flex" : "none";
    $("#btn-mock-toggle").style.display = "inline-flex";
    progress.update(totalAds, "Terminé !");
    setTimeout(() => progress.hide(), 2000);

    if (SUPABASE_OK) dbSaveAds(state.ads, config).catch(console.error);
  } catch (err) {
    const msg = err.name === "AbortError"
      ? "Le serveur met trop de temps à répondre. Patiente quelques secondes puis réessaie."
      : "Le serveur est en train de démarrer. Attends 20-30 secondes puis réessaie.";
    status.style.display = "block";
    status.className = "status error";
    status.innerHTML = `${msg} <button class="btn btn-secondary btn-sm" style="margin-left:8px;" onclick="generateAds()">↺ Réessayer</button>`;
    progress.hide();
    checkHealth();
  } finally {
    btn.disabled = false;
    btn.textContent = "Générer les publicités";
  }
}

// ---------------------------------------------------------------------------
// Render ads
// ---------------------------------------------------------------------------
const SOURCE_LABELS = { none: "Couleurs", stock: "Stock", ai: "IA" };

function _buildAdCard(ad, i) {
  const sourceLabel = SOURCE_LABELS[ad.source] || "";
  const score = computePerformanceScore(getBrandConfig(), ad);
  const scoreColor = score >= 80 ? "#22c55e" : score >= 60 ? "#f59e0b" : "#ef4444";
  const card = document.createElement("div");
  card.className = "ad-card";
  card.dataset.format = ad.format;
  card.innerHTML = `
    <div class="ad-img-wrap">
      <img src="data:image/png;base64,${ad.image_b64}" alt="${ad.format} v${ad.variant}" loading="lazy" />
      <span class="source-badge src-${ad.source}">${sourceLabel}</span>
      <button class="ad-zoom-btn" title="Aperçu plein écran">⤢</button>
      <button class="ad-regen-btn" title="Régénérer ce visuel">↺</button>
    </div>
    <div class="ad-meta">
      <div class="ad-label">
        <strong>${ad.format}</strong>
        ${ad.width}×${ad.height} · V${ad.variant}
      </div>
      <div style="display:flex;align-items:center;gap:6px;">
        <span class="perf-badge" style="background:${scoreColor}22;color:${scoreColor};border:1px solid ${scoreColor}44;" title="Score de performance estimé">${score}</span>
        <button class="btn btn-secondary btn-sm" title="Télécharger" onclick="downloadAd(${i})">↓</button>
      </div>
    </div>`;
  card.querySelector(".ad-zoom-btn").addEventListener("click", () => openLightbox(i));
  card.querySelector("img").addEventListener("click", () => openLightbox(i));
  card.querySelector(".ad-regen-btn").addEventListener("click", () => regenAd(i));
  return card;
}

function appendAd(ad, i) {
  const grid = $("#ads-grid");
  if (!grid.querySelector(".ad-card")) grid.innerHTML = "";
  const card = _buildAdCard(ad, i);
  grid.appendChild(card);
  if (state.mockMode) applyMockClasses();
}

async function regenAd(index) {
  const ad = state.ads[index];
  if (!ad) return;
  const card = document.querySelectorAll(".ad-card")[index];
  if (!card) return;
  const regenBtn = card.querySelector(".ad-regen-btn");
  regenBtn.classList.add("spinning");
  regenBtn.disabled = true;

  const config = getBrandConfig();
  const payload = {
    ...config,
    formats: [ad.format],
    variants_per_format: 1,
    image_source: state.imageSource,
    ai_model: state.aiModel,
    style_preset: state.stylePreset,
    font_family: state.fontFamily || "",
    logo_b64: uploads.logo.b64 || "",
    product_b64: uploads.product.b64 || "",
  };

  try {
    const res = await fetch(`${API}/generate/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout(60000),
    });
    if (!res.ok) throw new Error(await res.text());

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const chunks = buffer.split("\n\n");
      buffer = chunks.pop();
      for (const chunk of chunks) {
        if (!chunk.startsWith("data: ")) continue;
        const raw = chunk.slice(6).trim();
        if (raw === "[DONE]") break;
        try {
          const newAd = JSON.parse(raw);
          if (newAd.error || !newAd.image_b64) continue;
          newAd.source = state.imageSource;
          newAd.variant = ad.variant;
          state.ads[index] = newAd;
          const newCard = _buildAdCard(newAd, index);
          card.replaceWith(newCard);
          if (state.mockMode) applyMockClasses();
          return;
        } catch {}
      }
    }
  } catch (err) {
    notify(`Regen échoué : ${err.message}`, "error");
    regenBtn.classList.remove("spinning");
    regenBtn.disabled = false;
  }
}

function renderAds(ads) {
  const grid = $("#ads-grid");
  if (!ads.length) {
    grid.innerHTML = `<div class="empty-state"><p>Aucun visuel généré.</p></div>`;
    return;
  }
  grid.innerHTML = "";
  ads.forEach((ad, i) => grid.appendChild(_buildAdCard(ad, i)));
  applyMockClasses();
}

function _slugBrand() {
  return ($("#brand-name")?.value || "brand").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "brand";
}

function downloadAd(index) {
  const ad = state.ads[index];
  const a = document.createElement("a");
  a.href = `data:image/png;base64,${ad.image_b64}`;
  a.download = `${_slugBrand()}-${ad.format}-v${ad.variant}.png`;
  a.click();
}

function downloadAll() {
  state.ads.forEach((_, i) => {
    setTimeout(() => downloadAd(i), i * 300);
  });
}

async function downloadAllZip() {
  if (!window.JSZip) { notify("JSZip non disponible", "error"); return; }
  const btn = $("#btn-download-zip");
  btn.disabled = true;
  btn.textContent = "…";
  const zip = new window.JSZip();
  state.ads.forEach((ad) => {
    const binary = atob(ad.image_b64);
    const bytes = new Uint8Array(binary.length);
    for (let j = 0; j < binary.length; j++) bytes[j] = binary.charCodeAt(j);
    zip.file(`loops-${ad.format}-v${ad.variant}.png`, bytes);
  });
  const blob = await zip.generateAsync({ type: "blob" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `${_slugBrand()}-${Date.now()}.zip`;
  a.click();
  URL.revokeObjectURL(a.href);
  btn.disabled = false;
  btn.textContent = "↓ ZIP";
}

// ---------------------------------------------------------------------------
// Mock contextuel
// ---------------------------------------------------------------------------
function toggleMock() {
  state.mockMode = !state.mockMode;
  const btn = $("#btn-mock-toggle");
  btn.classList.toggle("active", state.mockMode);
  btn.textContent = state.mockMode ? "⬛ Mock ON" : "⬜ Mock";
  applyMockClasses();
}

function applyMockClasses() {
  document.querySelectorAll(".ad-card").forEach(card => {
    const fmt = card.dataset.format;
    card.classList.remove("mock-phone", "mock-browser");
    if (!state.mockMode) return;
    if (fmt === "story" || fmt === "feed") {
      card.classList.add("mock-phone");
    } else if (fmt === "banner") {
      card.classList.add("mock-browser");
      if (!card.querySelector(".browser-bar")) {
        const bar = document.createElement("div");
        bar.className = "browser-bar";
        bar.innerHTML = `<span class="browser-dot" style="background:#ff5f56;"></span><span class="browser-dot" style="background:#ffbd2e;"></span><span class="browser-dot" style="background:#27c93f;"></span>`;
        card.insertBefore(bar, card.firstChild);
      }
    }
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
  const isAI = data.source === "ai";
  const sourceBadge = isAI
    ? `<span class="copy-source-badge" style="margin-left:8px;">✦ IA</span>`
    : `<span class="copy-source-badge src-static" style="margin-left:8px;">Statique</span>`;

  const hooksHtml    = data.top_hooks.map(h => `<span class="tag">${h}</span>`).join("");
  const ctasHtml     = data.top_ctas.map(c => `<span class="tag">${c}</span>`).join("");
  const insightsHtml = data.insights.map(i => `<li>${i}</li>`).join("");
  const compsHtml    = data.competitor_ads.map(c => `
    <tr>
      <td>${c.brand}</td>
      <td>${c.hook}</td>
      <td>${c.cta}</td>
      <td class="roas-cell">${c.roas}x</td>
    </tr>`).join("");

  container.innerHTML = `
    <div class="insights-grid">
      <div class="insight-card">
        <h4>ROAS moyen secteur ${sourceBadge}</h4>
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
  const btn = $("#btn-suggest");
  const config = getBrandConfig();
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span>';
  try {
    const res = await fetch(`${API}/suggest`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(config),
    });
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    if (data.variants && data.variants.length) {
      renderCopyVariants(data);
    } else {
      $("#tagline").value = data.suggested_tagline;
      $("#cta").value = data.suggested_cta;
      saveBrandConfig();
      if (data.tip) notify("Conseil : " + data.tip, "info");
    }
  } catch (err) {
    notify("Erreur : " + err.message, "error");
    checkHealth();
  } finally {
    btn.disabled = false;
    btn.innerHTML = "✦ Suggérer un copy";
  }
}

function renderCopyVariants(data) {
  const panel = $("#copy-variants-panel");
  if (!panel) return;
  const isAI = data.source === "ai";
  const badgeClass = isAI ? "" : "src-static";
  const badgeLabel = isAI ? "✦ IA" : "Statique";

  panel.innerHTML = `
    <div class="copy-variants-header">
      <span class="copy-variants-title">
        5 propositions
        <span class="copy-source-badge ${badgeClass}">${badgeLabel}</span>
      </span>
      <button class="copy-variants-close" title="Fermer">✕</button>
    </div>
    ${data.variants.map((v, i) => `
      <div class="copy-variant-item" data-index="${i}">
        <div class="variant-text">
          <div class="variant-tagline">${v.tagline}</div>
          <div class="variant-cta">CTA : ${v.cta}</div>
        </div>
        <span class="variant-apply">Appliquer →</span>
      </div>
    `).join("")}
    ${data.tip ? `<div class="copy-tip">💡 ${data.tip}</div>` : ""}
  `;
  panel.style.display = "flex";

  panel.querySelector(".copy-variants-close").addEventListener("click", () => {
    panel.style.display = "none";
  });

  panel.querySelectorAll(".copy-variant-item").forEach(item => {
    item.addEventListener("click", () => {
      const i = parseInt(item.dataset.index);
      const v = data.variants[i];
      $("#tagline").value = v.tagline;
      $("#cta").value = v.cta;
      saveBrandConfig();
      updateColorPreview();
      panel.querySelectorAll(".copy-variant-item").forEach(el => el.classList.remove("applied"));
      item.classList.add("applied");
      item.querySelector(".variant-apply").textContent = "✓ Appliqué";
    });
  });
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
  let mode = "login"; // login | signup | forgot | recovery

  const LABELS = {
    login:    "Se connecter",
    signup:   "Créer un compte",
    forgot:   "Envoyer le lien",
    recovery: "Définir le mot de passe",
  };

  function setMode(newMode) {
    mode = newMode;
    const isForgot   = mode === "forgot";
    const isRecovery = mode === "recovery";

    $("#auth-tabs-wrap").style.display      = (isForgot || isRecovery) ? "none" : "";
    $("#auth-password").style.display       = isRecovery ? "none" : "";
    $("#auth-new-password").style.display   = isRecovery ? "" : "none";
    $("#auth-forgot").style.display         = (isForgot || isRecovery) ? "none" : "";
    $("#auth-back").style.display           = isForgot ? "" : "none";
    $("#auth-submit").textContent           = LABELS[mode];
    $("#auth-error").textContent            = "";
    $("#auth-error").style.color            = "#f87171";

    if (isForgot) {
      $(".auth-title").textContent = "Mot de passe oublié";
      $(".auth-sub").textContent   = "Entre ton email pour recevoir un lien de réinitialisation.";
    } else if (isRecovery) {
      $(".auth-title").textContent = "Nouveau mot de passe";
      $(".auth-sub").textContent   = "Choisis un nouveau mot de passe pour ton compte.";
    } else {
      $(".auth-title").textContent = "Bienvenue";
      $(".auth-sub").textContent   = "Connecte-toi pour sauvegarder tes créations";
      $$(".auth-tab").forEach(t => t.classList.toggle("active", t.dataset.tab === mode));
    }
  }

  window._setAuthMode = setMode;

  $$(".auth-tab").forEach(tab => {
    tab.addEventListener("click", () => setMode(tab.dataset.tab));
  });

  $("#auth-forgot").addEventListener("click", (e) => {
    e.preventDefault();
    setMode("forgot");
  });

  $("#auth-back").addEventListener("click", (e) => {
    e.preventDefault();
    setMode("login");
  });

  $("#auth-submit").addEventListener("click", async () => {
    const email    = $("#auth-email").value.trim();
    const password = $("#auth-password").value;
    const errEl    = $("#auth-error");
    const btn      = $("#auth-submit");

    errEl.textContent = "";
    errEl.style.color = "#f87171";
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span>';

    try {
      if (mode === "forgot") {
        if (!email) { errEl.textContent = "Email requis."; return; }
        await authResetPassword(email);
        errEl.style.color = "#4ade80";
        errEl.textContent = "Lien envoyé ! Vérifie ta boîte mail.";
        return;
      }

      if (mode === "recovery") {
        const newPass = $("#auth-new-password").value;
        if (!newPass || newPass.length < 6) { errEl.textContent = "Mot de passe trop court (6 caractères min)."; return; }
        await authUpdatePassword(newPass);
        history.replaceState(null, "", window.location.pathname);
        return;
      }

      if (!email || !password) { errEl.textContent = "Email et mot de passe requis."; return; }

      if (mode === "login") {
        await authSignIn(email, password);
      } else {
        const result = await authSignUp(email, password);
        if (!result.session) {
          errEl.style.color = "#4ade80";
          errEl.textContent = "Compte créé ! Vérifiez votre email pour confirmer.";
          return;
        }
      }
    } catch (err) {
      errEl.textContent = err.message;
    } finally {
      btn.disabled = false;
      btn.textContent = LABELS[mode] || LABELS.login;
    }
  });

  ["auth-email", "auth-password", "auth-new-password"].forEach(id => {
    $(`#${id}`).addEventListener("keydown", e => {
      if (e.key === "Enter") $("#auth-submit").click();
    });
  });
}

// ---------------------------------------------------------------------------
// Performance score heuristic
// ---------------------------------------------------------------------------
function hexToRgb(hex) {
  const r = parseInt(hex.slice(1,3),16), g = parseInt(hex.slice(3,5),16), b = parseInt(hex.slice(5,7),16);
  return [r, g, b];
}

function relativeLuminance([r, g, b]) {
  return [r, g, b].reduce((acc, c, i) => {
    const s = c / 255;
    const lin = s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
    return acc + lin * [0.2126, 0.7152, 0.0722][i];
  }, 0);
}

function contrastRatio(hex1, hex2) {
  const l1 = relativeLuminance(hexToRgb(hex1));
  const l2 = relativeLuminance(hexToRgb(hex2));
  return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
}

function computePerformanceScore(config, ad) {
  let score = 40;

  // Tagline (5-10 words ideal)
  const tw = (config.tagline || "").trim().split(/\s+/).length;
  if (tw >= 5 && tw <= 10) score += 18;
  else if (tw >= 3 && tw <= 12) score += 10;

  // CTA (2-4 words ideal)
  const cw = (config.cta || "").trim().split(/\s+/).length;
  if (cw >= 2 && cw <= 4) score += 12;
  else if (cw === 1) score += 6;

  // Description present
  if ((config.description || "").length > 15) score += 8;

  // Color contrast
  try {
    const ratio = contrastRatio(config.primary_color, config.secondary_color);
    if (ratio >= 4.5) score += 15;
    else if (ratio >= 3) score += 8;
    else if (ratio >= 2) score += 3;
  } catch {}

  // Format bonus (story outperforms)
  if (ad.format === "story") score += 5;
  if (ad.format === "feed")  score += 3;

  // Logo / product uploaded
  if (uploads.logo.b64)    score += 4;
  if (uploads.product.b64) score += 4;

  return Math.min(100, Math.max(10, score));
}

// ---------------------------------------------------------------------------
// Google Fonts picker
// ---------------------------------------------------------------------------
const FONTS_LIST = [
  { key: "",            label: "Système",   css: "inherit" },
  { key: "poppins",     label: "Poppins",   css: "'Poppins', sans-serif" },
  { key: "montserrat",  label: "Montserrat",css: "'Montserrat', sans-serif" },
  { key: "playfair",    label: "Playfair",  css: "'Playfair Display', serif" },
  { key: "oswald",      label: "Oswald",    css: "'Oswald', sans-serif" },
  { key: "raleway",     label: "Raleway",   css: "'Raleway', sans-serif" },
];

const GFONTS_IMPORT = "https://fonts.googleapis.com/css2?family=Poppins:wght@700&family=Montserrat:wght@700&family=Playfair+Display:wght@700&family=Oswald:wght@700&family=Raleway:wght@700&display=swap";

function initFontPicker() {
  // Inject Google Fonts stylesheet once
  if (!document.getElementById("gfonts-link")) {
    const link = document.createElement("link");
    link.id = "gfonts-link";
    link.rel = "stylesheet";
    link.href = GFONTS_IMPORT;
    document.head.appendChild(link);
  }

  const container = $("#font-picker");
  if (!container) return;
  container.innerHTML = "";
  FONTS_LIST.forEach(f => {
    const btn = document.createElement("div");
    btn.className = "font-btn" + (state.fontFamily === f.key ? " selected" : "");
    btn.dataset.font = f.key;
    btn.style.fontFamily = f.css;
    btn.textContent = f.label;
    btn.addEventListener("click", () => {
      $$(".font-btn").forEach(b => b.classList.remove("selected"));
      btn.classList.add("selected");
      state.fontFamily = f.key;
      saveBrandConfig();
      updateColorPreview();
    });
    container.appendChild(btn);
  });
}

function getFontCss() {
  return FONTS_LIST.find(f => f.key === (state.fontFamily || ""))?.css || "inherit";
}

// ---------------------------------------------------------------------------
// Aperçu couleurs live
// ---------------------------------------------------------------------------
function updateColorPreview() {
  const preview = $("#color-preview");
  if (!preview) return;
  const brand   = $("#brand-name")?.value || "Brand";
  const tagline = $("#tagline")?.value   || "Your tagline here";
  const cta     = $("#cta")?.value       || "Shop Now";
  const primary   = $("#primary-hex")?.value   || "#000000";
  const secondary = $("#secondary-hex")?.value || "#e94560";
  const p = hexToRgb(primary), s = hexToRgb(secondary);
  if (!p || !s) return;

  const ctaText = relativeLuminance(s) > 0.25 ? "#111111" : "#ffffff";
  const fontCss = getFontCss();

  preview.style.background = "#ffffff";
  preview.style.borderColor = "var(--border)";

  preview.innerHTML = `
    <div style="
      width:100%;min-height:110px;height:100%;
      padding:12px 14px;
      position:relative;overflow:hidden;
      display:flex;flex-direction:column;justify-content:space-between;
      font-family:${fontCss};
    ">
      <div style="position:absolute;top:-20px;right:-20px;width:64px;height:64px;
           border-radius:50%;background:${secondary};opacity:.18;"></div>
      <div>
        <div style="font-size:.62rem;font-weight:800;letter-spacing:.08em;
             color:${secondary};text-transform:uppercase;margin-bottom:3px;">${brand}</div>
        <div style="width:18px;height:2px;background:${secondary};margin-bottom:6px;"></div>
        <div style="font-size:.68rem;font-weight:600;color:#111827;
             line-height:1.3;">${tagline}</div>
      </div>
      <div>
        <span style="display:inline-block;background:${secondary};color:${ctaText};
          font-size:.58rem;font-weight:700;padding:4px 10px;border-radius:20px;
          letter-spacing:.04em;text-transform:uppercase;">${cta}</span>
      </div>
    </div>`;
}

// ---------------------------------------------------------------------------
// Advanced section toggle
// ---------------------------------------------------------------------------
function initAdvancedToggle() {
  const btn = $("#btn-advanced-toggle");
  const section = $("#advanced-section");
  if (!btn || !section) return;
  const open = localStorage.getItem("loops_advanced_open") === "1";
  if (open) { section.style.display = "block"; btn.classList.add("open"); }
  btn.addEventListener("click", () => {
    const isOpen = section.style.display !== "none";
    section.style.display = isOpen ? "none" : "block";
    btn.classList.toggle("open", !isOpen);
    localStorage.setItem("loops_advanced_open", isOpen ? "0" : "1");
  });
}

// ---------------------------------------------------------------------------
// Style presets
// ---------------------------------------------------------------------------
function initStyleButtons() {
  $$(".style-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      $$(".style-btn").forEach(b => b.classList.remove("selected"));
      btn.classList.add("selected");
      state.stylePreset = btn.dataset.style;
      saveBrandConfig();
    });
  });
}

// ---------------------------------------------------------------------------
// Variants slider
// ---------------------------------------------------------------------------
function initVariantsSlider() {
  const sl = $("#variants-slider");
  const lbl = $("#variants-label");
  if (!sl) return;
  sl.addEventListener("input", () => {
    state.variantsPerFormat = parseInt(sl.value);
    lbl.textContent = sl.value;
    saveBrandConfig();
  });
}

// ---------------------------------------------------------------------------
// Brand Kit
// ---------------------------------------------------------------------------
const KIT_KEY = "loops_brand_kits";

function getBrandKits() {
  try { return JSON.parse(localStorage.getItem(KIT_KEY) || "{}"); } catch { return {}; }
}

function saveBrandKit() {
  const name = $("#kit-name").value.trim();
  if (!name) { notify("Donne un nom au kit", "error"); return; }
  const kits = getBrandKits();
  kits[name] = {
    ...getBrandConfig(),
    selectedFormats: state.selectedFormats,
    imageSource: state.imageSource,
    aiModel: state.aiModel,
    stylePreset: state.stylePreset,
    variantsPerFormat: state.variantsPerFormat,
  };
  localStorage.setItem(KIT_KEY, JSON.stringify(kits));
  $("#kit-name").value = "";
  renderBrandKits();
  notify(`Kit "${name}" sauvegardé`, "info");
}

function deleteBrandKit(name) {
  const kits = getBrandKits();
  delete kits[name];
  localStorage.setItem(KIT_KEY, JSON.stringify(kits));
  renderBrandKits();
}

const SECTOR_LABELS_FR = { beaute: "Beauté", ecommerce: "E-com", sante: "Santé", autre: "Autre" };

function renderBrandKits() {
  const list = $("#kit-list");
  if (!list) return;
  const kits = getBrandKits();
  const names = Object.keys(kits);
  list.innerHTML = names.length
    ? ""
    : `<p style="font-size:0.78rem;color:var(--text-muted);text-align:center;padding:8px 0;">Aucun kit sauvegardé</p>`;

  names.forEach(name => {
    const kit = kits[name];
    const item = document.createElement("div");
    item.className = "kit-item";
    item.innerHTML = `
      <div class="kit-swatch-row">
        <div class="kit-swatch" style="background:${kit.primary_color || "#1a1a2e"};"></div>
        <div class="kit-swatch" style="background:${kit.secondary_color || "#e94560"};"></div>
      </div>
      <span class="kit-name">${name}</span>
      <span class="kit-sector">${SECTOR_LABELS_FR[kit.sector] || kit.sector}</span>
      <button class="kit-delete" title="Supprimer">✕</button>`;
    item.addEventListener("click", e => {
      if (e.target.classList.contains("kit-delete")) { deleteBrandKit(name); return; }
      applyConfig(kit);
      saveBrandConfig();
      notify(`Kit "${name}" chargé`, "info");
    });
    list.appendChild(item);
  });
}

// ---------------------------------------------------------------------------
// Color Thief — extraction auto depuis logo
// ---------------------------------------------------------------------------
function extractColorsFromLogo(imgEl) {
  if (!window.ColorThief) return;
  try {
    const ct = new window.ColorThief();
    const dominant = ct.getColor(imgEl);
    const palette  = ct.getPalette(imgEl, 5);

    const domHex = rgbToHex(...dominant);

    // Palette color most contrasting against dominant
    let best = palette[1] || dominant;
    let maxDist = 0;
    palette.forEach(c => {
      const d = colorDistance(dominant, c);
      if (d > maxDist) { maxDist = d; best = c; }
    });
    const secHex = rgbToHex(...best);

    $("#primary-hex").value   = domHex;
    $("#primary-color").value = domHex;
    $("#secondary-hex").value = secHex;
    $("#secondary-color").value = secHex;
    saveBrandConfig();

    notify("Couleurs extraites depuis le logo ✓", "info");
  } catch (e) {
    console.warn("[ColorThief]", e);
  }
}

function rgbToHex(r, g, b) {
  return "#" + [r, g, b].map(v => v.toString(16).padStart(2, "0")).join("");
}

function colorDistance(a, b) {
  return Math.sqrt((a[0]-b[0])**2 + (a[1]-b[1])**2 + (a[2]-b[2])**2);
}

// ---------------------------------------------------------------------------
// Templates par secteur
// ---------------------------------------------------------------------------
const TEMPLATES = [
  {
    name: "GlowSkin",
    icon: "✨",
    sector: "beaute",
    primary_color: "#1a0a2e",
    secondary_color: "#f472b6",
    tagline: "90% ont vu des résultats en 14 jours",
    description: "Formule clean testée par des dermatologues qui transforme ta peau.",
    cta: "Découvrir",
  },
  {
    name: "FitPulse",
    icon: "💪",
    sector: "sante",
    primary_color: "#0f2027",
    secondary_color: "#00c9a7",
    tagline: "Sentez-vous plus fort en 7 jours",
    description: "Compléments prouvés cliniquement, approuvés par +100k athlètes.",
    cta: "Commencer",
  },
  {
    name: "UrbanDrop",
    icon: "🛍",
    sector: "ecommerce",
    primary_color: "#18181b",
    secondary_color: "#f59e0b",
    tagline: "Drop limité — plus que 48h",
    description: "Collab streetwear exclusive. Livraison offerte dès 50€.",
    cta: "Saisir l'offre",
  },
  {
    name: "NovaSaaS",
    icon: "⚡",
    sector: "autre",
    primary_color: "#0d1b2a",
    secondary_color: "#7c3aed",
    tagline: "Multipliez votre productivité par 10.",
    description: "La plateforme tout-en-un qu'utilisent les meilleures équipes.",
    cta: "Essayer",
  },
  {
    name: "PureBrew",
    icon: "☕",
    sector: "ecommerce",
    primary_color: "#2c1a0e",
    secondary_color: "#d97706",
    tagline: "Café de spécialité, livré chaque semaine",
    description: "Grains d'origine unique torréfiés frais, livrés chez vous.",
    cta: "Essayer la box",
  },
  {
    name: "ZenMind",
    icon: "🧘",
    sector: "sante",
    primary_color: "#0f1f17",
    secondary_color: "#22c55e",
    tagline: "Dormez mieux. Moins de stress. Vivez plus.",
    description: "Adaptogènes naturels approuvés par la science, adoptés par des milliers.",
    cta: "En savoir plus",
  },
];

function initTemplates() {
  const grid = $("#template-grid");
  if (!grid) return;
  grid.innerHTML = "";
  TEMPLATES.forEach(t => {
    const btn = document.createElement("div");
    btn.className = "template-btn";
    btn.innerHTML = `
      <div class="template-swatch" style="background:${t.secondary_color};"></div>
      <div class="template-info">
        <div class="template-name">${t.icon} ${t.name}</div>
        <div class="template-hook">${t.tagline}</div>
      </div>`;
    btn.addEventListener("click", () => {
      applyConfig({
        brand_name:      t.name,
        sector:          t.sector,
        tagline:         t.tagline,
        description:     t.description,
        cta:             t.cta,
        primary_color:   t.primary_color,
        secondary_color: t.secondary_color,
      });
      saveBrandConfig();
      notify(`Template "${t.name}" appliqué`, "info");
    });
    grid.appendChild(btn);
  });
}

// ---------------------------------------------------------------------------
// Upload logo / produit
// ---------------------------------------------------------------------------
const uploads = { logo: { b64: "" }, product: { b64: "" } };

function initUploadZone(type) {
  const zone      = $(`#${type}-drop`);
  const input     = $(`#${type}-input`);
  const ph        = $(`#${type}-placeholder`);
  const preview   = $(`#${type}-preview`);
  const img       = $(`#${type}-img`);

  zone.addEventListener("click", () => input.click());
  zone.addEventListener("dragover", e => { e.preventDefault(); zone.classList.add("drag-over"); });
  zone.addEventListener("dragleave", () => zone.classList.remove("drag-over"));
  zone.addEventListener("drop", e => { e.preventDefault(); zone.classList.remove("drag-over"); handleFile(type, e.dataTransfer.files[0]); });
  input.addEventListener("change", () => handleFile(type, input.files[0]));

  zone.querySelector(".upload-remove").addEventListener("click", e => {
    e.stopPropagation();
    clearUpload(type);
  });
}

function clearUpload(type) {
  uploads[type].b64 = "";
  $(`#${type}-img`).src = "";
  $(`#${type}-placeholder`).style.display = "flex";
  $(`#${type}-preview`).style.display = "none";
  $(`#${type}-input`).value = "";
  if (type === "product") {
    const st = $("#product-status");
    if (st) st.textContent = "";
  }
}

async function handleFile(type, file) {
  if (!file) return;
  const reader = new FileReader();
  reader.onload = async (e) => {
    const dataUrl = e.target.result;
    const b64Raw = dataUrl.split(",")[1];
    $(`#${type}-img`).src = dataUrl;
    $(`#${type}-placeholder`).style.display = "none";
    $(`#${type}-preview`).style.display = "flex";

    if (type === "logo" && window.ColorThief) {
      const tempImg = new Image();
      tempImg.crossOrigin = "anonymous";
      tempImg.onload = () => extractColorsFromLogo(tempImg);
      tempImg.src = dataUrl;
    }

    if (type === "product") {
      const st = $("#product-status");
      st.textContent = "Retrait du fond…";
      try {
        const blob = await (await fetch(dataUrl)).blob();
        const form = new FormData();
        form.append("file", blob, file.name);
        const res = await fetch(`${API}/remove-bg`, { method: "POST", body: form });
        if (!res.ok) throw new Error(await res.text());
        const data = await res.json();
        uploads.product.b64 = data.image_b64;
        $(`#product-img`).src = `data:image/png;base64,${data.image_b64}`;
        st.textContent = "✓ Fond retiré";
      } catch (err) {
        uploads.product.b64 = b64Raw;
        st.textContent = "⚠ Sans détourage";
        console.warn("[remove-bg]", err);
      }
    } else {
      uploads.logo.b64 = b64Raw;
    }
  };
  reader.readAsDataURL(file);
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
    $(`#${id}`).addEventListener("input", () => { saveBrandConfig(); updateColorPreview(); });
  });
  $("#sector").addEventListener("change", saveBrandConfig);

  $$("nav button").forEach(btn => {
    btn.addEventListener("click", () => {
      showPage(btn.dataset.page);
      if (btn.dataset.page === "analyze") loadAnalysis();
    });
  });

  initAdvancedToggle();
  initTemplates();
  initStyleButtons();
  initVariantsSlider();
  initFontPicker();
  initUploadZone("logo");
  initUploadZone("product");
  initModelButtons();
  updateModelFieldVisibility();
  renderBrandKits();
  updateColorPreview();

  $("#btn-generate").addEventListener("click", generateAds);
  $("#btn-suggest").addEventListener("click", suggestCopy);
  $("#btn-download-all").addEventListener("click", downloadAll);
  $("#btn-download-zip").addEventListener("click", downloadAllZip);
  $("#btn-mock-toggle").addEventListener("click", toggleMock);
  $("#btn-save-kit").addEventListener("click", saveBrandKit);
  $("#btn-analyze-refresh").addEventListener("click", loadAnalysis);

  $("#lightbox").addEventListener("click", e => {
    if (e.target === $("#lightbox") || e.target.id === "lb-close") closeLightbox();
  });
  document.addEventListener("keydown", e => {
    if (e.key === "Escape") closeLightbox();
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter" && document.getElementById("page-generate").classList.contains("active")) {
      e.preventDefault();
      generateAds();
    }
  });

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
    // Show auth overlay immediately to avoid blank page while session restores.
    showAuthOverlay();
    setupAuthForm();
    initAuth(
      async (user) => {
        showApp(user);
        await loadUserData();
      },
      () => showAuthOverlay(),
      () => {
        showAuthOverlay();
        if (window._setAuthMode) window._setAuthMode("recovery");
      }
    );
  } else {
    // Pas de Supabase configuré — mode sans auth
    $("#auth-overlay").style.display = "none";
    $("#app-root").style.display = "";
    window._appInitialized = true;
    initApp();
  }
});
