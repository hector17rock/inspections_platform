"""Genera los iconos PNG para la PWA de OPD Orders."""

from PIL import Image, ImageDraw, ImageFont

from paths import STATIC_DIR


BLUE  = (0, 30, 96)    # walmart deep navy #001e60
SPARK = (255, 194, 32)  # walmart spark.100
WHITE = (255, 255, 255)


def _draw_icon(size: int) -> Image.Image:
    img = Image.new("RGB", (size, size), BLUE)
    draw = ImageDraw.Draw(img)

    # Spark star shape (simplified circle accent)
    margin = size // 8
    draw.ellipse(
        [margin, margin, size - margin, size - margin],
        outline=SPARK,
        width=max(2, size // 24),
    )

    # Text "OPD"
    font_size = size // 4
    try:
        font = ImageFont.truetype("arial.ttf", font_size)
    except OSError:
        font = ImageFont.load_default()

    text = "OPD"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((size - tw) / 2, (size - th) / 2 - size // 16), text, fill=WHITE, font=font)

    return img


def main() -> None:
    out = STATIC_DIR
    out.mkdir(parents=True, exist_ok=True)

    for px in (192, 512):
        path = out / f"icon-{px}.png"
        _draw_icon(px).save(path, "PNG")
        print(f"Generado: {path}")


if __name__ == "__main__":
    main()
