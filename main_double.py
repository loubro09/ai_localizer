"""
This is the main entry point for the FastAPI application.
It defines the API endpoints and handles file uploads for floorplan
localization using two query images taken from the same position.
"""
import os
import shutil
import tempfile
from pathlib import Path
import base64
import io
import math
from typing import Optional

from PIL import Image, ImageDraw
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse

load_dotenv()

from openai_service_dot_test import localize_dot_from_3_files
from schemas_dot_test import DotTestResponse

app = FastAPI(title="Floorplan Localizer - Double Query")


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


def grid_to_pixel(
    grid_x: int,
    grid_y: int,
    width: int,
    height: int,
    max_grid_x: int = 54,
    max_grid_y: int = 44,
) -> tuple[int, int]:
    pixel_x = round(grid_x / max_grid_x * (width - 1))
    pixel_y = round(grid_y / max_grid_y * (height - 1))
    return pixel_x, pixel_y


def calculate_grid_error(
    predicted_x: int,
    predicted_y: int,
    actual_x: int,
    actual_y: int,
) -> dict:
    dx = predicted_x - actual_x
    dy = predicted_y - actual_y
    euclidean_error = math.sqrt(dx**2 + dy**2)

    return {
        "dx": dx,
        "dy": dy,
        "euclidean_error_m": round(euclidean_error, 3),
    }


