from typing import List
from pydantic import BaseModel, Field


class DotCoordinate(BaseModel):
    dot_number: int = Field(..., ge=1, le=6, description="The number written next to the green dot")
    x: int = Field(..., ge=1, description="X coordinate on the visible floorplan grid")
    y: int = Field(..., ge=1, description="Y coordinate on the visible floorplan grid")
    confidence: float = Field(..., ge=0.0, le=1.0)
    reasoning: str = Field(..., description="Short explanation of how the coordinate was determined")


class GridDotResult(BaseModel):
    dots: List[DotCoordinate] = Field(
        ...,
        min_length=6,
        max_length=6,
        description="Coordinates for the 6 numbered green dots"
    )