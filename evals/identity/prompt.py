"""Launch prompt for the identity task; kept free of Inspect imports so tests can read it."""


def prompt(video: str) -> str:
    return (
        f"Read annotate.md, format.md and target.md. Process all frames from {video}. The red outline in "
        "photo_2026-10-19_14-30-28.jpg marks the region whose dark cells to annotate. "
        "Save the annotations to output/annotations.json."
    )


PROMPT = prompt("IMG_6128.AVI")
