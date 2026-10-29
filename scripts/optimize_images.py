"""Build responsive WebP derivatives from the retained WebP master assets."""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ASSETS = ROOT / "frontend" / "assets"
def webp_variants(source: Path, widths: tuple[int, ...], quality: int = 84) -> list[dict[str, int | str]]:
    results: list[dict[str, int | str]] = []
    with Image.open(source) as original:
        has_alpha = "A" in original.getbands()
        image = original.convert("RGBA" if has_alpha else "RGB")
        for width in widths:
            if width > image.width:
                continue
            height = round(image.height * width / image.width)
            resized = image if width == image.width else image.resize((width, height), Image.Resampling.LANCZOS)
            base_name = source.stem.rsplit("-", 1)[0]
            output = source.with_name(f"{base_name}-{width}.webp")
            resized.save(
                output,
                "WEBP",
                quality=quality,
                method=6,
                exact=has_alpha,
                icc_profile=original.info.get("icc_profile"),
                exif=original.info.get("exif", b""),
            )
            results.append({"path": str(output.relative_to(ROOT)), "width": width, "height": height, "bytes": output.stat().st_size})
    return results


def main() -> None:
    report: dict[str, object] = {"quality": 84, "assets": []}
    masters = sorted(FRONTEND_ASSETS.glob("*-1280.webp")) + sorted(FRONTEND_ASSETS.glob("*-1024.webp"))
    for source in masters:
        widths = (640, 960) if source.stem.endswith("-1280") else (480, 800)
        variants = webp_variants(source, widths)
        report["assets"].append({
            "master": str(source.relative_to(ROOT)),
            "master_bytes": source.stat().st_size,
            "variants": variants,
        })

    output = ROOT / "docs" / "image-optimization-report.json"
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Generated responsive variants for {len(masters)} WebP masters.")


if __name__ == "__main__":
    main()
