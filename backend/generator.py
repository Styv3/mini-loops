from PIL import Image, ImageDraw, ImageFont, ImageFilter
import base64
import io
import os
import urllib.request
import urllib.parse
import random
import glob as _glob

AD_FORMATS = {
    "feed":   (1080, 1080),
    "story":  (1080, 1920),
    "banner": (1200, 628),
}

STYLE_PROMPTS = {
    "luxury":  "luxury editorial high fashion magazine, moody cinematic lighting, premium dark elegant aesthetic",
    "minimal": "clean minimal product photography, white studio background, simple elegant composition, airy light",
    "bold":    "bold graphic high contrast advertising, vibrant striking colors, powerful dynamic composition, punchy",
    "ugc":     "authentic user generated content, lifestyle photography, natural light, candid real person, relatable",
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

# ---------------------------------------------------------------------------
# Google Fonts download cache
# ---------------------------------------------------------------------------
_FONT_CACHE_DIR = os.path.join(os.path.dirname(__file__), "fonts_cache")
os.makedirs(_FONT_CACHE_DIR, exist_ok=True)

_GFONTS_TTF = {
    "poppins":    "https://raw.githubusercontent.com/google/fonts/main/ofl/poppins/Poppins-Bold.ttf",
    "montserrat": "https://raw.githubusercontent.com/google/fonts/main/ofl/montserrat/static/Montserrat-Bold.ttf",
    "playfair":   "https://raw.githubusercontent.com/google/fonts/main/ofl/playfairdisplay/PlayfairDisplay-Bold.ttf",
    "oswald":     "https://raw.githubusercontent.com/google/fonts/main/ofl/oswald/static/Oswald-Bold.ttf",
    "raleway":    "https://raw.githubusercontent.com/google/fonts/main/ofl/raleway/static/Raleway-Bold.ttf",
}

_font_cache: dict[str, str | None] = {}  # key → local path or None


def _get_custom_font_path(font_family: str) -> str | None:
    if not font_family or font_family not in _GFONTS_TTF:
        return None
    if font_family in _font_cache:
        return _font_cache[font_family]
    dest = os.path.join(_FONT_CACHE_DIR, f"{font_family}.ttf")
    if os.path.exists(dest):
        _font_cache[font_family] = dest
        return dest
    url = _GFONTS_TTF[font_family]
    print(f"[fonts] Downloading {font_family} from {url}")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            with open(dest, "wb") as f:
                f.write(resp.read())
        _font_cache[font_family] = dest
        print(f"[fonts] Saved to {dest}")
        return dest
    except Exception as e:
        print(f"[fonts] Download failed for {font_family}: {e}")
        _font_cache[font_family] = None
        return None


def _load_font(size: int, custom_path: str | None = None):
    path = custom_path or _SYSTEM_FONT
    if path:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
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


def _darken(c: tuple, factor: float = 0.65) -> tuple:
    return tuple(int(v * factor) for v in c)


def _gradient_bg(img: Image.Image, c1: tuple, c2: tuple) -> Image.Image:
    """Fast vertical gradient using strip-resize."""
    w, h = img.size
    strip = Image.new("RGB", (1, h))
    pix = strip.load()
    for y in range(h):
        t = y / max(h - 1, 1)
        pix[0, y] = (int(c1[0]+(c2[0]-c1[0])*t), int(c1[1]+(c2[1]-c1[1])*t), int(c1[2]+(c2[2]-c1[2])*t))
    return strip.resize((w, h), Image.BILINEAR)


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

def fetch_background(sector: str, hint: str, width: int, height: int, source: str = "ai", ai_model: str = "flux", style_preset: str = "") -> Image.Image | None:
    if source == "ai":
        gen_w = 512
        gen_h = max(256, round(gen_w * height / width))
        keywords = SECTOR_KEYWORDS.get(sector, SECTOR_KEYWORDS["autre"])
        style_suffix = STYLE_PROMPTS.get(style_preset, "professional advertisement photography, cinematic lighting, ultra high quality")
        prompt = f"{hint}, {keywords}, {style_suffix}"
        encoded = urllib.parse.quote(prompt)
        safe_model = ai_model if ai_model in ("flux", "flux-pro", "flux-realism", "turbo") else "flux"

        # Retry up to 3 times — Pollinations queues requests and is occasionally slow.
        for attempt in range(3):
            seed = random.randint(1, 99999)
            url = f"https://image.pollinations.ai/prompt/{encoded}?width={gen_w}&height={gen_h}&nologo=true&model={safe_model}&seed={seed}&nofeed=true"
            print(f"[fetch_background] AI attempt {attempt+1}/3 {url[:80]}...")
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=20) as resp:
                    data = resp.read()
                img = Image.open(io.BytesIO(data)).convert("RGB")
                result = img.resize((width, height), Image.LANCZOS)
                print(f"[fetch_background] OK attempt {attempt+1} — {len(data)} bytes")
                return result
            except Exception as e:
                print(f"[fetch_background] attempt {attempt+1} failed: {e}")
        return None

    elif source == "stock":
        seed = random.randint(1, 99999)
        kw = SECTOR_FLICKR.get(sector, SECTOR_FLICKR["autre"])
        url = f"https://loremflickr.com/{width}/{height}/{kw}?lock={seed}"
        print(f"[fetch_background] stock {url[:80]}...")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = resp.read()
            img = Image.open(io.BytesIO(data)).convert("RGB")
            return img.resize((width, height), Image.LANCZOS)
        except Exception as e:
            print(f"[fetch_background] stock failed: {e}")
            return None

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
    ai_model: str = "flux",
    logo_b64: str = "",           # PNG with alpha, base64-encoded
    product_b64: str = "",        # PNG with alpha (removed bg), base64-encoded
    style_preset: str = "",       # "" | "luxury" | "minimal" | "bold" | "ugc"
    font_family: str = "",        # "" | "poppins" | "montserrat" | etc.
) -> bytes:
    width, height = AD_FORMATS.get(format_key, AD_FORMATS["feed"])
    primary = _hex_to_rgb(primary_color)
    secondary = _hex_to_rgb(secondary_color)

    custom_font = _get_custom_font_path(font_family)

    bg = None
    if image_source in ("stock", "ai"):
        bg = fetch_background(sector, f"{brand_name} {tagline}", width, height, image_source, ai_model, style_preset)

    actual_source = image_source if bg is not None else "none"

    if bg is not None:
        # Overlay (0) and split (1) both work well across palettes; frame (2) is excluded
        # for now because its border color clashes with saturated secondaries.
        photo_lv = random.randint(0, 1)
        img = _render_photo_layout(bg, width, height, brand_name, tagline, description, cta, primary, secondary, photo_lv, custom_font)
    else:
        # Gradient background for all flat-color layouts — random so fallbacks vary too.
        grad_end = _blend(primary, secondary, 0.55)
        img = _gradient_bg(Image.new("RGB", (width, height)), primary, grad_end)
        draw = ImageDraw.Draw(img)
        lv = random.randint(0, 3)
        if lv == 0:
            _layout_centered(draw, width, height, brand_name, tagline, description, cta, primary, secondary, custom_font)
        elif lv == 1:
            _layout_split(draw, img, width, height, brand_name, tagline, description, cta, primary, secondary, custom_font)
        elif lv == 2:
            _layout_bold(draw, width, height, brand_name, tagline, description, cta, primary, secondary, custom_font)
        else:
            _layout_glass(draw, img, width, height, brand_name, tagline, description, cta, primary, secondary, custom_font)

    if logo_b64:
        img = _composite_logo(img, logo_b64, width, height)
    if product_b64:
        img = _composite_product(img, product_b64, width, height)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf.read(), actual_source


