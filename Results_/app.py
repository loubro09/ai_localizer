from __future__ import annotations

import io
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from PIL import Image, ImageDraw, ImageFont
from starlette.requests import Request

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = Path(os.getenv("DATA_FILE", BASE_DIR / "data" / "tests.xlsx"))
MAPS_DIR = Path(os.getenv("MAPS_DIR", BASE_DIR / "static" / "maps"))
MAX_GRID_X = int(os.getenv("MAX_GRID_X", "54"))
MAX_GRID_Y = int(os.getenv("MAX_GRID_Y", "44"))
SHEET_NAMES_RAW = os.getenv("SHEET_NAMES", "")
SHEET_NAMES = [name.strip() for name in SHEET_NAMES_RAW.split(",") if name.strip()]


@dataclass
class TestCase:
    index: int
    test_id: str
    floor: str
    image_id: str
    image_type: str
    true_x: float
    true_y: float
    predicted_x: float
    predicted_y: float
    euclidean_error: float | None
    reasoning: str
    source_sheet: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "test_id": self.test_id,
            "floor": self.floor,
            "image_id": self.image_id,
            "image_type": self.image_type,
            "true_x": self.true_x,
            "true_y": self.true_y,
            "predicted_x": self.predicted_x,
            "predicted_y": self.predicted_y,
            "euclidean_error": self.euclidean_error,
            "reasoning": self.reasoning,
            "source_sheet": self.source_sheet,
        }


@dataclass
class TestGroup:
    index: int
    floor: str
    image_id: str
    image_type: str
    true_x: float
    true_y: float
    cases: list[TestCase]

    def as_dict(self) -> dict[str, Any]:
        errors = [c.euclidean_error for c in self.cases if c.euclidean_error is not None]
        min_error = min(errors) if errors else None
        max_error = max(errors) if errors else None
        spread = (max_error - min_error) if errors else None

        return {
            "index": self.index,
            "group_label": f"{self.floor} | {self.image_id}",
            "floor": self.floor,
            "image_id": self.image_id,
            "image_type": self.image_type,
            "true_x": self.true_x,
            "true_y": self.true_y,
            "map_image": map_filename_for_floor(self.floor),
            "case_count": len(self.cases),
            "min_error": min_error,
            "max_error": max_error,
            "spread": spread,
            "cases": [case.as_dict() for case in self.cases],
        }


app = FastAPI(title="Floorplan Test Group Viewer")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

_CASES_CACHE: list[TestCase] | None = None
_GROUPS_CACHE: list[TestGroup] | None = None

COLUMN_ALIASES = {
    "id": "test_id",
    "floor": "floor",
    "image_id": "image_id",
    "image_type": "image_type",
    "true_x": "true_x",
    "true_y": "true_y",
    "predicted_x": "predicted_x",
    "predicted_y": "predicted_y",
    "euclidean_error": "euclidean_error",
    "reasoning": "reasoning",
}

REQUIRED_COLUMNS = {
    "test_id",
    "floor",
    "image_id",
    "image_type",
    "true_x",
    "true_y",
    "predicted_x",
    "predicted_y",
    "reasoning",
}


def normalize_column_name(name: str) -> str:
    return str(name).strip().lower().replace(" ", "_").replace("-", "_").replace("/", "_")


def normalize_dataframe_columns(df: pd.DataFrame) -> pd.DataFrame:
    renamed: dict[str, str] = {}
    for col in df.columns:
        normalized = normalize_column_name(col)
        if normalized in COLUMN_ALIASES:
            renamed[col] = COLUMN_ALIASES[normalized]
    df = df.rename(columns=renamed)

    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(
            "Missing required columns: "
            + ", ".join(sorted(missing))
            + ". Expected columns like Id, Floor, Image id, Image Type, True x, True y, Predicted x, Predicted y, Euclidean error, Reasoning."
        )

    return df


