from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel
from typing import Optional
import asyncio
import base64
import json
import os
import io

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
    primary_color: str = "#000000"
    secondary_color: str = "#e94560"
    sector: str = "autre"


class GenerateRequest(BrandConfig):
    formats: Optional[list[str]] = ["feed", "story", "banner"]
    variants_per_format: Optional[int] = 2
    image_source: Optional[str] = "none"   # "none" | "stock" | "ai"
    ai_model: Optional[str] = "flux"       # "flux" | "flux-pro" | "flux-realism" | "turbo"
    logo_b64: Optional[str] = ""           # PNG RGBA base64
    product_b64: Optional[str] = ""        # PNG RGBA base64 (fond retiré)
    style_preset: Optional[str] = ""       # "" | "luxury" | "minimal" | "bold" | "ugc"
    font_family: Optional[str] = ""        # "" | "poppins" | "montserrat" | etc.


@app.get("/")
def root():
    return {"status": "ok", "service": "Loops MVP"}


@app.get("/debug/font")
def debug_font():
    from generator import _SYSTEM_FONT
    return {"system_font": _SYSTEM_FONT}


@app.get("/formats")
def list_formats():
    return [{"key": k, "width": v[0], "height": v[1]} for k, v in AD_FORMATS.items()]


@app.post("/analyze")
def analyze(config: BrandConfig):
    return get_sector_analysis(config.sector, config.brand_name, config.description)


@app.post("/suggest")
def suggest(config: BrandConfig):
    return suggest_copy(
        config.brand_name,
        config.sector,
        description=config.description,
        tagline=config.tagline,
    )


@app.post("/generate")
def generate(req: GenerateRequest):
    results = []
    for fmt in req.formats:
        if fmt not in AD_FORMATS:
            raise HTTPException(status_code=400, detail=f"Format inconnu : {fmt}")
        for v in range(req.variants_per_format):
            png_bytes, used_source = generate_ad(
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
                ai_model=req.ai_model or "flux",
                logo_b64=req.logo_b64 or "",
                product_b64=req.product_b64 or "",
                style_preset=req.style_preset or "",
                font_family=req.font_family or "",
            )
            results.append({
                "format": fmt,
                "variant": v + 1,
                "width": AD_FORMATS[fmt][0],
                "height": AD_FORMATS[fmt][1],
                "image_b64": base64.b64encode(png_bytes).decode(),
                "used_source": used_source,
            })
    return {"ads": results, "total": len(results)}


@app.post("/generate/stream")
async def generate_stream(req: GenerateRequest):
    """SSE endpoint — envoie chaque image dès qu'elle est générée."""
    formats = [f for f in (req.formats or ["feed"]) if f in AD_FORMATS]
    vpf = max(1, req.variants_per_format or 1)
    total = len(formats) * vpf

    def _build_kwargs(fmt: str, v: int) -> dict:
        return dict(
            brand_name=req.brand_name, tagline=req.tagline,
            description=req.description, cta=req.cta,
            primary_color=req.primary_color, secondary_color=req.secondary_color,
            sector=req.sector, format_key=fmt, variant=v,
            image_source=req.image_source or "none",
            ai_model=req.ai_model or "flux",
            logo_b64=req.logo_b64 or "",
            product_b64=req.product_b64 or "",
            style_preset=req.style_preset or "",
            font_family=req.font_family or "",
        )

    async def event_gen():
        done = 0
        for fmt in formats:
            for v in range(vpf):
                try:
                    png, used_source = await asyncio.to_thread(generate_ad, **_build_kwargs(fmt, v))
                    done += 1
                    payload = json.dumps({
                        "format": fmt, "variant": v + 1,
                        "width": AD_FORMATS[fmt][0], "height": AD_FORMATS[fmt][1],
                        "image_b64": base64.b64encode(png).decode(),
                        "used_source": used_source,
                        "done": done, "total": total,
                    })
                except Exception as e:
                    done += 1
                    payload = json.dumps({"error": str(e), "format": fmt, "done": done, "total": total})
                yield f"data: {payload}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/remove-bg")
async def remove_background(file: UploadFile = File(...)):
    """Retire le fond d'une image uploadée, retourne un PNG avec transparence en base64."""
    try:
        from rembg import remove as rembg_remove
        data = await file.read()
        result = rembg_remove(data)
        b64 = base64.b64encode(result).decode()
        return {"image_b64": b64, "mime": "image/png"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/generate/single")
def generate_single(
    brand_name: str = "My Brand",
    tagline: str = "Your tagline here",
    description: str = "Short description of your product.",
    cta: str = "Shop Now",
    primary_color: str = "#000000",
    secondary_color: str = "#e94560",
    format_key: str = "feed",
    variant: int = 0,
):
    if format_key not in AD_FORMATS:
        raise HTTPException(status_code=400, detail=f"Format inconnu : {format_key}")
    png_bytes, _ = generate_ad(
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
