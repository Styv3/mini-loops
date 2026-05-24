import random
import os
import json

# ---------------------------------------------------------------------------
# Static fallback data
# ---------------------------------------------------------------------------

SECTOR_PATTERNS = {
    "beaute": {
        "top_hooks": [
            "Before & After Results",
            "Dermatologist Recommended",
            "Clean Ingredients Only",
            "90-Day Money Back Guarantee",
        ],
        "top_ctas": ["Shop Now", "Get 30% Off", "Try Risk-Free", "Claim Your Offer"],
        "top_formats": ["feed", "story"],
        "avg_roas": 3.2,
        "insights": [
            "Les visuels avant/après génèrent 2x plus de clics.",
            "La preuve sociale (avis, dermatologues) augmente le taux de conversion de 40%.",
            "Les stories verticales surpassent les posts carrés de 28% sur Instagram.",
        ],
    },
    "ecommerce": {
        "top_hooks": [
            "Limited Time Offer",
            "Free Shipping Today Only",
            "Join 50,000+ Happy Customers",
            "As Seen On TikTok",
        ],
        "top_ctas": ["Buy Now", "Get Yours", "Order Today", "Grab the Deal"],
        "top_formats": ["banner", "feed"],
        "avg_roas": 2.8,
        "insights": [
            "L'urgence (« today only ») augmente le CTR de 35%.",
            "Afficher un prix barré réduit l'hésitation d'achat de 22%.",
            "Les visuels produit sur fond blanc performent mieux en feed.",
        ],
    },
    "sante": {
        "top_hooks": [
            "Clinically Proven Formula",
            "Feel the Difference in 7 Days",
            "No Side Effects",
            "Trusted by 100k Users",
        ],
        "top_ctas": ["Start Today", "Get Free Trial", "Learn More", "Try It Now"],
        "top_formats": ["story", "feed"],
        "avg_roas": 2.5,
        "insights": [
            "Les chiffres précis (« 7 jours ») inspirent plus confiance que les promesses vagues.",
            "Le vert et le blanc dominent les couleurs les plus performantes.",
            "Les témoignages vidéo génèrent 3x plus d'engagement que les visuels statiques.",
        ],
    },
    "autre": {
        "top_hooks": [
            "Why Everyone Is Talking About This",
            "The Secret Top Brands Use",
            "Stop Wasting Money On X",
            "Simple. Effective. Guaranteed.",
        ],
        "top_ctas": ["Discover Now", "Get Started", "Shop the Collection", "See More"],
        "top_formats": ["feed", "banner"],
        "avg_roas": 2.3,
        "insights": [
            "La simplicité du message augmente la mémorisation de la marque.",
            "Un seul CTA clair surpasse les publicités à messages multiples.",
            "Le contraste élevé entre fond et texte améliore la lisibilité mobile.",
        ],
    },
}

COMPETITOR_ADS = [
    {"brand": "GlowSkin", "hook": "90% saw results in 30 days", "cta": "Shop Now", "roas": 3.8, "sector": "beaute"},
    {"brand": "FitCore", "hook": "Join 200k+ athletes", "cta": "Start Free Trial", "roas": 2.9, "sector": "sante"},
    {"brand": "StyleBox", "hook": "Free shipping on orders $50+", "cta": "Get Yours", "roas": 3.1, "sector": "ecommerce"},
    {"brand": "NovaDerm", "hook": "Dermatologist approved formula", "cta": "Try Risk-Free", "roas": 4.1, "sector": "beaute"},
    {"brand": "PureVital", "hook": "Feel the difference in 7 days", "cta": "Order Today", "roas": 2.7, "sector": "sante"},
    {"brand": "UrbanWear", "hook": "Limited drop — only 48h", "cta": "Grab the Deal", "roas": 3.5, "sector": "ecommerce"},
]

SECTOR_LABELS = {
    "beaute": "beauté / cosmétiques",
    "ecommerce": "e-commerce",
    "sante": "santé / bien-être",
    "autre": "autre",
}

# ---------------------------------------------------------------------------
# Lazy Anthropic client
# ---------------------------------------------------------------------------

_client = None

def _get_client():
    global _client
    if _client is None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if api_key:
            try:
                import anthropic
                _client = anthropic.Anthropic(api_key=api_key)
            except Exception as e:
                print(f"[analyzer] Anthropic init error: {e}")
    return _client


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_sector_analysis(sector: str, brand_name: str = "", description: str = "") -> dict:
    client = _get_client()
    if client:
        try:
            return _analyze_sector_llm(client, sector, brand_name, description)
        except Exception as e:
            print(f"[analyze] LLM error: {e}, falling back to static")
    return _analyze_sector_static(sector)


