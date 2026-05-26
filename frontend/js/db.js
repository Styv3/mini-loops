// Supabase DB/Storage operations — dépend de auth.js (getUser, getSB)

async function dbSaveBrandConfig(cfg) {
  const sb = getSB(), user = getUser();
  if (!sb || !user) return;
  await sb.from("brand_configs").upsert(
    { user_id: user.id, ...cfg, updated_at: new Date().toISOString() },
    { onConflict: "user_id" }
  );
}

async function dbLoadBrandConfig() {
  const sb = getSB(), user = getUser();
  if (!sb || !user) return null;
  const { data } = await sb.from("brand_configs")
    .select("*").eq("user_id", user.id).maybeSingle();
  return data;
}

async function dbSaveAds(ads, brandConfig) {
  const sb = getSB(), user = getUser();
  if (!sb || !user) return;
  if (window.ENABLE_SUPABASE_AD_STORAGE !== true) return;
  for (const ad of ads) {
    try {
      const blob = await fetch(`data:image/png;base64,${ad.image_b64}`).then(r => r.blob());
      const path = `${user.id}/${Date.now()}-${ad.format}-v${ad.variant}.png`;
      const { error: upErr } = await sb.storage.from("ads").upload(path, blob, { contentType: "image/png" });
      if (upErr) { console.warn("[db] ad storage disabled:", upErr.message); return; }
      const { data: { publicUrl } } = sb.storage.from("ads").getPublicUrl(path);
      await sb.from("generated_ads").insert({
        user_id: user.id,
        format: ad.format,
        variant: ad.variant,
        width: ad.width,
        height: ad.height,
        source: ad.source || "none",
        image_url: publicUrl,
        brand_name: brandConfig.brand_name,
      });
    } catch (e) { console.error("[db] save ad:", e); }
  }
}

async function dbLoadRecentAds(limit = 9) {
  const sb = getSB(), user = getUser();
  if (!sb || !user) return [];
  const { data } = await sb.from("generated_ads")
    .select("*").eq("user_id", user.id)
    .order("created_at", { ascending: false }).limit(limit);
  return data || [];
}
