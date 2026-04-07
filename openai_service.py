"""
This module defines the OpenAI client and the function for localizing a query image on a 
floorplan using the OpenAI API. The main function, localize_from_images, takes the file paths 
of the floorplan and query images, converts them to data URLs, and sends them to the OpenAI API 
for processing. The response is parsed into a LocalizationResult schema, which includes the 
estimated coordinates and reasoning for the localization.
"""
import base64
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

"""
Helper function to convert an image file to a data URL. This is necessary because the OpenAI API 
expects images to be sent as URLs, and using data URLs allows us to include the image data 
directly in the request without needing to host the images on an external server.
"""
def _image_to_data_url(path: str) -> str:
    file_path = Path(path)
    mime_type, _ = mimetypes.guess_type(file_path.name)
    if mime_type is None:
        mime_type = "application/octet-stream"

    with open(file_path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")

    return f"data:{mime_type};base64,{encoded}"


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

"""
Main function to localize the query image on the floorplan. It takes the file paths of the floorplan and query images, converts them to data URLs, and sends them to the OpenAI
API for processing. The response is parsed into a LocalizationResult schema, which includes the estimated coordinates and reasoning for the localization.
"""
def localize_from_images(floorplan_path: str, query_path: str) -> LocalizationResult:
    floorplan_data_url = _image_to_data_url(floorplan_path)
    query_data_url = _image_to_data_url(query_path)

    response = client.responses.parse(
        model=MODEL_NAME,
        input=[
            {
                "role": "system",
                "content": (
                    "You are an indoor localization assistant. "
                    "You will receive two images: "
                    "1) a floorplan image and "
                    "2) a query image taken somewhere inside that building. "
                    "The floorplan uses a 50x50 coordinate grid. "
                    "Return the top 5 most likely candidate camera locations. "
                    "Coordinate rules: "
                    "x is horizontal from left to right, integer 0 to 49. "
                    "y is vertical from top to bottom, integer 0 to 49. "
                    "(0,0) is the top-left corner of the floorplan. "
                    "(49,49) is the bottom-right corner. "
                    "Also return a confidence score between 0 and 1 for each candidate. "
                    "Sort candidates from highest confidence to lowest confidence. "
                    "Do not return normalized coordinates. "
                    "Do not return pixel coordinates. "
                    "Use only the 50x50 grid."
                ),
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "The first image is the floorplan. "
                            "The second image is the query image. "
                            "Analyze visible spatial cues such as walls, doors, openings, corridor shape, "
                            "room layout, furniture, floor type, and lighting. "
                            "Match the query image to the floorplan and return the 5 most likely positions on the 50x50 grid. "
                            "Each candidate must include x, y, confidence, and a short reasoning."
                        ),
                    },
                    {
                        "type": "input_image",
                        "image_url": floorplan_data_url,
                    },
                    {
                        "type": "input_image",
                        "image_url": query_data_url,
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

    return response.output_parsed