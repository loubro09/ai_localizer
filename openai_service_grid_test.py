import base64
from openai import OpenAI

from schemas_grid_test import GridDotResult

client = OpenAI()

MODEL_NAME = "gpt-5.4"


def _file_to_base64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def extract_grid_dot_coordinates(floorplan_pdf_path: str) -> GridDotResult:
    floorplan_b64 = _file_to_base64(floorplan_pdf_path)

    response = client.responses.parse(
        model=MODEL_NAME,
        input=[
            {
                "role": "system",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "You are reading a floorplan that contains a visible page grid. "
                            "The top-left grid cell is (1,1). "
                            "x increases left to right. "
                            "y increases top to bottom. "
                            "You will receive one floorplan PDF with exactly 6 green numbered dots. "
                            "Your task is only to identify the grid cell containing each numbered dot. "
                            "Return one result for each dot number 1 through 6. "
                            "Use the full visible page grid exactly as shown. "
                            "Do not normalize or rescale the coordinates. "
                            "Return integer grid coordinates only."
                        ),
                    }
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "Read the floorplan PDF and return the x and y grid coordinates "
                            "for each of the 6 numbered green dots. "
                            "Each dot should be mapped to the grid cell it occupies. "
                            "If a dot is close to a grid line, choose the cell that contains most of the dot."
                        ),
                    },
                    {
                        "type": "input_file",
                        "filename": "floorplan_with_dots.pdf",
                        "file_data": f"data:application/pdf;base64,{floorplan_b64}",
                    },
                ],
            },
        ],
        text_format=GridDotResult,
    )

    if response.output_parsed is None:
        raise ValueError(f"Model returned no parsed output. Raw text: {response.output_text!r}")

    return response.output_parsed