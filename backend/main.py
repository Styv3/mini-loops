from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Optional
import base64
import os

from generator import generate_ad, AD_FORMATS
from analyzer import get_sector_analysis, suggest_copy

app = FastAPI(title="Loops MVP API")

_origins_env = os.getenv("ALLOWED_ORIGINS", "*")
_origins = _origins_env.split(",") if _origins_env != "*" else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


class BrandConfig(BaseModel):
    brand_name: str
    tagline: str
    description: str
    cta: str
    primary_color: str = "#1a1a2e"
    secondary_color: str = "#e94560"
    sector: str = "autre"


class GenerateRequest(BrandConfig):
    formats: Optional[list[str]] = ["feed", "story", "banner"]
    variants_per_format: Optional[int] = 2
    image_source: Optional[str] = "none"   # "none" | "stock" | "ai"


@app.get("/")
def root():
    return {"status": "ok", "service": "Loops MVP"}


@app.get("/formats")
def list_formats():
    return [{"key": k, "width": v[0], "height": v[1]} for k, v in AD_FORMATS.items()]


@app.post("/analyze")
def analyze(config: BrandConfig):
    return get_sector_analysis(config.sector)


@app.post("/suggest")
def suggest(config: BrandConfig):
    return suggest_copy(config.brand_name, config.sector)


@app.post("/generate")
def generate(req: GenerateRequest):
    results = []
    for fmt in req.formats:
        if fmt not in AD_FORMATS:
            raise HTTPException(status_code=400, detail=f"Format inconnu : {fmt}")
        for v in range(req.variants_per_format):
            png_bytes = generate_ad(
                brand_name=req.brand_name,
                tagline=req.tagline,
                description=req.description,
                cta=req.cta,
                primary_color=req.primary_color,
                secondary_color=req.secondary_color,
                sector=req.sector,
                format_key=fmt,
                variant=v,
                image_source=req.image_source or "none",
            )
            results.append({
                "format": fmt,
                "variant": v + 1,
                "width": AD_FORMATS[fmt][0],
                "height": AD_FORMATS[fmt][1],
                "image_b64": base64.b64encode(png_bytes).decode(),
            })
    return {"ads": results, "total": len(results)}


@app.get("/generate/single")
def generate_single(
    brand_name: str = "My Brand",
    tagline: str = "Your tagline here",
    description: str = "Short description of your product.",
    cta: str = "Shop Now",
    primary_color: str = "#1a1a2e",
    secondary_color: str = "#e94560",
    format_key: str = "feed",
    variant: int = 0,
):
    if format_key not in AD_FORMATS:
        raise HTTPException(status_code=400, detail=f"Format inconnu : {format_key}")
    png_bytes = generate_ad(
        brand_name=brand_name,
        tagline=tagline,
        description=description,
        cta=cta,
        primary_color=primary_color,
        secondary_color=secondary_color,
        format_key=format_key,
        variant=variant,
    )
    return Response(content=png_bytes, media_type="image/png")
