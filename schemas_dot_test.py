from typing import Optional
from pydantic import BaseModel, Field


class DotLocalizationResult(BaseModel):
    dot_x: int = Field(..., ge=0, description="Predicted X pixel coordinate on the floorplan image")
    dot_y: int = Field(..., ge=0, description="Predicted Y pixel coordinate on the floorplan image")
    reasoning: str = Field(..., description="Short explanation of why this location was chosen")


class DotTestResponse(BaseModel):
    dot_x: int
    dot_y: int
    grid_x: int
    grid_y: int
    reasoning: str
    annotated_image_base64: str

    actual_grid_x: Optional[int] = None
    actual_grid_y: Optional[int] = None
    actual_pixel_x: Optional[int] = None
    actual_pixel_y: Optional[int] = None

    dx: Optional[int] = None
    dy: Optional[int] = None
    euclidean_error_m: Optional[float] = None
    manhattan_error_m: Optional[int] = None