def load_dataframe(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Data file not found: {path}")

    suffix = path.suffix.lower()
    if suffix == ".csv":
        return normalize_dataframe_columns(pd.read_csv(path))

    if suffix in {".xlsx", ".xls"}:
        workbook = pd.read_excel(path, sheet_name=None)
        if not workbook:
            raise ValueError("The Excel workbook does not contain any sheets.")

        selected = workbook
        if SHEET_NAMES:
            missing = [name for name in SHEET_NAMES if name not in workbook]
            if missing:
                raise ValueError("These sheet names were not found in the workbook: " + ", ".join(missing))
            selected = {name: workbook[name] for name in SHEET_NAMES}

        frames: list[pd.DataFrame] = []
        for sheet_name, sheet_df in selected.items():
            normalized = normalize_dataframe_columns(sheet_df.copy())
            normalized["source_sheet"] = sheet_name
            frames.append(normalized)

        combined = pd.concat(frames, ignore_index=True).dropna(how="all")
        return combined

    raise ValueError("Only .csv, .xlsx, and .xls are supported for DATA_FILE.")


def parse_float(value: Any) -> float:
    if pd.isna(value):
        raise ValueError("Encountered a missing coordinate value in the dataset.")
    return float(value)


def parse_optional_float(value: Any) -> float | None:
    if pd.isna(value) or value == "":
        return None
    return float(value)


def load_test_cases(force: bool = False) -> list[TestCase]:
    global _CASES_CACHE, _GROUPS_CACHE
    if _CASES_CACHE is not None and not force:
        return _CASES_CACHE

    df = load_dataframe(DATA_FILE)
    cases: list[TestCase] = []
    for idx, row in df.iterrows():
        cases.append(
            TestCase(
                index=idx,
                test_id=str(row["test_id"]),
                floor=str(row["floor"]).strip(),
                image_id=str(row["image_id"]).strip(),
                image_type=str(row["image_type"]).strip(),
                true_x=parse_float(row["true_x"]),
                true_y=parse_float(row["true_y"]),
                predicted_x=parse_float(row["predicted_x"]),
                predicted_y=parse_float(row["predicted_y"]),
                euclidean_error=parse_optional_float(row.get("euclidean_error")),
                reasoning=str(row["reasoning"]),
                source_sheet=None if pd.isna(row.get("source_sheet")) else str(row.get("source_sheet")),
            )
        )

    if not cases:
        raise ValueError("No usable rows found in the dataset.")

    _CASES_CACHE = cases
    _GROUPS_CACHE = None
    return cases


def build_groups(force: bool = False) -> list[TestGroup]:
    global _GROUPS_CACHE
    if _GROUPS_CACHE is not None and not force:
        return _GROUPS_CACHE

    cases = load_test_cases(force=force)
    grouped: dict[tuple[str, str], list[TestCase]] = {}
    for case in cases:
        key = (case.floor, case.image_id)
        grouped.setdefault(key, []).append(case)

    groups: list[TestGroup] = []
    for idx, ((floor, image_id), group_cases) in enumerate(sorted(grouped.items(), key=lambda item: (item[0][0], item[0][1]))):
        first = group_cases[0]
        groups.append(
            TestGroup(
                index=idx,
                floor=floor,
                image_id=image_id,
                image_type=first.image_type,
                true_x=first.true_x,
                true_y=first.true_y,
                cases=group_cases,
            )
        )

    _GROUPS_CACHE = groups
    return groups


def map_filename_for_floor(floor: str) -> str:
    floor_lower = floor.strip().lower()
    if floor_lower in {"floor 3", "3", "third floor"}:
        return "floor3.png"
    if floor_lower in {"floor 5", "5", "fifth floor"}:
        return "floor5.png"
    raise ValueError(f"Unsupported floor value: {floor}")


def map_path_for_floor(floor: str) -> Path:
    path = MAPS_DIR / map_filename_for_floor(floor)
    if not path.exists():
        raise FileNotFoundError(f"Map image not found for {floor}: {path}")
    return path


def grid_to_pixel(grid_x: float, grid_y: float, width: int, height: int) -> tuple[int, int]:
    px = round(grid_x / MAX_GRID_X * (width - 1))
    py = round(grid_y / MAX_GRID_Y * (height - 1))
    return px, py


def get_font(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size)
    except Exception:
        return ImageFont.load_default()


def draw_marker(draw: ImageDraw.ImageDraw, x: int, y: int, fill: tuple[int, int, int, int], label: str, radius: int, font: ImageFont.ImageFont) -> None:
    draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=fill, outline=(255, 255, 255, 255), width=3)
    tx = x + radius + 6
    ty = y - radius - 4
    bbox = draw.textbbox((tx, ty), label, font=font)
    draw.rounded_rectangle((bbox[0] - 4, bbox[1] - 2, bbox[2] + 4, bbox[3] + 2), radius=4, fill=(255, 255, 255, 220))
    draw.text((tx, ty), label, font=font, fill=(0, 0, 0, 255))


