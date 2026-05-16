from PIL import Image, ImageDraw, ImageFont, ImageFilter
import io
import urllib.request
import urllib.parse
import random
import glob as _glob

AD_FORMATS = {
    "feed":   (1080, 1080),
    "story":  (1080, 1920),
    "banner": (1200, 628),
}

SECTOR_KEYWORDS = {
    "beaute":    "luxury beauty skincare cosmetics elegant woman glowing skin",
    "ecommerce": "product photography lifestyle modern minimal studio",
    "sante":     "health wellness nature green light fresh outdoors",
    "autre":     "modern business lifestyle abstract professional",
}

# Keywords for loremflickr (comma-separated, no spaces)
SECTOR_FLICKR = {
    "beaute":    "beauty,skincare,cosmetics,makeup",
    "ecommerce": "fashion,lifestyle,shopping,product",
    "sante":     "health,wellness,nature,fitness",
    "autre":     "business,modern,lifestyle,office",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hex_to_rgb(hex_color: str) -> tuple:
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def _luminance(rgb: tuple) -> float:
    return 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]


def _contrast_color(bg_rgb: tuple) -> tuple:
    return (15, 15, 15) if _luminance(bg_rgb) > 128 else (245, 245, 245)


def _find_system_font() -> str | None:
    """Locate a usable TTF font on Windows, Linux, or Nix environments."""
    direct = ["arialbd.ttf", "arial.ttf", "DejaVuSans-Bold.ttf", "DejaVuSans.ttf"]
    for name in direct:
        try:
            ImageFont.truetype(name, 12)
            return name
        except Exception:
            pass
    patterns = [
        "/nix/store/*/share/fonts/truetype/DejaVuSans-Bold.ttf",
        "/nix/store/*/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    ]
    for pattern in patterns:
        matches = _glob.glob(pattern)
        if matches:
            return matches[0]
    return None

_SYSTEM_FONT = _find_system_font()


def _load_font(size: int):
    if _SYSTEM_FONT:
        try:
            return ImageFont.truetype(_SYSTEM_FONT, size)
        except Exception:
            pass
    return ImageFont.load_default()


def _wrap_text(text: str, font, max_width: int, draw: ImageDraw) -> list[str]:
    words = text.split()
    lines, current = [], ""
    for word in words:
        test = (current + " " + word).strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] > max_width and current:
            lines.append(current)
            current = word
        else:
            current = test
    if current:
        lines.append(current)
    return lines


def _draw_gradient(draw: ImageDraw, width: int, height: int, c1: tuple, c2: tuple):
    for y in range(height):
        r = y / height
        draw.line(
            [(0, y), (width, y)],
            fill=(int(c1[0]*(1-r)+c2[0]*r), int(c1[1]*(1-r)+c2[1]*r), int(c1[2]*(1-r)+c2[2]*r)),
        )