def _decode_b64_image(b64: str) -> Image.Image | None:
    try:
        data = base64.b64decode(b64)
        return Image.open(io.BytesIO(data)).convert("RGBA")
    except Exception as e:
        print(f"[_decode_b64_image] error: {e}")
        return None


def _composite_logo(img: Image.Image, logo_b64: str, w: int, h: int) -> Image.Image:
    logo = _decode_b64_image(logo_b64)
    if logo is None:
        return img
    max_w = int(w * 0.22)
    ratio = max_w / logo.width
    new_h = int(logo.height * ratio)
    logo = logo.resize((max_w, new_h), Image.LANCZOS)
    pad = int(w * 0.05)
    canvas = img.convert("RGBA")
    canvas.paste(logo, (w - max_w - pad, pad), logo)
    return canvas.convert("RGB")


def _composite_product(img: Image.Image, product_b64: str, w: int, h: int) -> Image.Image:
    product = _decode_b64_image(product_b64)
    if product is None:
        return img
    max_h = int(h * 0.45)
    ratio = max_h / product.height
    new_w = int(product.width * ratio)
    if new_w > int(w * 0.45):
        new_w = int(w * 0.45)
        ratio = new_w / product.width
        max_h = int(product.height * ratio)
    product = product.resize((new_w, max_h), Image.LANCZOS)
    x = w - new_w - int(w * 0.04)
    y = int(h * 0.30)
    canvas = img.convert("RGBA")
    canvas.paste(product, (x, y), product)
    return canvas.convert("RGB")


