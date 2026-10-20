"""Launch prompt for the identity task; kept free of Inspect imports so tests can read it."""


def prompt(video: str) -> str:
    return (
        f"Read annotate.md and target.md. Process all frames from {video}. The red outline in "
        "target.jpg marks the region whose dark cells to annotate. "
        "Save the annotations to output/annotations.json."
    )


PROMPT = prompt("IMG_6128.AVI")
