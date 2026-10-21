"""Optimize complete AIM poker card faces; leave source artwork and PSDs intact."""
import argparse
import json
import re
from pathlib import Path
from PIL import Image

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("source", type=Path, help="AIM 五周年扑克计划 folder")
parser.add_argument("--width", type=int, default=640)
parser.add_argument("--quality", type=int, default=85)
args = parser.parse_args()
if args.width <= 0 or not 1 <= args.quality <= 100:
    parser.error("width must be positive and quality must be between 1 and 100")
target = Path(__file__).resolve().parents[1] / "src/assets/aim-cards"
suits = {"黑桃": "spades", "红桃": "hearts", "梅花": "clubs", "方片": "diamonds"}
suit_order = {suit: index for index, suit in enumerate(suits)}
ranks = {"A": 1, **{str(i): i for i in range(2, 11)}, "J": 11, "Q": 12, "K": 13}
faces = []
for path in args.source.rglob("*.png"):
    match = re.search(r"(黑桃|红桃|梅花|方片)(10|[A2-9JQK])$", path.stem)
    if match:
        suit, rank = match.groups()
        faces.append((suit_order[suit], ranks[rank], suit, rank, path))
if not faces:
    parser.error("No complete card faces found")
identities = [(suit, rank) for _, _, suit, rank, _ in faces]
if len(identities) != len(set(identities)):
    parser.error("Duplicate suit/rank card faces found; resolve duplicates before importing")
target.mkdir(parents=True, exist_ok=True)
records = []
for _, _, suit, rank, path in sorted(faces):
    filename = f"{suits[suit]}-{rank.lower()}.webp"
    with Image.open(path) as original:
        if not 0.62 < original.width / original.height < 0.69:
            raise ValueError(f"Unexpected card face aspect ratio: {path}")
        image = original.convert("RGB")
        image.thumbnail((args.width, round(args.width * 8700 / 5700)), Image.Resampling.LANCZOS)
        image.save(target / filename, "WEBP", quality=args.quality, method=6)
        width, height = image.size
    records.append({"id": filename[:-5], "file": filename, "name": f"{suit} {rank}",
                    "source": path.relative_to(args.source).as_posix(), "width": width, "height": height,
                    "original_bytes": path.stat().st_size, "bytes": (target / filename).stat().st_size})
(target / "manifest.json").write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n")
original_bytes = sum(record["original_bytes"] for record in records)
compressed_bytes = sum(record["bytes"] for record in records)
print(json.dumps({"cards": len(records), "original_bytes": original_bytes,
                  "compressed_bytes": compressed_bytes,
                  "reduction_percent": round((1 - compressed_bytes / original_bytes) * 100, 1),
                  "target": str(target)}, ensure_ascii=False))