# ---------------------------------------------------------------------------
# Photo-backed layouts
# ---------------------------------------------------------------------------

def _render_photo_layout(
    bg: Image.Image, w: int, h: int,
    brand: str, tagline: str, desc: str, cta: str,
    primary: tuple, secondary: tuple, variant: int, custom_font=None,
) -> Image.Image:
    f = custom_font
    if variant % 3 == 0:
        return _photo_overlay(bg, w, h, brand, tagline, desc, cta, primary, secondary, f)
    elif variant % 3 == 1:
        return _photo_split(bg, w, h, brand, tagline, desc, cta, primary, secondary, f)
    else:
        return _photo_frame(bg, w, h, brand, tagline, desc, cta, primary, secondary, f)


def _photo_overlay(bg, w, h, brand, tagline, desc, cta, primary, secondary, cf=None):
    """Full-bleed photo with gradient overlay and text stack."""
    img = _apply_overlay(bg, primary, opacity=180)
    draw = ImageDraw.Draw(img)
    pad = int(w * 0.08)
    white = (245, 245, 245)

    # Brand name — top left
    font_brand = _load_font(int(h * 0.042), cf)
    draw.text((pad, int(h * 0.07)), brand.upper(), font=font_brand, fill=white)

    # Accent line
    draw.rectangle([(pad, int(h * 0.13)), (pad + 50, int(h * 0.133))], fill=secondary)

    # Tagline — large, center-bottom area
    font_tag = _load_font(int(h * 0.062), cf)
    lines = _wrap_text(tagline, font_tag, w - pad * 2, draw)
    y = int(h * 0.52)
    for line in lines:
        # Subtle shadow
        draw.text((pad + 2, y + 2), line, font=font_tag, fill=(0, 0, 0, 120))
        draw.text((pad, y), line, font=font_tag, fill=white)
        y += int(h * 0.075)

    # Description
    font_desc = _load_font(int(h * 0.030), cf)
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
    font_cta = _load_font(int(h * 0.034), cf)
    draw.text((bx + btn_w // 2, by + btn_h // 2), cta.upper(), font=font_cta, fill=accent, anchor="mm")

    return img


def _photo_split(bg, w, h, brand, tagline, desc, cta, primary, secondary, cf=None):
    """Photo on the right, solid color panel on the left."""
    img = Image.new("RGB", (w, h))
    # Left panel: solid primary
    left = Image.new("RGB", (w // 2, h), primary)
    img.paste(left, (0, 0))
    # Right: photo (crop right half)
    right_resized = bg.resize((w, h)).crop((w // 2, 0, w, h))
    img.paste(right_resized, (w // 2, 0))

    draw = ImageDraw.Draw(img)
    text_color = _contrast_color(primary)
    pad = int(w * 0.05)
    half = w // 2

    # Brand
    font_brand = _load_font(int(h * 0.050), cf)
    draw.text((pad, int(h * 0.10)), brand.upper(), font=font_brand, fill=secondary)

    # Divider
    dy = int(h * 0.20)
    draw.rectangle([(pad, dy), (pad + 40, dy + 3)], fill=text_color)

    # Tagline
    font_tag = _load_font(int(h * 0.042), cf)
    lines = _wrap_text(tagline, font_tag, half - pad * 2, draw)
    y = int(h * 0.25)
    for line in lines:
        draw.text((pad, y), line, font=font_tag, fill=text_color)
        y += int(h * 0.057)

    # Description
    font_desc = _load_font(int(h * 0.028), cf)
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
    font_cta = _load_font(int(h * 0.032), cf)
    draw.text((bx + btn_w // 2, by + btn_h // 2), cta.upper(), font=font_cta, fill=accent, anchor="mm")

    # Thin divider line
    draw.rectangle([(half - 1, 0), (half + 1, h)], fill=secondary)

    return img


def _photo_frame(bg, w, h, brand, tagline, desc, cta, primary, secondary, cf=None):
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

    # Subtle border — blend secondary toward white to avoid jarring saturated outlines
    border_color = _blend(secondary, (220, 220, 220), 0.45)
    draw.rounded_rectangle([pad_x, pad_y, pad_x + card_w, pad_y + card_h], radius=16, outline=border_color, width=1)

    # Accent top bar inside card
    draw.rounded_rectangle([pad_x, pad_y, pad_x + card_w, pad_y + int(h * 0.007)], radius=4, fill=secondary)

    white = _contrast_color(primary)
    inner_pad = int(w * 0.14)
    inner_w = w - inner_pad * 2

    font_brand = _load_font(int(h * 0.046), cf)
    draw.text((w // 2, pad_y + int(h * 0.09)), brand.upper(), font=font_brand, fill=secondary, anchor="mm")

    font_tag = _load_font(int(h * 0.040), cf)
    lines = _wrap_text(tagline, font_tag, inner_w, draw)
    y = pad_y + int(h * 0.20)
    for line in lines:
        draw.text((w // 2, y), line, font=font_tag, fill=white, anchor="mm")
        y += int(h * 0.056)

    font_desc = _load_font(int(h * 0.027), cf)
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
    font_cta = _load_font(int(h * 0.032), cf)
    draw.text((w // 2, by + btn_h // 2), cta.upper(), font=font_cta, fill=accent, anchor="mm")

    return img


# ---------------------------------------------------------------------------
# Flat color layouts — professional redesign
# ---------------------------------------------------------------------------

def _blend(c1: tuple, c2: tuple, t: float) -> tuple:
    return tuple(int(c1[i] * (1 - t) + c2[i] * t) for i in range(3))


def _layout_centered(draw, w, h, brand, tagline, desc, cta, primary, secondary, cf=None):
    """Editorial magazine — large tagline left-aligned, accent elements."""
    text_color = _contrast_color(primary)
    accent_btn = _contrast_color(secondary)
    pad = int(w * 0.09)
    muted = _blend(primary, text_color, 0.45)

    # Decorative top-right quarter circle (blended color, no RGBA needed)
    deco = _blend(primary, secondary, 0.20)
    r1 = int(w * 0.35)
    draw.ellipse([(w - r1, -r1), (w + r1, r1)], fill=deco)
    deco2 = _blend(primary, secondary, 0.32)
    r2 = int(w * 0.20)
    draw.ellipse([(w - r2, -r2), (w + r2, r2)], fill=deco2)

    # Thin accent line left-aligned
    line_y = int(h * 0.14)
    draw.rectangle([(pad, line_y), (pad + int(w * 0.06), line_y + 3)], fill=secondary)

    # Brand name — small caps, accent color
    font_brand = _load_font(int(h * 0.040), cf)
    draw.text((pad, line_y - int(h * 0.055)), brand.upper(), font=font_brand, fill=secondary)

    # Tagline — large, high contrast
    font_tag = _load_font(int(h * 0.062), cf)
    lines = _wrap_text(tagline, font_tag, w - pad * 2, draw)
    y = int(h * 0.26)
    for line in lines:
        draw.text((pad, y), line, font=font_tag, fill=text_color)
        y += int(h * 0.078)

    # Description
    font_desc = _load_font(int(h * 0.028), cf)
    desc_lines = _wrap_text(desc, font_desc, w - pad * 2, draw)
    y_desc = int(h * 0.55)
    for line in desc_lines:
        draw.text((pad, y_desc), line, font=font_desc, fill=muted)
        y_desc += int(h * 0.038)

    # CTA pill button
    font_cta = _load_font(int(h * 0.034), cf)
    btn_w, btn_h = int(w * 0.58), int(h * 0.076)
    bx, by = pad, int(h * 0.865)
    draw.rounded_rectangle([bx, by, bx + btn_w, by + btn_h], radius=btn_h // 2, fill=secondary)
    draw.text((bx + btn_w // 2, by + btn_h // 2), cta.upper(), font=font_cta, fill=accent_btn, anchor="mm")

    # Bottom decorative line
    draw.rectangle([(0, h - 4), (w, h)], fill=secondary)


def _layout_split(draw, img, w, h, brand, tagline, desc, cta, primary, secondary, cf=None):
    """Split panel — dark left with brand + CTA, accent right with tagline."""
    half = w // 2
    text_left  = _contrast_color(primary)
    text_right = _contrast_color(secondary)
    accent_btn = _contrast_color(primary)
    pad = int(w * 0.055)
    muted_left  = _blend(primary, text_left, 0.5)
    muted_right = _blend(secondary, text_right, 0.5)

    # Right panel — secondary color
    draw.rectangle([(half, 0), (w, h)], fill=secondary)

    # Diagonal overlap strip for depth
    points = [(half - int(w * 0.04), 0), (half + int(w * 0.04), 0), (half, h)]
    draw.polygon(points, fill=secondary)

    # Left: brand name — big
    font_brand = _load_font(int(h * 0.065), cf)
    draw.text((pad, int(h * 0.10)), brand.upper(), font=font_brand, fill=text_left)

    # Left: accent separator
    sep_y = int(h * 0.23)
    draw.rectangle([(pad, sep_y), (pad + int(w * 0.07), sep_y + 3)], fill=secondary)

    # Left: description
    font_desc = _load_font(int(h * 0.026), cf)
    desc_lines = _wrap_text(desc, font_desc, half - pad * 2, draw)
    y_desc = int(h * 0.30)
    for line in desc_lines:
        draw.text((pad, y_desc), line, font=font_desc, fill=muted_left)
        y_desc += int(h * 0.037)

    # Left: CTA
    font_cta = _load_font(int(h * 0.032), cf)
    btn_w, btn_h = int(half * 0.78), int(h * 0.07)
    bx, by = pad, int(h * 0.82)
    draw.rounded_rectangle([bx, by, bx + btn_w, by + btn_h], radius=6, fill=text_left)
    draw.text((bx + btn_w // 2, by + btn_h // 2), cta.upper(), font=font_cta, fill=primary, anchor="mm")

    # Right: tagline — large
    font_tag = _load_font(int(h * 0.056), cf)
    tag_lines = _wrap_text(tagline, font_tag, half - pad * 2 - int(w * 0.04), draw)
    y_tag = int(h * 0.18)
    for line in tag_lines:
        draw.text((half + pad + int(w * 0.02), y_tag), line, font=font_tag, fill=text_right)
        y_tag += int(h * 0.07)

    # Right: decorative dots
    for i in range(3):
        cx = half + int(w * 0.14) + i * int(w * 0.07)
        cy = int(h * 0.82)
        r = int(w * 0.018)
        alpha = 160 - i * 40
        draw.ellipse([(cx - r, cy - r), (cx + r, cy + r)], fill=(*text_right[:3], alpha))


def _layout_bold(draw, w, h, brand, tagline, desc, cta, primary, secondary, cf=None):
    """Bold header band + large type below — high contrast."""
    text_color = _contrast_color(primary)
    block_text = _contrast_color(secondary)
    accent_btn = _contrast_color(secondary)
    pad = int(w * 0.08)
    muted = _blend(primary, text_color, 0.50)

    # Top band with angled bottom edge
    band_h = int(h * 0.30)
    draw.rectangle([(0, 0), (w, band_h)], fill=secondary)
    # Angled bottom of band
    draw.polygon([(0, band_h), (w, band_h - int(h * 0.06)), (w, band_h), (0, band_h)], fill=secondary)

    # Brand name in band — large, centered
    font_brand = _load_font(int(h * 0.090), cf)
    draw.text((w // 2, int(band_h * 0.52)), brand.upper(), font=font_brand, fill=block_text, anchor="mm")

    # Tagline
    font_tag = _load_font(int(h * 0.052), cf)
    tag_lines = _wrap_text(tagline, font_tag, w - pad * 2, draw)
    y = int(h * 0.40)
    for line in tag_lines:
        draw.text((pad, y), line, font=font_tag, fill=text_color)
        y += int(h * 0.066)

    # Description
    font_desc = _load_font(int(h * 0.027), cf)
    desc_lines = _wrap_text(desc, font_desc, w - pad * 2, draw)
    y_desc = int(h * 0.63)
    for line in desc_lines:
        draw.text((pad, y_desc), line, font=font_desc, fill=muted)
        y_desc += int(h * 0.037)

    # CTA — wide, rounded rect
    font_cta = _load_font(int(h * 0.036), cf)
    btn_w, btn_h = int(w * 0.82), int(h * 0.082)
    bx = (w - btn_w) // 2
    by = int(h * 0.855)
    draw.rounded_rectangle([bx, by, bx + btn_w, by + btn_h], radius=10, fill=secondary)
    draw.text((w // 2, by + btn_h // 2), cta.upper(), font=font_cta, fill=accent_btn, anchor="mm")

    # Corner accent dots
    r = int(w * 0.015)
    draw.ellipse([(pad - r, by + btn_h // 2 - r), (pad + r, by + btn_h // 2 + r)], fill=secondary)
    draw.ellipse([(w - pad - r, by + btn_h // 2 - r), (w - pad + r, by + btn_h // 2 + r)], fill=secondary)


def _layout_glass(draw, img, w, h, brand, tagline, desc, cta, primary, secondary, cf=None):
    """Glass-morphism card on gradient background — modern premium aesthetic."""
    text_color = _contrast_color(primary)
    accent_btn = _contrast_color(secondary)
    pad = int(w * 0.08)

    # Frosted glass card via RGBA compositing
    card_x1, card_y1 = pad, int(h * 0.10)
    card_x2, card_y2 = w - pad, int(h * 0.91)
    card_cw = card_x2 - card_x1
    card_ch = card_y2 - card_y1

    # Frosted color: blend primary toward a neutral light to stand out from the gradient
    glass_color = _blend(primary, (160, 165, 185), 0.22)
    glass_layer = Image.new("RGBA", (card_cw, card_ch), (*glass_color, 195))
    base = img.convert("RGBA")
    region = base.crop((card_x1, card_y1, card_x2, card_y2))
    frosted = Image.alpha_composite(region, glass_layer)
    img.paste(frosted.convert("RGB"), (card_x1, card_y1))

    draw = ImageDraw.Draw(img)

    # Card border
    draw.rounded_rectangle([card_x1, card_y1, card_x2, card_y2], radius=18,
                            outline=_blend(text_color, secondary, 0.4), width=2)

    # Top accent bar
    draw.rounded_rectangle([card_x1, card_y1, card_x2, card_y1 + int(h * 0.007)],
                            radius=4, fill=secondary)

    inner_pad = int(w * 0.13)
    inner_w = w - inner_pad * 2

    # Brand name — centered, large, accent color
    font_brand = _load_font(int(h * 0.072), cf)
    draw.text((w // 2, card_y1 + int(h * 0.085)), brand.upper(),
              font=font_brand, fill=secondary, anchor="mm")

    # Thin divider
    div_y = card_y1 + int(h * 0.150)
    draw.rectangle([(w // 2 - int(w * 0.06), div_y), (w // 2 + int(w * 0.06), div_y + 2)],
                   fill=_blend(text_color, primary, 0.4))

    # Tagline — centered
    font_tag = _load_font(int(h * 0.046), cf)
    lines = _wrap_text(tagline, font_tag, inner_w, draw)
    y = card_y1 + int(h * 0.195)
    for line in lines:
        draw.text((w // 2, y), line, font=font_tag, fill=text_color, anchor="mm")
        y += int(h * 0.063)

    # Description — muted
    font_desc = _load_font(int(h * 0.026), cf)
    desc_lines = _wrap_text(desc, font_desc, inner_w, draw)
    muted = _blend(text_color, glass_color, 0.40)
    y_desc = card_y1 + int(h * 0.510)
    for line in desc_lines:
        draw.text((w // 2, y_desc), line, font=font_desc, fill=muted, anchor="mm")
        y_desc += int(h * 0.035)

    # CTA button
    font_cta = _load_font(int(h * 0.034), cf)
    btn_w, btn_h = int(inner_w * 0.78), int(h * 0.074)
    bx = (w - btn_w) // 2
    by = card_y2 - btn_h - int(h * 0.044)
    draw.rounded_rectangle([bx, by, bx + btn_w, by + btn_h], radius=btn_h // 2, fill=secondary)
    draw.text((w // 2, by + btn_h // 2), cta.upper(), font=font_cta, fill=accent_btn, anchor="mm")

    # Decorative corner circles in background (outside card)
    deco = _blend(primary, secondary, 0.30)
    rr = int(w * 0.18)
    draw.ellipse([(w - rr, h - rr), (w + rr, h + rr)], fill=deco)
    draw.ellipse([(-rr // 2, -rr // 2), (rr // 2, rr // 2)], fill=_blend(primary, secondary, 0.15))
