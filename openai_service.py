"""
This module defines the OpenAI client and the function for localizing a query image on a 
floorplan using the OpenAI API. The main function, localize_from_images, takes the file paths 
of the floorplan and query images, converts them to data URLs, and sends them to the OpenAI API 
for processing. The response is parsed into a LocalizationResult schema, which includes the 
estimated coordinates and reasoning for the localization.
"""
import base64
import json
import mimetypes
from pathlib import Path

from openai import OpenAI

from schemas import LocalizationResult

from typing import Any

client = OpenAI()

#MODEL_NAME = "gpt-5.4-nano"
MODEL_NAME = "gpt-5.4"
#MODEL_NAME = "gpt-5.4-mini"

MODEL_PRICING_PER_1M = {
    "gpt-5.4": {"input": 2.50, "output": 15.00},
    "gpt-5.4-mini": {"input": 0.750, "output": 4.500},
    "gpt-5.4-nano": {"input": 0.20, "output": 1.25},
}

def _file_to_base64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")

def calculate_request_cost(model: str, usage: Any) -> dict:
    pricing = MODEL_PRICING_PER_1M.get(model)
    if pricing is None:
        return {
            "input_tokens": 0,
            "output_tokens": 0,
            "reasoning_tokens": 0,
            "estimated_cost_usd": None,
        }

    input_tokens = getattr(usage, "input_tokens", 0) or 0
    output_tokens = getattr(usage, "output_tokens", 0) or 0

    reasoning_tokens = 0
    output_details = getattr(usage, "output_tokens_details", None)
    if output_details is not None:
        reasoning_tokens = getattr(output_details, "reasoning_tokens", 0) or 0

    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "reasoning_tokens": reasoning_tokens,
        "estimated_cost_usd": round(input_cost + output_cost, 6),
    }

def localize_from_files(floorplan_pdf_path: str, query_path: str) -> LocalizationResult:
    query_path_obj = Path(query_path)

    query_mime_type, _ = mimetypes.guess_type(query_path_obj.name)
    if query_mime_type is None:
        query_mime_type = "image/jpeg"

    floorplan_b64 = _file_to_base64(floorplan_pdf_path)
    query_b64 = _file_to_base64(query_path)

    response = client.responses.parse(
        model=MODEL_NAME,
        input=[
            {
                "role": "system",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "You are an indoor localization assistant. "
                            "You will receive: "
                            "1) a floorplan PDF and "
                            "2) a query image taken somewhere inside that building. "

                            "The floorplan contains a visible background grid. "
                            "This grid is the coordinate system and must be used exactly as shown. "
                            "Each grid square corresponds to approximately one meter. "

                            "The coordinate origin is the top-left grid cell of the floorplan image. "
                            "The top-left grid cell is (1,1). "
                            "x increases from left to right and y increases from top to bottom. "

                            "IMPORTANT: "
                            "Use the full page grid, not just the building footprint. "
                            "Do NOT create or assume a new grid. "
                            "Do NOT normalize or rescale coordinates. "
                            "Do NOT estimate coordinates relative only to rooms or building geometry. "

                            "Return the top 5 most likely candidate camera locations. "
                            "Each candidate must use integer grid coordinates only. "
                            "Each candidate must include x, y, confidence, and reasoning. "
                            "Confidence must be between 0 and 1. "
                            "Sort candidates from highest confidence to lowest confidence."
                        )
                    }
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "The PDF is the floorplan and includes a visible background grid. "
                            "The image is the query image. "

                            "First identify the most likely location in the floorplan "
                            "(room, corridor, or area). "

                            "Then map that location to the visible page grid and return the grid cell "
                            "that best represents the camera position. "

                            "The coordinate system is one-based, with the top-left grid cell at (1,1). "
                            "x increases to the right and y increases downward. "

                            "Each grid cell corresponds to approximately one meter. "
                            "Different floorplans may have different sizes. "

                            "IMPORTANT: "
                            "Return the grid cell of the camera position, not the center of the room. "

                            "Each candidate must include x, y, confidence, and a short reasoning."
                        )
                    },
                    {
                        "type": "input_file",
                        "filename": "floorplan.pdf",
                        "file_data": f"data:application/pdf;base64,{floorplan_b64}",
                    },
                    {
                        "type": "input_image",
                        "image_url": f"data:{query_mime_type};base64,{query_b64}",
                    },
                ],
            },
        ],
        text_format=LocalizationResult,
    )

    usage_info = calculate_request_cost(MODEL_NAME, response.usage)

    print("\n===== OPENAI REQUEST USAGE =====")
    print("Model:", MODEL_NAME)
    print("Input tokens:", usage_info["input_tokens"])
    print("Output tokens:", usage_info["output_tokens"])
    print("Reasoning tokens:", usage_info["reasoning_tokens"])
    print("Estimated cost (USD):", usage_info["estimated_cost_usd"])
    print("================================\n")

    print("OUTPUT_PARSED:", repr(response.output_parsed))
    print("OUTPUT_TEXT:", repr(response.output_text))

    if response.output_parsed is None:
        raise ValueError(f"Model returned no parsed output. Raw text: {response.output_text!r}")

    return response.output_parsed