def _analyze_sector_llm(client, sector: str, brand_name: str, description: str) -> dict:
    sector_label = SECTOR_LABELS.get(sector, sector)
    context = f"Secteur : {sector_label}"
    if brand_name:
        context += f"\nMarque : {brand_name}"
    if description:
        context += f"\nProduit : {description}"

    prompt = f"""{context}

Tu es un expert en performance publicitaire digitale (Meta Ads, TikTok, Google Ads).

Génère une analyse de marché actionnable pour ce secteur. Réponds UNIQUEMENT en JSON valide (pas de markdown) :
{{
  "top_hooks": ["hook1","hook2","hook3","hook4","hook5"],
  "top_ctas": ["cta1","cta2","cta3","cta4"],
  "insights": [
    "Insight stratégique 1 (avec un chiffre concret)",
    "Insight stratégique 2 (avec un chiffre concret)",
    "Insight stratégique 3 (avec un chiffre concret)"
  ],
  "avg_roas": 3.2,
  "competitor_ads": [
    {{"brand": "Marque A", "hook": "...", "cta": "...", "roas": 3.8}},
    {{"brand": "Marque B", "hook": "...", "cta": "...", "roas": 2.9}},
    {{"brand": "Marque C", "hook": "...", "cta": "...", "roas": 4.1}}
  ]
}}

Les hooks doivent être percutants et variés (urgence, preuve sociale, résultat, curiosité, émotion).
Les competitor_ads sont des exemples réalistes du secteur (pas forcément des vraies marques).
avg_roas : estimation réaliste pour ce secteur (nombre décimal).
Les insights doivent contenir des pourcentages ou chiffres concrets."""

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=900,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    data = json.loads(raw.strip())

    for ad in data.get("competitor_ads", []):
        ad["sector"] = sector

    return {
        "sector": sector,
        "top_hooks": data.get("top_hooks", []),
        "top_ctas": data.get("top_ctas", []),
        "recommended_formats": SECTOR_PATTERNS.get(sector, SECTOR_PATTERNS["autre"])["top_formats"],
        "avg_roas": data.get("avg_roas", 2.5),
        "insights": data.get("insights", []),
        "competitor_ads": data.get("competitor_ads", []),
        "source": "ai",
    }


def _analyze_sector_static(sector: str) -> dict:
    data = SECTOR_PATTERNS.get(sector, SECTOR_PATTERNS["autre"])
    competitors = [ad for ad in COMPETITOR_ADS if ad["sector"] == sector]
    if not competitors:
        competitors = random.sample(COMPETITOR_ADS, 2)
    return {
        "sector": sector,
        "top_hooks": data["top_hooks"],
        "top_ctas": data["top_ctas"],
        "recommended_formats": data["top_formats"],
        "avg_roas": data["avg_roas"],
        "insights": data["insights"],
        "competitor_ads": competitors,
        "source": "static",
    }


def suggest_copy(brand_name: str, sector: str, description: str = "", tagline: str = "") -> dict:
    client = _get_client()
    if client:
        try:
            return _suggest_copy_llm(client, brand_name, sector, description, tagline)
        except Exception as e:
            print(f"[suggest_copy] LLM error: {e}, falling back to static")
    return _suggest_copy_static(brand_name, sector)


# ---------------------------------------------------------------------------
# LLM path
# ---------------------------------------------------------------------------

def _suggest_copy_llm(client, brand_name: str, sector: str, description: str, tagline: str) -> dict:
    sector_label = SECTOR_LABELS.get(sector, sector)
    context_lines = [f"Marque : {brand_name}", f"Secteur : {sector_label}"]
    if description:
        context_lines.append(f"Description : {description}")
    if tagline:
        context_lines.append(f"Tagline actuelle : {tagline}")
    context = "\n".join(context_lines)

    prompt = f"""{context}

Tu es expert en copywriting publicitaire pour les réseaux sociaux (Meta Ads, TikTok, Instagram).

Génère 5 variantes de copy publicitaire percutantes et distinctes pour cette marque.
Chaque variante doit avoir :
- Un hook / tagline court et accrocheur (maximum 12 mots, impactant, orienté conversion)
- Un CTA (call-to-action) efficace (maximum 4 mots)

Assure-toi que les 5 variantes sont vraiment différentes (urgence, preuve sociale, résultat, curiosité, émotion).

Réponds UNIQUEMENT avec un JSON valide, sans markdown ni backticks, dans ce format exact :
{{
  "variants": [
    {{"tagline": "...", "cta": "..."}},
    {{"tagline": "...", "cta": "..."}},
    {{"tagline": "...", "cta": "..."}},
    {{"tagline": "...", "cta": "..."}},
    {{"tagline": "...", "cta": "..."}}
  ],
  "tip": "Un conseil stratégique concis (1 phrase) pour maximiser les conversions de cette campagne."
}}"""

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=700,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()
    # Strip accidental markdown fences
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    data = json.loads(raw.strip())

    variants = data.get("variants", [])
    return {
        "variants": variants,
        "suggested_tagline": variants[0]["tagline"] if variants else "",
        "suggested_cta": variants[0]["cta"] if variants else "",
        "tip": data.get("tip", ""),
        "source": "ai",
    }


# ---------------------------------------------------------------------------
# Static fallback
# ---------------------------------------------------------------------------

def _suggest_copy_static(brand_name: str, sector: str) -> dict:
    data = SECTOR_PATTERNS.get(sector, SECTOR_PATTERNS["autre"])
    ctas = data["top_ctas"][:]
    random.shuffle(ctas)
    variants = [
        {"tagline": hook, "cta": ctas[i % len(ctas)]}
        for i, hook in enumerate(data["top_hooks"])
    ]
    random.shuffle(variants)
    return {
        "variants": variants[:5],
        "suggested_tagline": variants[0]["tagline"],
        "suggested_cta": variants[0]["cta"],
        "tip": random.choice(data["insights"]),
        "source": "static",
    }
