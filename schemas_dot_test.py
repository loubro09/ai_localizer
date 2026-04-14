from pydantic import BaseModel, Field


class DotLocalizationResult(BaseModel):
    dot_x: int = Field(..., ge=0, description="Predicted X pixel coordinate on the floorplan image")
    dot_y: int = Field(..., ge=0, description="Predicted Y pixel coordinate on the floorplan image")
    reasoning: str = Field(..., description="Short explanation of why this location was chosen")

class DotTestResponse(BaseModel):
    dot_x: int = Field(..., ge=0)
    dot_y: int = Field(..., ge=0)
    grid_x: int = Field(..., ge=0)
    grid_y: int = Field(..., ge=0)
    reasoning: str
    annotated_image_base64: str