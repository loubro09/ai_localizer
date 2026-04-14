import base64
import mimetypes
from pathlib import Path
from typing import Any

from openai import OpenAI
from PIL import Image

from schemas_dot_test import DotLocalizationResult

#from prompts.prompt_area_first import SYSTEM_PROMPT, USER_PROMPT
#rom prompts.prompt_direct_pixel import SYSTEM_PROMPT, USER_PROMPT
from prompts.prompt_semantic_geometric import SYSTEM_PROMPT, USER_PROMPT

client = OpenAI()

MODEL_NAME = "gpt-5.4"
# MODEL_NAME = "gpt-5.4-mini"
# MODEL_NAME = "gpt-5.4-nano"

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


def localize_dot_from_files(floorplan_image_path: str, query_path: str) -> DotLocalizationResult:
    floorplan_path_obj = Path(floorplan_image_path)
    query_path_obj = Path(query_path)

    floorplan_mime_type, _ = mimetypes.guess_type(floorplan_path_obj.name)
    query_mime_type, _ = mimetypes.guess_type(query_path_obj.name)

    if floorplan_mime_type is None:
        floorplan_mime_type = "image/png"
    if query_mime_type is None:
        query_mime_type = "image/jpeg"

    with Image.open(floorplan_image_path) as img:
        width, height = img.size

    floorplan_b64 = _file_to_base64(floorplan_image_path)
    query_b64 = _file_to_base64(query_path)

    response = client.responses.parse(
        model=MODEL_NAME,
        input=[
            {
                "role": "system",
                "content": [
                    {
                        "type": "input_text",
                        "text": SYSTEM_PROMPT.format(
                            width=width,
                            height=height,
                            max_x=width - 1,
                            max_y=height - 1,
                        )
                    }
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": USER_PROMPT
                    },
                    {
                        "type": "input_image",
                        "image_url": f"data:{floorplan_mime_type};base64,{floorplan_b64}",
                    },
                    {
                        "type": "input_image",
                        "image_url": f"data:{query_mime_type};base64,{query_b64}",
                    },
                ],
            },
        ],
        text_format=DotLocalizationResult,
    )

    usage_info = calculate_request_cost(MODEL_NAME, response.usage)

    print("\n===== OPENAI DOT TEST USAGE =====")
    print("Model:", MODEL_NAME)
    print("Input tokens:", usage_info["input_tokens"])
    print("Output tokens:", usage_info["output_tokens"])
    print("Reasoning tokens:", usage_info["reasoning_tokens"])
    print("Estimated cost (USD):", usage_info["estimated_cost_usd"])
    print("=================================\n")

    print("DOT OUTPUT_PARSED:", repr(response.output_parsed))
    print("DOT OUTPUT_TEXT:", repr(response.output_text))

    if response.output_parsed is None:
        raise ValueError(f"Model returned no parsed output. Raw text: {response.output_text!r}")

    return response.output_parsed