def draw_dots_on_floorplan(
    image_path: str,
    predicted_x: int,
    predicted_y: int,
    actual_x: Optional[int] = None,
    actual_y: Optional[int] = None,
) -> str:
    with Image.open(image_path).convert("RGBA") as img:
        draw = ImageDraw.Draw(img)
        radius = max(8, min(img.size) // 80)

        # Predicted dot = red
        left = predicted_x - radius
        top = predicted_y - radius
        right = predicted_x + radius
        bottom = predicted_y + radius

        draw.ellipse((left, top, right, bottom), fill=(255, 0, 0, 255))
        draw.ellipse(
            (left - 2, top - 2, right + 2, bottom + 2),
            outline=(255, 255, 255, 255),
            width=2,
        )

        # Actual dot = green
        if actual_x is not None and actual_y is not None:
            left = actual_x - radius
            top = actual_y - radius
            right = actual_x + radius
            bottom = actual_y + radius

            draw.ellipse((left, top, right, bottom), fill=(0, 180, 0, 255))
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
        <h1>Floorplan Localizer - Double Query</h1>

        <form id="dotTestForm" enctype="multipart/form-data" style="margin-bottom: 24px;">
          <div style="margin-bottom: 12px;">
            <label>Floorplan PNG:</label><br>
            <input type="file" id="dotFloorplanInput" name="floorplan" accept="image/*" required>
          </div>

          <div style="margin-bottom: 12px;">
            <label>Query image 1:</label><br>
            <input type="file" id="dotQuery1Input" name="query1" accept="image/*" required>
          </div>

          <div style="margin-bottom: 12px;">
            <label>Query image 2:</label><br>
            <input type="file" id="dotQuery2Input" name="query2" accept="image/*" required>
          </div>

          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; max-width: 320px; margin-bottom: 12px;">
            <div>
              <label>Actual X (optional):</label><br>
              <input type="number" id="actualDotX" name="actual_x">
            </div>
            <div>
              <label>Actual Y (optional):</label><br>
              <input type="number" id="actualDotY" name="actual_y">
            </div>
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
            <div style="margin-top: 8px; color: #555;">
              Red = predicted, Green = actual
            </div>
          </div>

          <div style="flex: 0 0 320px;">
            <h2>Query 1 Preview</h2>
            <img
              id="query1Preview"
              alt="Query image 1 preview"
              style="width: 100%; max-width: 240px; border: 1px solid #ccc; display: none; margin-bottom: 16px;"
            />

            <h2>Query 2 Preview</h2>
            <img
              id="query2Preview"
              alt="Query image 2 preview"
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
          const dotQuery1Input = document.getElementById("dotQuery1Input");
          const dotQuery2Input = document.getElementById("dotQuery2Input");
          const actualDotXInput = document.getElementById("actualDotX");
          const actualDotYInput = document.getElementById("actualDotY");
          const floorplanPreview = document.getElementById("floorplanPreview");
          const query1Preview = document.getElementById("query1Preview");
          const query2Preview = document.getElementById("query2Preview");
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

          dotQuery1Input.addEventListener("change", function () {
            const file = this.files[0];

            if (!file) {
              query1Preview.src = "";
              query1Preview.style.display = "none";
              return;
            }

            if (!file.type.startsWith("image/")) {
              alert("Please upload an image file for query image 1.");
              dotQuery1Input.value = "";
              query1Preview.src = "";
              query1Preview.style.display = "none";
              return;
            }

            query1Preview.src = URL.createObjectURL(file);
            query1Preview.style.display = "block";
          });

          dotQuery2Input.addEventListener("change", function () {
            const file = this.files[0];

            if (!file) {
              query2Preview.src = "";
              query2Preview.style.display = "none";
              return;
            }

            if (!file.type.startsWith("image/")) {
              alert("Please upload an image file for query image 2.");
              dotQuery2Input.value = "";
              query2Preview.src = "";
              query2Preview.style.display = "none";
              return;
            }

            query2Preview.src = URL.createObjectURL(file);
            query2Preview.style.display = "block";
          });

          dotTestForm.addEventListener("submit", async function (event) {
            event.preventDefault();

            const floorplanFile = dotFloorplanInput.files[0];
            const query1File = dotQuery1Input.files[0];
            const query2File = dotQuery2Input.files[0];
            const actualDotX = actualDotXInput.value;
            const actualDotY = actualDotYInput.value;

            if (!floorplanFile || !query1File || !query2File) {
              dotResultBox.textContent = "Please select a floorplan image and both query images.";
              return;
            }

            const formData = new FormData();
            formData.append("floorplan", floorplanFile);
            formData.append("query1", query1File);
            formData.append("query2", query2File);

            if (actualDotX !== "") {
              formData.append("actual_x", actualDotX);
            }
            if (actualDotY !== "") {
              formData.append("actual_y", actualDotY);
            }

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

              let extraHtml = "";
              if (data.actual_grid_x !== null && data.actual_grid_y !== null) {
                extraHtml = `
                  <hr style="margin: 10px 0;">
                  <div><strong>actual_grid_x:</strong> ${data.actual_grid_x}</div>
                  <div><strong>actual_grid_y:</strong> ${data.actual_grid_y}</div>
                  <div><strong>actual_pixel_x:</strong> ${data.actual_pixel_x}</div>
                  <div><strong>actual_pixel_y:</strong> ${data.actual_pixel_y}</div>
                  <div><strong>dx:</strong> ${data.dx}</div>
                  <div><strong>dy:</strong> ${data.dy}</div>
                  <div><strong>Euclidean error:</strong> ${data.euclidean_error_m} m</div>
                `;
              }

              dotResultBox.innerHTML = `
                <div style="margin-bottom: 10px;"><strong>Predicted dot location</strong></div>
                <div><strong>dot_x:</strong> ${data.dot_x}</div>
                <div><strong>dot_y:</strong> ${data.dot_y}</div>
                <div><strong>grid_x:</strong> ${data.grid_x}</div>
                <div><strong>grid_y:</strong> ${data.grid_y}</div>
                <div style="margin-top: 10px;"><strong>Reasoning:</strong> ${data.reasoning}</div>
                ${extraHtml}
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
    query1: UploadFile = File(...),
    query2: UploadFile = File(...),
    actual_x: Optional[int] = Form(None),
    actual_y: Optional[int] = Form(None),
) -> DotTestResponse:
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY is not set.")

    if not floorplan.content_type or not floorplan.content_type.startswith("image/"):
        raise HTTPException(
            status_code=400,
            detail="Floorplan must be an image file for dot test (recommended: PNG).",
        )

    if not query1.content_type or not query1.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Query image 1 must be an image file.")

    if not query2.content_type or not query2.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Query image 2 must be an image file.")

    temp_dir = tempfile.mkdtemp(prefix="dot_test_double_")

    try:
        floorplan_ext = Path(floorplan.filename or "floorplan.png").suffix or ".png"
        query1_ext = Path(query1.filename or "query1.jpg").suffix or ".jpg"
        query2_ext = Path(query2.filename or "query2.jpg").suffix or ".jpg"

        floorplan_path = os.path.join(temp_dir, f"floorplan{floorplan_ext}")
        query1_path = os.path.join(temp_dir, f"query1{query1_ext}")
        query2_path = os.path.join(temp_dir, f"query2{query2_ext}")

        with open(floorplan_path, "wb") as f:
            shutil.copyfileobj(floorplan.file, f)

        with open(query1_path, "wb") as f:
            shutil.copyfileobj(query1.file, f)

        with open(query2_path, "wb") as f:
            shutil.copyfileobj(query2.file, f)

        result = localize_dot_from_3_files(
            floorplan_path,
            query1_path,
            query2_path,
        )

        with Image.open(floorplan_path) as img:
            width, height = img.size

        grid_x, grid_y = pixel_to_grid(
            result.dot_x,
            result.dot_y,
            width,
            height,
        )

        actual_pixel_x = None
        actual_pixel_y = None
        error_result = None

        if actual_x is not None and actual_y is not None:
            actual_pixel_x, actual_pixel_y = grid_to_pixel(
                actual_x,
                actual_y,
                width,
                height,
            )
            error_result = calculate_grid_error(
                predicted_x=grid_x,
                predicted_y=grid_y,
                actual_x=actual_x,
                actual_y=actual_y,
            )

        annotated_image_base64 = draw_dots_on_floorplan(
            floorplan_path,
            predicted_x=result.dot_x,
            predicted_y=result.dot_y,
            actual_x=actual_pixel_x,
            actual_y=actual_pixel_y,
        )

        response_data = {
            "dot_x": result.dot_x,
            "dot_y": result.dot_y,
            "grid_x": grid_x,
            "grid_y": grid_y,
            "reasoning": result.reasoning,
            "annotated_image_base64": annotated_image_base64,
            "actual_grid_x": actual_x,
            "actual_grid_y": actual_y,
            "actual_pixel_x": actual_pixel_x,
            "actual_pixel_y": actual_pixel_y,
            "dx": None,
            "dy": None,
            "euclidean_error_m": None,
        }

        if error_result is not None:
            response_data.update(error_result)

        return response_data

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)