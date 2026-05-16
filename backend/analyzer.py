import random

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
            "La simplicité du message augmente le mémorisation de la marque.",
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


def get_sector_analysis(sector: str) -> dict:
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
    }


def suggest_copy(brand_name: str, sector: str) -> dict:
    data = SECTOR_PATTERNS.get(sector, SECTOR_PATTERNS["autre"])
    hook = random.choice(data["top_hooks"])
    cta = random.choice(data["top_ctas"])
    return {
        "suggested_tagline": hook,
        "suggested_cta": cta,
        "tip": random.choice(data["insights"]),
    }