def render_annotated_map(group: TestGroup) -> bytes:
    with Image.open(map_path_for_floor(group.floor)).convert("RGBA") as img:
        draw = ImageDraw.Draw(img, "RGBA")
        font = get_font(max(14, img.width // 55))
        small_font = get_font(max(12, img.width // 70))
        radius = max(8, min(img.size) // 90)

        actual_x, actual_y = grid_to_pixel(group.true_x, group.true_y, img.width, img.height)
        draw_marker(draw, actual_x, actual_y, (30, 160, 60, 255), "Actual", radius + 1, font)

        for idx, case in enumerate(group.cases, start=1):
            pred_x, pred_y = grid_to_pixel(case.predicted_x, case.predicted_y, img.width, img.height)
            draw.line((actual_x, actual_y, pred_x, pred_y), fill=(255, 140, 0, 190), width=max(2, radius // 3))
            label = str(idx)
            draw_marker(draw, pred_x, pred_y, (220, 40, 40, 235), label, radius, small_font)

        legend_lines = [
            f"{group.floor} | {group.image_id} | {group.image_type}",
            f"Actual: ({group.true_x:g}, {group.true_y:g})",
            f"Predictions shown: {len(group.cases)}",
        ]
        pad = 12
        gap = 6
        widths, heights = [], []
        for line in legend_lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            widths.append(bbox[2] - bbox[0])
            heights.append(bbox[3] - bbox[1])
        box_w = min(max(widths) + pad * 2, img.width - 20)
        box_h = sum(heights) + gap * (len(legend_lines) - 1) + pad * 2
        box = (10, 10, 10 + box_w, 10 + box_h)
        draw.rounded_rectangle(box, radius=12, fill=(255, 255, 255, 220), outline=(140, 140, 140, 255), width=2)
        y = 10 + pad
        for line in legend_lines:
            draw.text((10 + pad, y), line, font=font, fill=(0, 0, 0, 255))
            bbox = draw.textbbox((10 + pad, y), line, font=font)
            y = bbox[3] + gap

        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        return buffer.getvalue()


def get_group_or_404(index: int) -> TestGroup:
    groups = build_groups()
    if index < 0 or index >= len(groups):
        raise HTTPException(status_code=404, detail="Group index out of range.")
    return groups[index]


@app.get("/", response_class=HTMLResponse)
def home(request: Request) -> HTMLResponse:
    groups = build_groups()
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "group_count": len(groups),
            "first_group": groups[0].as_dict(),
            "max_index": len(groups) - 1,
        },
    )


@app.get("/api/groups")
def list_groups() -> JSONResponse:
    groups = [group.as_dict() for group in build_groups()]
    return JSONResponse({"count": len(groups), "items": groups})


@app.get("/api/groups/{index}")
def get_group(index: int) -> JSONResponse:
    return JSONResponse(get_group_or_404(index).as_dict())


@app.get("/api/groups/{index}/map")
def get_group_map(index: int) -> StreamingResponse:
    image_bytes = render_annotated_map(get_group_or_404(index))
    return StreamingResponse(io.BytesIO(image_bytes), media_type="image/png")


@app.post("/api/reload")
def reload_data() -> JSONResponse:
    global _CASES_CACHE, _GROUPS_CACHE
    _CASES_CACHE = None
    _GROUPS_CACHE = None
    groups = build_groups(force=True)
    return JSONResponse({"reloaded": True, "group_count": len(groups)})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
