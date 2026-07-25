"""Generate the VoiceCode application icon assets."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = ROOT / "assets"
SIZE = 1024
SCALE = 4
CANVAS = SIZE * SCALE


def point(value: int) -> int:
    return value * SCALE


def rounded_gradient() -> Image.Image:
    image = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    gradient = Image.new("RGBA", (CANVAS, CANVAS))
    pixels = gradient.load()
    for y in range(CANVAS):
        ratio = y / max(1, CANVAS - 1)
        for x in range(CANVAS):
            radial = max(
                0.0, 1.0 - (((x - point(360)) ** 2 + (y - point(250)) ** 2) ** 0.5) / point(900)
            )
            red = round(8 + 9 * (1 - ratio) + 3 * radial)
            green = round(15 + 14 * (1 - ratio) + 20 * radial)
            blue = round(34 + 24 * (1 - ratio) + 31 * radial)
            pixels[x, y] = (red, green, blue, 255)
    mask = Image.new("L", (CANVAS, CANVAS), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (point(36), point(36), point(988), point(988)), radius=point(220), fill=255
    )
    image.alpha_composite(Image.composite(gradient, Image.new("RGBA", image.size), mask))
    return image


def build_icon() -> Image.Image:
    image = rounded_gradient()

    glow = Image.new("RGBA", image.size, (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    glow_draw.ellipse((point(228), point(188), point(796), point(756)), fill=(29, 225, 255, 95))
    glow = glow.filter(ImageFilter.GaussianBlur(point(80)))
    image.alpha_composite(glow)

    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle(
        (point(52), point(52), point(972), point(972)),
        radius=point(205),
        outline=(122, 225, 255, 90),
        width=point(10),
    )

    # Code brackets frame the microphone without relying on text or fonts.
    draw.line(
        [(point(318), point(330)), (point(198), point(512)), (point(318), point(694))],
        fill=(39, 224, 255, 255),
        width=point(54),
        joint="curve",
    )
    draw.line(
        [(point(706), point(330)), (point(826), point(512)), (point(706), point(694))],
        fill=(151, 104, 255, 255),
        width=point(54),
        joint="curve",
    )

    # Microphone capsule.
    draw.rounded_rectangle(
        (point(414), point(224), point(610), point(600)),
        radius=point(98),
        fill=(237, 251, 255, 255),
    )
    draw.rounded_rectangle(
        (point(454), point(270), point(570), point(552)),
        radius=point(58),
        fill=(20, 43, 76, 255),
    )
    for index, width in enumerate((54, 82, 108, 82, 54)):
        center_x = point(512 + (index - 2) * 22)
        draw.rounded_rectangle(
            (
                center_x - point(width // 10),
                point(334 + abs(index - 2) * 16),
                center_x + point(width // 10),
                point(488 - abs(index - 2) * 16),
            ),
            radius=point(10),
            fill=(50, 225, 255, 255) if index < 2 else (128, 112, 255, 255),
        )

    # Microphone support and compact waveform.
    draw.arc(
        (point(360), point(410), point(664), point(714)),
        start=12,
        end=168,
        fill=(237, 251, 255, 255),
        width=point(34),
    )
    draw.rounded_rectangle(
        (point(494), point(680), point(530), point(790)),
        radius=point(18),
        fill=(237, 251, 255, 255),
    )
    draw.rounded_rectangle(
        (point(404), point(770), point(620), point(814)),
        radius=point(22),
        fill=(237, 251, 255, 255),
    )
    wave_heights = (44, 82, 126, 166, 126, 82, 44)
    for index, height in enumerate(wave_heights):
        x = point(350 + index * 54)
        draw.rounded_rectangle(
            (x, point(872 - height // 2), x + point(22), point(872 + height // 2)),
            radius=point(11),
            fill=(40 + index * 14, 220 - index * 10, 255, 230),
        )

    return image.resize((SIZE, SIZE), Image.Resampling.LANCZOS)


def write_svg() -> None:
    svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1024 1024">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#142c50"/><stop offset="1" stop-color="#080f22"/>
    </linearGradient>
    <linearGradient id="wave" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="#27e0ff"/><stop offset="1" stop-color="#9868ff"/>
    </linearGradient>
  </defs>
  <rect x="36" y="36" width="952" height="952" rx="220" fill="url(#bg)" stroke="#7ae1ff" stroke-opacity=".45" stroke-width="10"/>
  <path d="M318 330 198 512l120 182" fill="none" stroke="#27e0ff" stroke-width="54" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="m706 330 120 182-120 182" fill="none" stroke="#9768ff" stroke-width="54" stroke-linecap="round" stroke-linejoin="round"/>
  <rect x="414" y="224" width="196" height="376" rx="98" fill="#edfbff"/>
  <rect x="454" y="270" width="116" height="282" rx="58" fill="#142b4c"/>
  <path d="M376 500a136 136 0 0 0 272 0M512 636v154M404 792h216" fill="none" stroke="#edfbff" stroke-width="34" stroke-linecap="round"/>
  <path d="M361 850v44m54-63v82m54-103v126m54-147v166m54-145v126m54-105v82m54-63v44" fill="none" stroke="url(#wave)" stroke-width="22" stroke-linecap="round"/>
</svg>
"""
    (ASSET_DIR / "voicecode-icon.svg").write_text(svg, encoding="utf-8", newline="\n")


def main() -> None:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    icon = build_icon()
    icon.save(ASSET_DIR / "voicecode-icon.png", optimize=True)
    icon.save(
        ASSET_DIR / "voicecode-icon.ico",
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    write_svg()
    print(f"Generated VoiceCode icons in {ASSET_DIR}")


if __name__ == "__main__":
    main()
