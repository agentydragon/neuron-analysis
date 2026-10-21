"""Launch prompt for the identity task; kept free of Inspect imports so tests can read it."""


def prompt(video: str) -> str:
    return (
        f"Read annotate.md and target.md. Process all frames from {video}. "
        "Save the annotations to output/annotations.json."
    )


PROMPT = prompt("timelapse1.avi")


if __name__ == "__main__":
    import sys

    print(prompt(sys.argv[1]))
