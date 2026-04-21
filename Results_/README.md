# Floorplan Test Case Viewer

## What it does
- Loads your test cases from a CSV or Excel file.
- If the Excel file has multiple sheets, it automatically combines all sheets into one dataset.
- Uses one built-in map for Floor 3 and one built-in map for Floor 5.
- Lets you move through all test cases with a slider.
- Draws actual and predicted XY positions on the correct floor map automatically.
- Shows the reasoning text for the selected case.

## Expected dataset columns
Each sheet should contain these columns:
- Id
- Floor
- Image id
- Image Type
- True x
- True y
- Predicted x
- Predicted y
- Euclidean error
- Reasoning

## Expected files
Place these files here:
- `data/tests.xlsx` or set `DATA_FILE`
- `static/maps/floor3.png`
- `static/maps/floor5.png`

## Run
```bash
pip install -r requirements.txt
uvicorn app:app --reload
```

Then open:
```text
http://127.0.0.1:8000
```

## Optional environment variables
```bash
export DATA_FILE=/absolute/path/to/your/tests.xlsx
export MAPS_DIR=/absolute/path/to/your/maps
export MAX_GRID_X=54
export MAX_GRID_Y=44
export SHEET_NAMES="Area prompt,Pixel prompt,Semantic prompt,Double prompt,Gray Scale,Low Light"
```

## Limit Excel loading to selected sheets
If your workbook contains extra sheets, set `SHEET_NAMES` as a comma-separated list. Only those sheets will be loaded.

export SHEET_NAMES="Area prompt,Pixel prompt,Semantic prompt,Gray Scale,Low Light"
python -m uvicorn app:app --reload