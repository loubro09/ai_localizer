""""
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

load_dotenv()  # Load environment variables from .env file

from openai_service import localize_from_images
from schemas import LocalizationResult

app = FastAPI(title="Floorplan Localizer")

""""
GET / endpoint that serves a simple HTML form for uploading a floorplan and query image.
"""
@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return """
    <html>
      <body style="font-family: sans-serif; max-width: 700px; margin: 40px auto;">
        <h1>Floorplan Localizer</h1>
        <form action="/localize" method="post" enctype="multipart/form-data">
          <div style="margin-bottom: 12px;">
            <label>Floorplan image:</label><br>
            <input type="file" name="floorplan" accept="image/*" required>
          </div>
          <div style="margin-bottom: 12px;">
            <label>Query image:</label><br>
            <input type="file" name="query" accept="image/*" required>
          </div>
          <button type="submit">Localize</button>
        </form>
      </body>
    </html>
    """

""""
POST /localize endpoint that accepts two image files: a floorplan and a query image. It saves the uploaded files to a temporary directory, calls the localization 
function, and returns the result. 
"""
@app.post("/localize", response_model=LocalizationResult)
async def localize(
    floorplan: UploadFile = File(...),
    query: UploadFile = File(...),
) -> LocalizationResult:
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY is not set.")

    temp_dir = tempfile.mkdtemp(prefix="floorplan_localizer_")

    try:
        floorplan_ext = Path(floorplan.filename or "floorplan.png").suffix or ".png"
        query_ext = Path(query.filename or "query.jpg").suffix or ".jpg"

        floorplan_path = os.path.join(temp_dir, f"floorplan{floorplan_ext}")
        query_path = os.path.join(temp_dir, f"query{query_ext}")

        with open(floorplan_path, "wb") as f:
            shutil.copyfileobj(floorplan.file, f)

        with open(query_path, "wb") as f:
            shutil.copyfileobj(query.file, f)

        result = localize_from_images(floorplan_path, query_path)
        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)