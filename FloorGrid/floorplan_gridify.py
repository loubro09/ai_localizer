from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

import fitz
from PIL import Image, ImageDraw, ImageFont


@dataclass
class GridStyle:
    render_scale: float = 3.0

    minor_line_color: Tuple[int, int, int, int] = (0, 120, 255, 120)
    major_line_color: Tuple[int, int, int, int] = (0, 120, 255, 200)
    text_color: Tuple[int, int, int, int] = (0, 70, 180, 220)
    note_color: Tuple[int, int, int, int] = (90, 90, 90, 210)

    minor_line_width: int = 2
    major_line_width: int = 3
    major_every_m: int = 5
    label_every_m: int = 5

    font_size: int = 18
    small_font_size: int = 14


class FloorplanGridder:
    def __init__(self, style: Optional[GridStyle] = None) -> None:
        self.style = style or GridStyle()

    def render_first_page(self, pdf_path: str | Path) -> Image.Image:
        doc = fitz.open(str(pdf_path))
        page = doc[0]

        pix = page.get_pixmap(
            matrix=fitz.Matrix(self.style.render_scale, self.style.render_scale),
            alpha=False,
        )

        return Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

    def _load_fonts(self):
        try:
            font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", self.style.font_size)
            small_font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", self.style.small_font_size)
            return font, small_font
        except:
            return None, None

    def add_grid(self, img: Image.Image, px_per_meter: float) -> Image.Image:
        base = img.convert("RGBA")
        overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        step = max(1, round(px_per_meter))
        major_step = step * self.style.major_every_m
        label_step = step * self.style.label_every_m

        font, small_font = self._load_fonts()

        # Minor lines (1m)
        for x in range(0, base.size[0], step):
            draw.line([(x, 0), (x, base.size[1])],
                      fill=self.style.minor_line_color,
                      width=self.style.minor_line_width)

        for y in range(0, base.size[1], step):
            draw.line([(0, y), (base.size[0], y)],
                      fill=self.style.minor_line_color,
                      width=self.style.minor_line_width)

        # Major lines (5m)
        for x in range(0, base.size[0], major_step):
            draw.line([(x, 0), (x, base.size[1])],
                      fill=self.style.major_line_color,
                      width=self.style.major_line_width)

        for y in range(0, base.size[1], major_step):
            draw.line([(0, y), (base.size[0], y)],
                      fill=self.style.major_line_color,
                      width=self.style.major_line_width)

        # Labels X
        for i, x in enumerate(range(0, base.size[0], label_step)):
            draw.text((x + 5, 5), str(i * self.style.label_every_m),
                      fill=self.style.text_color, font=font)

        # Labels Y
        for i, y in enumerate(range(0, base.size[1], label_step)):
            draw.text((5, y + 5), str(i * self.style.label_every_m),
                      fill=self.style.text_color, font=font)

        # Note
        note = "Grid: 1 meter per square\nOrigin: top-left"
        draw.multiline_text(
            (base.size[0] - 260, 10),
            note,
            fill=self.style.note_color,
            font=small_font,
        )

        return Image.alpha_composite(base, overlay).convert("RGB")

    def process_pdf(
        self,
        pdf_path: str | Path,
        output_png: str | Path,
        output_pdf: Optional[str | Path] = None,
    ):
        rendered = self.render_first_page(pdf_path)

        # 🔥 ONLY THING THAT MATTERS
        px_per_meter = 82  # ← CHANGE THIS

        result = self.add_grid(rendered, px_per_meter)

        output_png = Path(output_png)
        result.save(output_png)

        saved_pdf = None
        if output_pdf:
            output_pdf = Path(output_pdf)
            result.save(output_pdf, "PDF")
            saved_pdf = output_pdf

        return output_png, saved_pdf


if __name__ == "__main__":
    gridder = FloorplanGridder()

    input_pdf = Path("floorplan") / "A-40-1-A1400.pdf"
    output_png = Path("Grid_floorplan") / "A-40-1-A1400_grid.png"
    output_pdf = Path("Grid_floorplan") / "A-40-1-A1400_grid.pdf"

    output_png.parent.mkdir(parents=True, exist_ok=True)

    png_path, pdf_path = gridder.process_pdf(
        pdf_path=input_pdf,
        output_png=output_png,
        output_pdf=output_pdf,
    )

    print("Saved PNG:", png_path)
    print("Saved PDF:", pdf_path)