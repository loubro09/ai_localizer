"""
This is the main entry point for the FastAPI application.
It defines the API endpoints and handles file uploads for floorplan
localization.
"""
import os
import shutil
import tempfile
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse

load_dotenv()

from openai_service import localize_from_files
from schemas import LocalizationResult
from openai_service_grid_test import extract_grid_dot_coordinates
from schemas_grid_test import GridDotResult

app = FastAPI(title="Floorplan Localizer")


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return """
    <html>
      <body style="font-family: sans-serif; max-width: 1000px; margin: 40px auto;">
        <h1>Floorplan Localizer</h1>

        <form id="localizeForm" enctype="multipart/form-data">
          <div style="margin-bottom: 12px;">
            <label>Floorplan PDF:</label><br>
            <input type="file" id="floorplanInput" name="floorplan" accept="application/pdf" required>
          </div>

          <div style="margin-bottom: 12px;">
            <label>Query image:</label><br>
            <input type="file" id="queryInput" name="query" accept="image/*" required>
          </div>

          <button type="submit">Localize</button>
        </form>

        <hr style="margin: 30px 0;">

        <div style="display: flex; gap: 24px; align-items: flex-start; flex-wrap: wrap;">
          <div style="flex: 1 1 650px; min-width: 300px;">
            <h2>Floorplan Preview</h2>
            <iframe
              id="pdfPreview"
              style="width: 100%; height: 800px; border: 1px solid #ccc;"
            ></iframe>
          </div>

          <div style="flex: 0 0 300px;">
            <h2>Query Preview</h2>
            <img
              id="queryPreview"
              alt="Query image preview"
              style="width: 100%; max-width: 240px; border: 1px solid #ccc; display: none; margin-bottom: 16px;"
            />

            <h2>Result</h2>
            <div
              id="resultBox"
              style="border: 1px solid #ccc; padding: 12px; min-height: 80px; background: #f9f9f9;"
            >No result yet.</div>
          </div>
        </div>

        <script>
          const form = document.getElementById("localizeForm");
          const floorplanInput = document.getElementById("floorplanInput");
          const queryInput = document.getElementById("queryInput");
          const pdfPreview = document.getElementById("pdfPreview");
          const queryPreview = document.getElementById("queryPreview");
          const resultBox = document.getElementById("resultBox");

          floorplanInput.addEventListener("change", function () {
            const file = this.files[0];
            if (!file) {
              pdfPreview.src = "";
              return;
            }
            if (file.type !== "application/pdf") {
              alert("Please upload a PDF file for the floorplan.");
              floorplanInput.value = "";
              pdfPreview.src = "";
              return;
            }
            pdfPreview.src = URL.createObjectURL(file);
          });

          queryInput.addEventListener("change", function () {
            const file = this.files[0];
            if (!file) {
              queryPreview.src = "";
              queryPreview.style.display = "none";
              return;
            }
            if (!file.type.startsWith("image/")) {
              alert("Please upload an image file for the query.");
              queryInput.value = "";
              queryPreview.src = "";
              queryPreview.style.display = "none";
              return;
            }
            queryPreview.src = URL.createObjectURL(file);
            queryPreview.style.display = "block";
          });

          form.addEventListener("submit", async function (event) {
            event.preventDefault();

            const floorplanFile = floorplanInput.files[0];
            const queryFile = queryInput.files[0];

            if (!floorplanFile || !queryFile) {
              resultBox.textContent = "Please select both a floorplan PDF and a query image.";
              return;
            }

            const formData = new FormData();
            formData.append("floorplan", floorplanFile);
            formData.append("query", queryFile);

            resultBox.textContent = "Localizing...";

            try {
              const response = await fetch("/localize", {
                method: "POST",
                body: formData
              });

              const data = await response.json();

              if (!response.ok) {
                resultBox.textContent = "Error: " + (data.detail || "Unknown error");
                return;
              }

              resultBox.innerHTML = `
                <div style="margin-bottom: 10px;"><strong>Top 5 candidate locations</strong></div>
                ${data.candidates.map((candidate, index) => `
                  <div style="border: 1px solid #ddd; background: white; padding: 10px; margin-bottom: 10px;">
                    <div><strong>#${index + 1}</strong></div>
                    <div><strong>X:</strong> ${candidate.x}</div>
                    <div><strong>Y:</strong> ${candidate.y}</div>
                    <div><strong>Confidence:</strong> ${(candidate.confidence * 100).toFixed(1)}%</div>
                    <div><strong>Reasoning:</strong> ${candidate.reasoning}</div>
                  </div>
                `).join("")}
              `;
            } catch (error) {
              resultBox.textContent = "Error: " + error.message;
            }
          });
        </script>
      </body>
    </html>
    """


@app.post("/localize", response_model=LocalizationResult)
async def localize(
    floorplan: UploadFile = File(...),
    query: UploadFile = File(...),
) -> LocalizationResult:
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY is not set.")

    if floorplan.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Floorplan must be a PDF file.")

    if not query.content_type or not query.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Query must be an image file.")

    temp_dir = tempfile.mkdtemp(prefix="floorplan_localizer_")

    try:
        floorplan_path = os.path.join(temp_dir, "floorplan.pdf")
        query_ext = Path(query.filename or "query.jpg").suffix or ".jpg"
        query_path = os.path.join(temp_dir, f"query{query_ext}")

        with open(floorplan_path, "wb") as f:
            shutil.copyfileobj(floorplan.file, f)

        with open(query_path, "wb") as f:
            shutil.copyfileobj(query.file, f)

        result = localize_from_files(floorplan_path, query_path)
        print("RESULT FROM OPENAI SERVICE:", repr(result))
        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@app.post("/test-grid", response_model=GridDotResult)
async def test_grid(
    floorplan: UploadFile = File(...),
) -> GridDotResult:
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY is not set.")

    if floorplan.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Floorplan must be a PDF file.")

    temp_dir = tempfile.mkdtemp(prefix="grid_test_")

    try:
        floorplan_path = os.path.join(temp_dir, "floorplan_with_dots.pdf")

        with open(floorplan_path, "wb") as f:
            shutil.copyfileobj(floorplan.file, f)

        result = extract_grid_dot_coordinates(floorplan_path)
        print("GRID TEST RESULT:", result.model_dump())
        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)