"""
This is the main entry point for the FastAPI application.
It defines the API endpoints and handles file uploads for floorplan
localization.
"""
import os
import shutil
import tempfile
from pathlib import Path
import base64
import io

from PIL import Image, ImageDraw
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse

load_dotenv()

from openai_service_dot_test import localize_dot_from_files
from schemas_dot_test import DotTestResponse

app = FastAPI(title="Floorplan Localizer")


def pixel_to_grid(
    dot_x: int,
    dot_y: int,
    width: int,
    height: int,
    max_grid_x: int = 54,
    max_grid_y: int = 44,
) -> tuple[int, int]:
    grid_x = round(dot_x / (width - 1) * max_grid_x)
    grid_y = round(dot_y / (height - 1) * max_grid_y)
    return grid_x, grid_y


def draw_dot_on_floorplan(image_path: str, x: int, y: int) -> str:
    with Image.open(image_path).convert("RGBA") as img:
        draw = ImageDraw.Draw(img)

        radius = max(8, min(img.size) // 80)

        left = x - radius
        top = y - radius
        right = x + radius
        bottom = y + radius

        draw.ellipse((left, top, right, bottom), fill=(255, 0, 0, 255))
        draw.ellipse(
            (left - 2, top - 2, right + 2, bottom + 2),
            outline=(255, 255, 255, 255),
            width=2,
        )

        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
        return encoded


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return """
    <html>
      <body style="font-family: sans-serif; max-width: 1100px; margin: 40px auto;">
        <h1>Floorplan Localizer</h1>

        <form id="dotTestForm" enctype="multipart/form-data" style="margin-bottom: 24px;">
          <div style="margin-bottom: 12px;">
            <label>Floorplan PNG:</label><br>
            <input type="file" id="dotFloorplanInput" name="floorplan" accept="image/*" required>
          </div>

          <div style="margin-bottom: 12px;">
            <label>Query image:</label><br>
            <input type="file" id="dotQueryInput" name="query" accept="image/*" required>
          </div>

          <button type="submit">Run Test</button>
        </form>

        <div style="display: flex; gap: 24px; align-items: flex-start; flex-wrap: wrap;">
          <div style="flex: 1 1 700px; min-width: 300px;">
            <h2>Floorplan Preview</h2>
            <img
              id="floorplanPreview"
              alt="Floorplan preview"
              style="width: 100%; border: 1px solid #ccc; display: none;"
            />
          </div>

          <div style="flex: 0 0 300px;">
            <h2>Query Preview</h2>
            <img
              id="queryPreview"
              alt="Query image preview"
              style="width: 100%; max-width: 240px; border: 1px solid #ccc; display: none; margin-bottom: 16px;"
            />

            <h2>Dot Test Result</h2>
            <div
              id="dotResultBox"
              style="border: 1px solid #ccc; padding: 12px; min-height: 80px; background: #f9f9f9;"
            >No result yet.</div>
          </div>
        </div>

        <script>
          const dotTestForm = document.getElementById("dotTestForm");
          const dotFloorplanInput = document.getElementById("dotFloorplanInput");
          const dotQueryInput = document.getElementById("dotQueryInput");
          const floorplanPreview = document.getElementById("floorplanPreview");
          const queryPreview = document.getElementById("queryPreview");
          const dotResultBox = document.getElementById("dotResultBox");

          dotFloorplanInput.addEventListener("change", function () {
            const file = this.files[0];

            if (!file) {
              floorplanPreview.src = "";
              floorplanPreview.style.display = "none";
              return;
            }

            if (!file.type.startsWith("image/")) {
              alert("Please upload an image file for the floorplan.");
              dotFloorplanInput.value = "";
              floorplanPreview.src = "";
              floorplanPreview.style.display = "none";
              return;
            }

            floorplanPreview.src = URL.createObjectURL(file);
            floorplanPreview.style.display = "block";
          });

          dotQueryInput.addEventListener("change", function () {
            const file = this.files[0];

            if (!file) {
              queryPreview.src = "";
              queryPreview.style.display = "none";
              return;
            }

            if (!file.type.startsWith("image/")) {
              alert("Please upload an image file for the query.");
              dotQueryInput.value = "";
              queryPreview.src = "";
              queryPreview.style.display = "none";
              return;
            }

            queryPreview.src = URL.createObjectURL(file);
            queryPreview.style.display = "block";
          });

          dotTestForm.addEventListener("submit", async function (event) {
            event.preventDefault();

            const floorplanFile = dotFloorplanInput.files[0];
            const queryFile = dotQueryInput.files[0];

            if (!floorplanFile || !queryFile) {
              dotResultBox.textContent = "Please select both a floorplan image and a query image.";
              return;
            }

            const formData = new FormData();
            formData.append("floorplan", floorplanFile);
            formData.append("query", queryFile);

            dotResultBox.textContent = "Running dot test...";

            try {
              const response = await fetch("/test-dot", {
                method: "POST",
                body: formData
              });

              const data = await response.json();

              if (!response.ok) {
                dotResultBox.textContent = "Error: " + (data.detail || "Unknown error");
                return;
              }

              dotResultBox.innerHTML = `
                <div style="margin-bottom: 10px;"><strong>Predicted dot location</strong></div>
                <div><strong>dot_x:</strong> ${data.dot_x}</div>
                <div><strong>dot_y:</strong> ${data.dot_y}</div>
                <div><strong>grid_x:</strong> ${data.grid_x}</div>
                <div><strong>grid_y:</strong> ${data.grid_y}</div>
                <div style="margin-top: 10px;"><strong>Reasoning:</strong> ${data.reasoning}</div>
              `;

              floorplanPreview.src = "data:image/png;base64," + data.annotated_image_base64;
              floorplanPreview.style.display = "block";
            } catch (error) {
              dotResultBox.textContent = "Error: " + error.message;
            }
          });
        </script>
      </body>
    </html>
    """


@app.post("/test-dot", response_model=DotTestResponse)
async def test_dot(
    floorplan: UploadFile = File(...),
    query: UploadFile = File(...),
) -> DotTestResponse:
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY is not set.")

    if not floorplan.content_type or not floorplan.content_type.startswith("image/"):
        raise HTTPException(
            status_code=400,
            detail="Floorplan must be an image file for dot test (recommended: PNG).",
        )

    if not query.content_type or not query.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Query must be an image file.")

    temp_dir = tempfile.mkdtemp(prefix="dot_test_")

    try:
        floorplan_ext = Path(floorplan.filename or "floorplan.png").suffix or ".png"
        query_ext = Path(query.filename or "query.jpg").suffix or ".jpg"

        floorplan_path = os.path.join(temp_dir, f"floorplan{floorplan_ext}")
        query_path = os.path.join(temp_dir, f"query{query_ext}")

        with open(floorplan_path, "wb") as f:
            shutil.copyfileobj(floorplan.file, f)

        with open(query_path, "wb") as f:
            shutil.copyfileobj(query.file, f)

        result = localize_dot_from_files(floorplan_path, query_path)

        with Image.open(floorplan_path) as img:
            width, height = img.size

        grid_x, grid_y = pixel_to_grid(
            result.dot_x,
            result.dot_y,
            width,
            height,
        )

        annotated_image_base64 = draw_dot_on_floorplan(
            floorplan_path,
            result.dot_x,
            result.dot_y,
        )

        return {
            "dot_x": result.dot_x,
            "dot_y": result.dot_y,
            "grid_x": grid_x,
            "grid_y": grid_y,
            "reasoning": result.reasoning,
            "annotated_image_base64": annotated_image_base64,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)