def _apply_overlay(img: Image.Image, primary: tuple, opacity: int = 160) -> Image.Image:
    """Darkened tinted gradient overlay for text readability."""
    w, h = img.size
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    # Gradient: opaque at bottom, lighter at top
    for y in range(h):
        alpha = int(opacity * (y / h) ** 0.7)
        draw.line([(0, y), (w, y)], fill=(*primary, alpha // 2))
    for y in range(h):
        alpha = int(120 * (y / h) ** 1.5)
        draw.line([(0, y), (w, y)], fill=(0, 0, 0, alpha))
    return Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")


# ---------------------------------------------------------------------------
# Image fetching
# ---------------------------------------------------------------------------

def fetch_background(sector: str, hint: str, width: int, height: int, source: str = "ai") -> Image.Image | None:
    seed = random.randint(1, 99999)

    if source == "ai":
        keywords = SECTOR_KEYWORDS.get(sector, SECTOR_KEYWORDS["autre"])
        prompt = f"{hint}, {keywords}, professional advertisement photography, cinematic lighting, ultra high quality"
        encoded = urllib.parse.quote(prompt)
        url = f"https://image.pollinations.ai/prompt/{encoded}?width={width}&height={height}&nologo=true&model=flux&seed={seed}"
    elif source == "stock":
        kw = SECTOR_FLICKR.get(sector, SECTOR_FLICKR["autre"])
        url = f"https://loremflickr.com/{width}/{height}/{kw}?lock={seed}"
    else:
        return None

    print(f"[fetch_background] source={source} url={url[:80]}...")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = resp.read()
        img = Image.open(io.BytesIO(data)).convert("RGB")
        result = img.resize((width, height), Image.LANCZOS)
        print(f"[fetch_background] OK — {len(data)} bytes")
        return result
    except Exception as e:
        print(f"[fetch_background] ERREUR : {e}")
        return None


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def generate_ad(
    brand_name: str,
    tagline: str,
    description: str,
    cta: str,
    primary_color: str,
    secondary_color: str,
    sector: str = "autre",
    format_key: str = "feed",
    variant: int = 0,
    image_source: str = "none",   # "none" | "stock" | "ai"
) -> bytes:
    width, height = AD_FORMATS.get(format_key, AD_FORMATS["feed"])
    primary = _hex_to_rgb(primary_color)
    secondary = _hex_to_rgb(secondary_color)

    bg = None
    if image_source in ("stock", "ai"):
        bg = fetch_background(sector, f"{brand_name} {tagline}", width, height, image_source)

    if bg is not None:
        img = _render_photo_layout(bg, width, height, brand_name, tagline, description, cta, primary, secondary, variant)
    else:
        img = Image.new("RGB", (width, height), primary)
        draw = ImageDraw.Draw(img)
        if variant % 3 == 0:
            _draw_gradient(draw, width, height, primary, secondary)
            _layout_centered(draw, width, height, brand_name, tagline, description, cta, primary, secondary)
        elif variant % 3 == 1:
            _layout_split(draw, img, width, height, brand_name, tagline, description, cta, primary, secondary)
        else:
            _layout_bold(draw, width, height, brand_name, tagline, description, cta, primary, secondary)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf.read()


# ---------------------------------------------------------------------------
# Photo-backed layouts
# ---------------------------------------------------------------------------

def _render_photo_layout(
    bg: Image.Image, w: int, h: int,
    brand: str, tagline: str, desc: str, cta: str,
    primary: tuple, secondary: tuple, variant: int,
) -> Image.Image:
    if variant % 3 == 0:
        return _photo_overlay(bg, w, h, brand, tagline, desc, cta, primary, secondary)
    elif variant % 3 == 1:
        return _photo_split(bg, w, h, brand, tagline, desc, cta, primary, secondary)
    else:
        return _photo_frame(bg, w, h, brand, tagline, desc, cta, primary, secondary)


def _photo_overlay(bg, w, h, brand, tagline, desc, cta, primary, secondary):
    """Full-bleed photo with gradient overlay and text stack."""
    img = _apply_overlay(bg, primary, opacity=180)
    draw = ImageDraw.Draw(img)
    pad = int(w * 0.08)
    white = (245, 245, 245)

    # Brand name — top left
    font_brand = _load_font(int(h * 0.042))
    draw.text((pad, int(h * 0.07)), brand.upper(), font=font_brand, fill=white)

    # Accent line
    draw.rectangle([(pad, int(h * 0.13)), (pad + 50, int(h * 0.133))], fill=secondary)

    # Tagline — large, center-bottom area
    font_tag = _load_font(int(h * 0.062))
    lines = _wrap_text(tagline, font_tag, w - pad * 2, draw)
    y = int(h * 0.52)
    for line in lines:
        # Subtle shadow
        draw.text((pad + 2, y + 2), line, font=font_tag, fill=(0, 0, 0, 120))
        draw.text((pad, y), line, font=font_tag, fill=white)
        y += int(h * 0.075)

    # Description
    font_desc = _load_font(int(h * 0.030))
    lines = _wrap_text(desc, font_desc, w - pad * 2, draw)
    y_desc = y + int(h * 0.02)
    for line in lines:
        draw.text((pad, y_desc), line, font=font_desc, fill=(200, 200, 210))
        y_desc += int(h * 0.040)

    # CTA button
    btn_w, btn_h = int(w * 0.52), int(h * 0.072)
    bx, by = pad, int(h * 0.87)
    draw.rounded_rectangle([bx, by, bx + btn_w, by + btn_h], radius=btn_h // 2, fill=secondary)
    accent = _contrast_color(secondary)
    font_cta = _load_font(int(h * 0.034))
    draw.text((bx + btn_w // 2, by + btn_h // 2), cta.upper(), font=font_cta, fill=accent, anchor="mm")

    return img


def _photo_split(bg, w, h, brand, tagline, desc, cta, primary, secondary):
    """Photo on the right, solid color panel on the left."""
    img = Image.new("RGB", (w, h))
    # Left panel: solid primary
    left = Image.new("RGB", (w // 2, h), primary)
    img.paste(left, (0, 0))
    # Right: photo (crop right half)
    right = bg.crop((w // 2, 0, w, h)) if bg.size[0] >= w else bg.resize((w, h)).crop((w // 2, 0, w, h))
    right_resized = bg.resize((w, h)).crop((w // 2, 0, w, h))
    img.paste(right_resized, (w // 2, 0))

    draw = ImageDraw.Draw(img)
    text_color = _contrast_color(primary)
    pad = int(w * 0.05)
    half = w // 2

    # Brand
    font_brand = _load_font(int(h * 0.050))
    draw.text((pad, int(h * 0.10)), brand.upper(), font=font_brand, fill=secondary)

    # Divider
    dy = int(h * 0.20)
    draw.rectangle([(pad, dy), (pad + 40, dy + 3)], fill=text_color)

    # Tagline
    font_tag = _load_font(int(h * 0.042))
    lines = _wrap_text(tagline, font_tag, half - pad * 2, draw)
    y = int(h * 0.25)
    for line in lines:
        draw.text((pad, y), line, font=font_tag, fill=text_color)
        y += int(h * 0.057)

    # Description
    font_desc = _load_font(int(h * 0.028))
    lines = _wrap_text(desc, font_desc, half - pad * 2, draw)
    y_desc = int(h * 0.57)
    for line in lines:
        draw.text((pad, y_desc), line, font=font_desc, fill=(*text_color[:3],))
        y_desc += int(h * 0.038)

    # CTA
    btn_w, btn_h = int(half * 0.80), int(h * 0.072)
    bx, by = pad, int(h * 0.83)
    draw.rounded_rectangle([bx, by, bx + btn_w, by + btn_h], radius=6, fill=secondary)
    accent = _contrast_color(secondary)
    font_cta = _load_font(int(h * 0.032))
    draw.text((bx + btn_w // 2, by + btn_h // 2), cta.upper(), font=font_cta, fill=accent, anchor="mm")

    # Thin divider line
    draw.rectangle([(half - 1, 0), (half + 1, h)], fill=secondary)

    return img


def _photo_frame(bg, w, h, brand, tagline, desc, cta, primary, secondary):
    """Blurred photo bg + centered frosted card."""
    blurred = bg.filter(ImageFilter.GaussianBlur(radius=18))
    darkened = _apply_overlay(blurred, primary, opacity=140)
    img = darkened.copy()
    draw = ImageDraw.Draw(img)

    pad_x = int(w * 0.10)
    pad_y = int(h * 0.12)
    card_w = w - pad_x * 2
    card_h = h - pad_y * 2

    # Frosted card
    card = Image.new("RGBA", (card_w, card_h), (*primary, 210))
    img.paste(Image.alpha_composite(img.crop((pad_x, pad_y, pad_x + card_w, pad_y + card_h)).convert("RGBA"), card).convert("RGB"), (pad_x, pad_y))

    # Border
    draw.rounded_rectangle([pad_x, pad_y, pad_x + card_w, pad_y + card_h], radius=16, outline=secondary, width=3)

    # Accent top bar inside card
    draw.rounded_rectangle([pad_x, pad_y, pad_x + card_w, pad_y + int(h * 0.007)], radius=4, fill=secondary)

    white = _contrast_color(primary)
    inner_pad = int(w * 0.14)
    inner_w = w - inner_pad * 2

    font_brand = _load_font(int(h * 0.046))
    draw.text((w // 2, pad_y + int(h * 0.09)), brand.upper(), font=font_brand, fill=secondary, anchor="mm")

    font_tag = _load_font(int(h * 0.040))
    lines = _wrap_text(tagline, font_tag, inner_w, draw)
    y = pad_y + int(h * 0.20)
    for line in lines:
        draw.text((w // 2, y), line, font=font_tag, fill=white, anchor="mm")
        y += int(h * 0.056)

    font_desc = _load_font(int(h * 0.027))
    lines = _wrap_text(desc, font_desc, inner_w, draw)
    y_desc = pad_y + int(h * 0.50)
    for line in lines:
        draw.text((w // 2, y_desc), line, font=font_desc, fill=(*white[:3],), anchor="mm")
        y_desc += int(h * 0.037)

    btn_w, btn_h = int(card_w * 0.65), int(h * 0.072)
    bx = (w - btn_w) // 2
    by = pad_y + card_h - btn_h - int(h * 0.06)
    draw.rounded_rectangle([bx, by, bx + btn_w, by + btn_h], radius=btn_h // 2, fill=secondary)
    accent = _contrast_color(secondary)
    font_cta = _load_font(int(h * 0.032))
    draw.text((w // 2, by + btn_h // 2), cta.upper(), font=font_cta, fill=accent, anchor="mm")

    return img


# ---------------------------------------------------------------------------
# Flat color fallback layouts (unchanged)
# ---------------------------------------------------------------------------

def _layout_centered(draw, w, h, brand, tagline, desc, cta, primary, secondary):
    text_color = _contrast_color(primary)
    accent = _contrast_color(secondary)
    pad = int(w * 0.08)
    font_brand = _load_font(int(h * 0.07))
    draw.text((w // 2, int(h * 0.18)), brand.upper(), font=font_brand, fill=text_color, anchor="mm")
    div_y = int(h * 0.27)
    draw.rectangle([(w // 2 - 40, div_y), (w // 2 + 40, div_y + 3)], fill=text_color)
    font_tag = _load_font(int(h * 0.04))
    lines = _wrap_text(tagline, font_tag, w - pad * 2, draw)
    y = int(h * 0.34)
    for line in lines:
        draw.text((w // 2, y), line, font=font_tag, fill=text_color, anchor="mm")
        y += int(h * 0.055)
    font_desc = _load_font(int(h * 0.028))
    lines = _wrap_text(desc, font_desc, w - pad * 2, draw)
    y = int(h * 0.56)
    for line in lines:
        draw.text((w // 2, y), line, font=font_desc, fill=text_color, anchor="mm")
        y += int(h * 0.038)
    btn_w, btn_h = int(w * 0.55), int(h * 0.075)
    bx = (w - btn_w) // 2
    by = int(h * 0.82)
    draw.rounded_rectangle([bx, by, bx + btn_w, by + btn_h], radius=btn_h // 2, fill=secondary)
    font_cta = _load_font(int(h * 0.035))
    draw.text((w // 2, by + btn_h // 2), cta.upper(), font=font_cta, fill=accent, anchor="mm")


def _layout_split(draw, img, w, h, brand, tagline, desc, cta, primary, secondary):
    draw.rectangle([(0, 0), (w // 2, h)], fill=secondary)
    text_left = _contrast_color(secondary)
    text_right = _contrast_color(primary)
    pad = int(w * 0.06)
    font_brand = _load_font(int(h * 0.055))
    draw.text((w // 4, int(h * 0.15)), brand.upper(), font=font_brand, fill=text_left, anchor="mm")
    draw.rectangle([(w // 2 - 2, 0), (w // 2 + 2, h)], fill=(255, 255, 255))
    font_tag = _load_font(int(h * 0.038))
    lines = _wrap_text(tagline, font_tag, w // 2 - pad * 2, draw)
    y = int(h * 0.28)
    for line in lines:
        draw.text((w // 4, y), line, font=font_tag, fill=text_left, anchor="mm")
        y += int(h * 0.055)
    font_desc = _load_font(int(h * 0.028))
    lines = _wrap_text(desc, font_desc, w // 2 - pad * 2, draw)
    y = int(h * 0.25)
    for line in lines:
        draw.text((w * 3 // 4, y), line, font=font_desc, fill=text_right, anchor="mm")
        y += int(h * 0.042)
    btn_w, btn_h = int(w * 0.35), int(h * 0.07)
    bx = w * 3 // 4 - btn_w // 2
    by = int(h * 0.80)
    draw.rounded_rectangle([bx, by, bx + btn_w, by + btn_h], radius=btn_h // 2, fill=secondary)
    accent = _contrast_color(secondary)
    font_cta = _load_font(int(h * 0.032))
    draw.text((w * 3 // 4, by + btn_h // 2), cta.upper(), font=font_cta, fill=accent, anchor="mm")


def _layout_bold(draw, w, h, brand, tagline, desc, cta, primary, secondary):
    text_color = _contrast_color(primary)
    pad = int(w * 0.08)
    block_h = int(h * 0.35)
    draw.rectangle([(0, 0), (w, block_h)], fill=secondary)
    font_brand = _load_font(int(h * 0.10))
    block_text = _contrast_color(secondary)
    draw.text((w // 2, block_h // 2), brand.upper(), font=font_brand, fill=block_text, anchor="mm")
    r = int(w * 0.12)
    draw.ellipse([(w - r * 2, block_h - r), (w, block_h + r)], fill=primary)
    font_tag = _load_font(int(h * 0.05))
    lines = _wrap_text(tagline, font_tag, w - pad * 2, draw)
    y = int(h * 0.42)
    for line in lines:
        draw.text((pad, y), line, font=font_tag, fill=text_color)
        y += int(h * 0.065)
    font_desc = _load_font(int(h * 0.028))
    lines = _wrap_text(desc, font_desc, w - pad * 2, draw)
    y = int(h * 0.64)
    for line in lines:
        draw.text((pad, y), line, font=font_desc, fill=text_color)
        y += int(h * 0.038)
    btn_w, btn_h = int(w * 0.8), int(h * 0.08)
    bx = (w - btn_w) // 2
    by = int(h * 0.85)
    draw.rounded_rectangle([bx, by, bx + btn_w, by + btn_h], radius=8, fill=secondary)
    accent = _contrast_color(secondary)
    font_cta = _load_font(int(h * 0.038))
    draw.text((w // 2, by + btn_h // 2), cta.upper(), font=font_cta, fill=accent, anchor="mm")
