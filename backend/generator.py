from PIL import Image, ImageDraw, ImageFont, ImageFilter
import base64
import io
import os
import urllib.request
import urllib.parse
import random
import glob as _glob
import subprocess

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
    direct = [
        "arialbd.ttf",
        "arial.ttf",
        "DejaVuSans-Bold.ttf",
        "DejaVuSans.ttf",
        "LiberationSans-Bold.ttf",
        "LiberationSans-Regular.ttf",
        "NotoSans-Bold.ttf",
        "NotoSans-Regular.ttf",
    ]
    for name in direct:
        try:
            ImageFont.truetype(name, 12)
            return name
        except Exception:
            pass

    try:
        result = subprocess.run(
            ["fc-match", "-f", "%{file}", "DejaVu Sans:style=Bold"],
            check=False,
            capture_output=True,
            text=True,
            timeout=3,
        )
        path = result.stdout.strip()
        if path and os.path.exists(path):
            return path
    except Exception:
        pass

    patterns = [
        "/app/backend/fonts/*.ttf",
        "/app/fonts/*.ttf",
        os.path.join(os.path.dirname(__file__), "fonts", "*.ttf"),
        "/nix/store/*/share/fonts/truetype/DejaVuSans-Bold.ttf",
        "/nix/store/*/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/nix/store/*/share/fonts/truetype/ttf-dejavu/DejaVuSans-Bold.ttf",
        "/nix/store/*/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/nix/store/*/share/fonts/truetype/noto/NotoSans-Bold.ttf",
        "/nix/store/*/share/fonts/**/*.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
        "/usr/share/fonts/truetype/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    ]
    for pattern in patterns:
        matches = _glob.glob(pattern, recursive=True)
        preferred = [m for m in matches if os.path.basename(m) in direct]
        for path in preferred + matches:
            try:
                ImageFont.truetype(path, 12)
                return path
            except Exception:
                pass
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
    path = custom_path or _SYSTEM_FONT or _get_custom_font_path("poppins")
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


def _text_line_step(font, draw: ImageDraw, fallback: int) -> int:
    try:
        bbox = draw.textbbox((0, 0), "Ag", font=font)
        return max(1, int((bbox[3] - bbox[1]) * 1.25), fallback)
    except Exception:
        return max(1, fallback)


def _fit_full_text_block(text: str, base_size: int, custom_path: str | None, max_width: int, draw: ImageDraw, max_height: int) -> tuple:
    if not text or max_width <= 0 or max_height <= 0:
        font = _load_font(max(8, base_size), custom_path)
        return font, [], 1

    min_size = 2
    for size in range(max(8, base_size), min_size - 1, -1):
        font = _load_font(size, custom_path)
        line_step = _text_line_step(font, draw, max(1, int(size * 1.38)))
        lines = _wrap_text(text, font, max_width, draw)
        if len(lines) * line_step <= max_height:
            return font, lines, line_step

    font = _load_font(min_size, custom_path)
    line_step = _text_line_step(font, draw, max(1, int(min_size * 1.30)))
    return font, _wrap_text(text, font, max_width, draw), line_step


def _fit_single_line_font(text: str, base_size: int, custom_path: str | None, max_width: int, draw: ImageDraw) -> ImageFont.ImageFont:
    min_size = max(7, int(base_size * 0.45))
    for size in range(max(8, base_size), min_size - 1, -1):
        font = _load_font(size, custom_path)
        bbox = draw.textbbox((0, 0), text, font=font)
        if bbox[2] - bbox[0] <= max_width:
            return font
    return _load_font(min_size, custom_path)


def _draw_cta_button(
    draw: ImageDraw,
    box: tuple[int, int, int, int],
    text: str,
    base_size: int,
    custom_path: str | None,
    fill,
    text_fill,
    radius: int,
    pad_ratio: float = 0.12,
):
    x1, y1, x2, y2 = box
    btn_w = max(1, x2 - x1)
    text_pad = max(8, int(btn_w * pad_ratio))
    font = _fit_single_line_font(text, base_size, custom_path, max(1, btn_w - text_pad * 2), draw)
    draw.rounded_rectangle([x1, y1, x2, y2], radius=radius, fill=fill)
    draw.text(((x1 + x2) // 2, (y1 + y2) // 2), text, font=font, fill=text_fill, anchor="mm")


def _draw_text_lines(draw: ImageDraw, lines: list[str], x: int, y: int, font, fill, line_step: int, anchor: str | None = None):
    for line in lines:
        if anchor:
            draw.text((x, y), line, font=font, fill=fill, anchor=anchor)
        else:
            draw.text((x, y), line, font=font, fill=fill)
        y += line_step


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


def _resize_cover(img: Image.Image, width: int, height: int) -> Image.Image:
    """Scale without distortion, filling the whole target canvas."""
    src = img.convert("RGB")
    scale = max(width / max(src.width, 1), height / max(src.height, 1))
    new_w = max(width, int(src.width * scale))
    new_h = max(height, int(src.height * scale))
    resized = src.resize((new_w, new_h), Image.LANCZOS)
    left = max(0, (new_w - width) // 2)
    top = max(0, (new_h - height) // 2)
    return resized.crop((left, top, left + width, top + height))


def _crop_flat_frame(img: Image.Image) -> Image.Image:
    """Remove large uniform stock-image frames before scaling."""
    def _largest_run(values: list[int]) -> tuple[int, int] | None:
        if not values:
            return None
        best = (values[0], values[0])
        start = prev = values[0]
        for value in values[1:]:
            if value == prev + 1:
                prev = value
                continue
            if prev - start > best[1] - best[0]:
                best = (start, prev)
            start = prev = value
        if prev - start > best[1] - best[0]:
            best = (start, prev)
        return best

    src = img.convert("RGB")
    sw = 240
    sh = max(1, round(sw * src.height / max(src.width, 1)))
    small = src.resize((sw, sh), Image.BILINEAR)
    pix = small.load()

    edge = max(3, min(sw, sh) // 25)
    bins: dict[tuple[int, int, int], list[tuple[int, int, int]]] = {}
    edge_count = 0
    for y in range(sh):
        for x in range(sw):
            if x >= edge and x < sw - edge and y >= edge and y < sh - edge:
                continue
            rgb = pix[x, y]
            key = tuple(v // 16 for v in rgb)
            bins.setdefault(key, []).append(rgb)
            edge_count += 1

    if not bins:
        return src

    dominant = max(bins.values(), key=len)
    if len(dominant) / max(edge_count, 1) < 0.45:
        return src

    border = tuple(sum(c[i] for c in dominant) // len(dominant) for i in range(3))

    def differs(rgb: tuple[int, int, int]) -> bool:
        return sum((rgb[i] - border[i]) ** 2 for i in range(3)) ** 0.5 > 58

    col_counts = [0] * sw
    row_counts = [0] * sh
    for y in range(sh):
        for x in range(sw):
            if differs(pix[x, y]):
                col_counts[x] += 1
                row_counts[y] += 1

    min_col = max(3, int(sh * 0.075))
    min_row = max(3, int(sw * 0.075))
    xs = [i for i, count in enumerate(col_counts) if count >= min_col]
    ys = [i for i, count in enumerate(row_counts) if count >= min_row]
    x_run = _largest_run(xs)
    y_run = _largest_run(ys)
    if not x_run or not y_run:
        return src

    left, right = x_run[0], x_run[1] + 1
    top, bottom = y_run[0], y_run[1] + 1
    crop_w = right - left
    crop_h = bottom - top
    if crop_w > sw * 0.90 and crop_h > sh * 0.90:
        return src
    if crop_w < sw * 0.25 or crop_h < sh * 0.15:
        return src

    margin_x = max(1, int(crop_w * 0.035))
    margin_y = 0
    left = max(0, left - margin_x)
    right = min(sw, right + margin_x)
    top = max(0, top - margin_y)
    bottom = min(sh, bottom + margin_y)

    scale_x = src.width / sw
    scale_y = src.height / sh
    box = (
        int(left * scale_x),
        int(top * scale_y),
        int(right * scale_x),
        int(bottom * scale_y),
    )
    if box[2] <= box[0] or box[3] <= box[1]:
        return src
    print(f"[_crop_flat_frame] cropped stock frame {src.size} -> {(box[2] - box[0], box[3] - box[1])}")
    return src.crop(box)


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

POLLINATIONS_FREE_MODEL = "sana"


def _normalize_ai_model(model: str) -> str:
    return POLLINATIONS_FREE_MODEL if model != POLLINATIONS_FREE_MODEL else model


def fetch_background(sector: str, hint: str, width: int, height: int, source: str = "ai", ai_model: str = POLLINATIONS_FREE_MODEL, style_preset: str = "") -> Image.Image | None:
    if source == "ai":
        gen_w = 512
        gen_h = max(256, round(gen_w * height / width))
        keywords = SECTOR_KEYWORDS.get(sector, SECTOR_KEYWORDS["autre"])
        style_suffix = STYLE_PROMPTS.get(style_preset, "professional advertisement photography, cinematic lighting, ultra high quality")
        prompt = f"{hint}, {keywords}, {style_suffix}"
        encoded = urllib.parse.quote(prompt)
        safe_model = _normalize_ai_model(ai_model)

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
                result = _resize_cover(img, width, height)
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
            return _resize_cover(_crop_flat_frame(img), width, height)
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
    ai_model: str = POLLINATIONS_FREE_MODEL,
    logo_b64: str = "",           # PNG with alpha, base64-encoded
    product_b64: str = "",        # PNG with alpha (removed bg), base64-encoded
    style_preset: str = "",       # "" | "luxury" | "minimal" | "bold" | "ugc"
    photo_layout: str = "overlay", # "overlay" | "split"
    font_family: str = "",        # "" | "poppins" | "montserrat" | etc.
    background_b64: str = "",     # background pré-récupéré côté client (évite l'appel Pollinations)
) -> tuple:
    width, height = AD_FORMATS.get(format_key, AD_FORMATS["feed"])
    primary = _hex_to_rgb(primary_color)
    secondary = _hex_to_rgb(secondary_color)

    custom_font = _get_custom_font_path(font_family)

    bg = None
    # 1. Background pré-récupéré par le navigateur — prioritaire
    if background_b64:
        try:
            data = base64.b64decode(background_b64)
            prefetched = Image.open(io.BytesIO(data)).convert("RGB")
            bg = _resize_cover(prefetched, width, height)
            print(f"[generate_ad] used client-prefetched background for {format_key}")
        except Exception as e:
            print(f"[generate_ad] prefetched bg decode failed: {e}")

    # 2. Fallback : récupération server-side (stock ou IA sans prefetch)
    if bg is None and image_source in ("stock", "ai"):
        bg = fetch_background(sector, f"{brand_name} {tagline}", width, height, image_source, ai_model, style_preset)

    actual_source = image_source if bg is not None else "none"

    if bg is not None:
        # The frame layout is still excluded because its border color clashes with
        # saturated secondaries. The user now explicitly chooses overlay vs split.
        photo_lv = 1 if photo_layout == "split" else 0
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

    # CTA button
    btn_w, btn_h = int(w * 0.52), int(h * 0.072)
    bx, by = pad, int(h * 0.87)

    # Description
    y_desc = y + int(h * 0.02)
    desc_bottom = by - int(h * 0.035)
    font_desc, lines, desc_step = _fit_full_text_block(desc, int(h * 0.030), cf, w - pad * 2, draw, desc_bottom - y_desc)
    _draw_text_lines(draw, lines, pad, y_desc, font_desc, (200, 200, 210), desc_step)

    accent = _contrast_color(secondary)
    _draw_cta_button(draw, (bx, by, bx + btn_w, by + btn_h), cta.upper(), int(h * 0.034), cf, secondary, accent, btn_h // 2)

    return img


def _photo_split(bg, w, h, brand, tagline, desc, cta, primary, secondary, cf=None):
    """Full-width photo with a tinted text panel on the left."""
    img = _resize_cover(bg, w, h).convert("RGBA")
    half = w // 2
    left = Image.new("RGBA", (half, h), (*primary, 224))
    img.alpha_composite(left, (0, 0))
    img = img.convert("RGB")

    draw = ImageDraw.Draw(img)
    text_color = _contrast_color(primary)
    pad = int(w * 0.05)

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

    # CTA
    btn_w, btn_h = int(half - pad * 1.15), int(h * 0.072)
    bx, by = pad, int(h * 0.83)

    # Description
    y_desc = max(int(h * 0.57), y + int(h * 0.035))
    desc_bottom = by - int(h * 0.035)
    font_desc, lines, desc_step = _fit_full_text_block(desc, int(h * 0.028), cf, half - pad * 2, draw, desc_bottom - y_desc)
    _draw_text_lines(draw, lines, pad, y_desc, font_desc, text_color, desc_step)

    accent = _contrast_color(secondary)
    _draw_cta_button(draw, (bx, by, bx + btn_w, by + btn_h), cta.upper(), int(h * 0.032), cf, secondary, accent, 6, pad_ratio=0.08)

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

    btn_w, btn_h = int(card_w * 0.65), int(h * 0.072)
    bx = (w - btn_w) // 2
    by = pad_y + card_h - btn_h - int(h * 0.06)

    y_desc = max(pad_y + int(h * 0.50), y + int(h * 0.030))
    desc_bottom = by - int(h * 0.035)
    font_desc, lines, desc_step = _fit_full_text_block(desc, int(h * 0.027), cf, inner_w, draw, desc_bottom - y_desc)
    _draw_text_lines(draw, lines, w // 2, y_desc, font_desc, white, desc_step, anchor="mm")

    accent = _contrast_color(secondary)
    _draw_cta_button(draw, (bx, by, bx + btn_w, by + btn_h), cta.upper(), int(h * 0.032), cf, secondary, accent, btn_h // 2)

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

    # CTA pill button
    btn_w, btn_h = int(w * 0.58), int(h * 0.076)
    bx, by = pad, int(h * 0.865)

    # Description
    y_desc = max(int(h * 0.55), y + int(h * 0.030))
    desc_bottom = by - int(h * 0.035)
    font_desc, desc_lines, desc_step = _fit_full_text_block(desc, int(h * 0.028), cf, w - pad * 2, draw, desc_bottom - y_desc)
    _draw_text_lines(draw, desc_lines, pad, y_desc, font_desc, muted, desc_step)

    _draw_cta_button(draw, (bx, by, bx + btn_w, by + btn_h), cta.upper(), int(h * 0.034), cf, secondary, accent_btn, btn_h // 2)

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

    # Left: CTA
    btn_w, btn_h = int(half - pad * 1.20), int(h * 0.07)
    bx, by = pad, int(h * 0.82)

    # Left: description
    y_desc = int(h * 0.30)
    desc_bottom = by - int(h * 0.035)
    font_desc, desc_lines, desc_step = _fit_full_text_block(desc, int(h * 0.026), cf, half - pad * 2, draw, desc_bottom - y_desc)
    _draw_text_lines(draw, desc_lines, pad, y_desc, font_desc, muted_left, desc_step)

    _draw_cta_button(draw, (bx, by, bx + btn_w, by + btn_h), cta.upper(), int(h * 0.032), cf, text_left, primary, 6, pad_ratio=0.08)

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

    # CTA — wide, rounded rect
    btn_w, btn_h = int(w * 0.82), int(h * 0.082)
    bx = (w - btn_w) // 2
    by = int(h * 0.855)

    # Description
    y_desc = max(int(h * 0.63), y + int(h * 0.030))
    desc_bottom = by - int(h * 0.035)
    font_desc, desc_lines, desc_step = _fit_full_text_block(desc, int(h * 0.027), cf, w - pad * 2, draw, desc_bottom - y_desc)
    _draw_text_lines(draw, desc_lines, pad, y_desc, font_desc, muted, desc_step)

    _draw_cta_button(draw, (bx, by, bx + btn_w, by + btn_h), cta.upper(), int(h * 0.036), cf, secondary, accent_btn, 10)

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

    # CTA button
    btn_w, btn_h = int(inner_w * 0.78), int(h * 0.074)
    bx = (w - btn_w) // 2
    by = card_y2 - btn_h - int(h * 0.044)

    # Description
    muted = _blend(text_color, glass_color, 0.40)
    y_desc = max(card_y1 + int(h * 0.510), y + int(h * 0.030))
    desc_bottom = by - int(h * 0.035)
    font_desc, desc_lines, desc_step = _fit_full_text_block(desc, int(h * 0.026), cf, inner_w, draw, desc_bottom - y_desc)
    _draw_text_lines(draw, desc_lines, w // 2, y_desc, font_desc, muted, desc_step, anchor="mm")

    _draw_cta_button(draw, (bx, by, bx + btn_w, by + btn_h), cta.upper(), int(h * 0.034), cf, secondary, accent_btn, btn_h // 2)

    # Decorative corner circles in background (outside card)
    deco = _blend(primary, secondary, 0.30)
    rr = int(w * 0.18)
    draw.ellipse([(w - rr, h - rr), (w + rr, h + rr)], fill=deco)
    draw.ellipse([(-rr // 2, -rr // 2), (rr // 2, rr // 2)], fill=_blend(primary, secondary, 0.15))
