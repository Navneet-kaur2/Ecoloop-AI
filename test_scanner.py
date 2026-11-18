"""Quick verification script for the waste scanner.

Calls analyze_waste_image() on two different uploaded images and prints both
outputs so you can confirm the results actually differ (i.e. the AI is really
analyzing each image, not returning a hardcoded response).

Run:  python test_scanner.py
"""
import sys
from pathlib import Path

from ai_service import analyze_waste_image

# Two visually different images already present in static/uploads/.
IMAGES = [
    "static/uploads/1828844.jpg",
    "static/uploads/images.png",
]


def main():
    # Run from the project root so relative paths resolve regardless of cwd.
    root = Path(__file__).resolve().parent
    outputs = []

    for rel in IMAGES:
        image_path = root / rel
        print("=" * 80)
        print(f"Image: {rel}")
        print("-" * 80)
        if not image_path.exists():
            print(f"!! file not found: {image_path}")
            outputs.append(None)
            continue
        result = analyze_waste_image(str(image_path))
        print(result)
        print()
        outputs.append(result)

    # A simple sanity check that the two responses are not identical.
    print("=" * 80)
    print("Sanity check")
    print("-" * 80)
    if outputs[0] and outputs[1]:
        if outputs[0] == outputs[1]:
            print("WARNING: both outputs are identical — the AI may be returning a hardcoded response.")
            sys.exit(1)
        else:
            print("OK: the two outputs differ, so each image was analyzed separately.")
    else:
        print("NOTE: at least one image could not be analyzed (see error above).")
        sys.exit(1)


if __name__ == "__main__":
    main()
