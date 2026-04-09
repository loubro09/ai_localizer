"""
This module defines the Pydantic schemas used for validating and structuring the data
returned by the localization function. The main schema is LocalizationResult, which includes the estimated coordinates and reasoning.
"""
from typing import List

from pydantic import BaseModel, Field

"""
Schema for a single location candidate, which includes the x and y coordinates on the floorplan grid, a confidence score, and a short reasoning explanation.
"""
class LocationCandidate(BaseModel):
    x: int = Field(..., ge=1, description="X coordinate on the floorplan grid")
    y: int = Field(..., ge=1, description="Y coordinate on the floorplan grid")
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score between 0 and 1 for this candidate",
    )
    reasoning: str = Field(..., description="Short explanation for this candidate")

"""
Schema for the localization result, which includes a list of the top 5 most likely candidate locations. Each candidate is represented by the LocationCandidate schema defined above.
The candidates are expected to be ordered from most likely to least likely, based on the confidence score provided by the localization function.
"""
class LocalizationResult(BaseModel):
    candidates: List[LocationCandidate] = Field(
        ...,
        min_length=5,
        max_length=5,
        description="Top 5 most likely candidate locations",
    )