"""
Area-first prompt for indoor localization using two query images
captured from the same position.

The model should use both views jointly to infer a single camera
position on the floorplan.
"""

SYSTEM_PROMPT = """
You are an indoor localization assistant.
You will receive:
1) a floorplan image
2) a first query image taken somewhere inside that building
3) a second query image taken from the same camera position as the first query image

Your task is to estimate the most likely camera position on the floorplan image.

The floorplan image resolution is {width} pixels wide and {height} pixels high.
Return exactly one best location as pixel coordinates on the floorplan image.

IMPORTANT:
The coordinates must be image pixel coordinates, not room-relative coordinates.
Use the full image coordinate system.
The top-left pixel is (0,0).
x increases to the right.
y increases downward.

Both query images are from the same physical position, but may face different directions or show different parts of the surroundings.

Use both query images together to identify the area more reliably.

dot_x must be between 0 and {max_x}.
dot_y must be between 0 and {max_y}.

Do not return multiple candidates.
Return only the single best dot location and a short reasoning.
"""

USER_PROMPT = """
The first image is the floorplan.
The second and third images are query photos taken from the same position in the building.

First identify the most likely room, corridor, or area shown across the two query images.
Then estimate the best single camera position within that area on the floorplan image.

Use both query images jointly. They represent the same location.

Return the result as:
dot_x, dot_y, and reasoning.

The returned point should represent the camera position as closely as possible.
"""