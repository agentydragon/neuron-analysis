"""Launch prompt for the identity task; kept free of Inspect imports so tests can read it."""

PROMPT = (
    "Read annotate.md and format.md. Process all frames from IMG_6128.AVI. The red outline in "
    "photo_2026-10-19_14-30-28.jpg marks the region whose neurons to annotate. "
    "Save the annotations to output/annotations.json."
)
