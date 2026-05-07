"""Fix the 3 validator complaints in hf_dataset/croissant.json:
  1. Add sha256 to each FileObject (5 of them).
  2. Replace `cr:Json` with `sc:Text` for the answer fields (cr:Json is not
     a recognized Croissant data type).
  3. Add a `citeAs` block (warning, not error, but worth fixing).

The script downloads the 5 test.jsonl files from HF, computes their SHA256,
patches a local croissant.json copy, and writes it to hf_dataset/croissant.json.
The user then pushes it back to HF.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO_ID = "SimVer-ano/simverse2026"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT = PROJECT_ROOT / "hf_dataset"

CONFIGS = ["voi", "cube1", "cube2", "lamp", "cutrope"]


def main() -> None:
    from huggingface_hub import hf_hub_download

    OUT.mkdir(exist_ok=True)

    # 1) Pull the current croissant.json from HF
    print(f"Downloading croissant.json from {REPO_ID}...")
    croissant_path = Path(hf_hub_download(
        repo_id=REPO_ID,
        filename="croissant.json",
        repo_type="dataset",
    ))
    croissant = json.loads(croissant_path.read_text(encoding="utf-8"))

    # 2) Download each test.jsonl, compute sha256
    hashes: dict[str, dict[str, int | str]] = {}
    for cfg in CONFIGS:
        rel = f"{cfg}/test.jsonl"
        print(f"Hashing {rel}...")
        local = Path(hf_hub_download(
            repo_id=REPO_ID,
            filename=rel,
            repo_type="dataset",
        ))
        digest = hashlib.sha256(local.read_bytes()).hexdigest()
        size = local.stat().st_size
        hashes[cfg] = {"sha256": digest, "contentSize": f"{size} B"}
        print(f"  sha256: {digest}")
        print(f"  size:   {size:,} bytes")

    # 3) Patch FileObject entries — add sha256 + contentSize
    fixed = 0
    for entry in croissant.get("distribution", []):
        if entry.get("@type") != "cr:FileObject":
            continue
        name = str(entry.get("name", ""))
        for cfg in CONFIGS:
            if name == f"{cfg}/test.jsonl":
                entry["sha256"] = hashes[cfg]["sha256"]
                entry["contentSize"] = hashes[cfg]["contentSize"]
                fixed += 1
                break
    print(f"\nPatched sha256+contentSize on {fixed} FileObjects.")

    # 4) Replace cr:Json with sc:Text on answer fields
    json_field_count = 0
    for record_set in croissant.get("recordSet", []):
        for field in record_set.get("field", []):
            if field.get("dataType") == "cr:Json":
                field["dataType"] = "sc:Text"
                # Make the description note that this string is JSON
                desc = str(field.get("description", ""))
                if "JSON" not in desc.upper():
                    field["description"] = desc + " (Stored as a JSON-encoded string.)"
                json_field_count += 1
    print(f"Patched {json_field_count} 'cr:Json' fields -> 'sc:Text'.")

    # 5) Add citeAs (the warning suggested it)
    if "citeAs" not in croissant:
        croissant["citeAs"] = (
            "@dataset{simverse_anonymous_2026,\n"
            "  title  = {SimVerse: A Multi-Task Benchmark for Multimodal Reasoning on "
            "Interactive Simulation Puzzles},\n"
            "  author = {Anonymous Authors (under double-blind review)},\n"
            "  year   = {2026},\n"
            "  url    = {https://huggingface.co/datasets/SimVer-ano/simverse2026}\n"
            "}"
        )
        print("Added citeAs.")

    # 6) Write to hf_dataset/croissant.json
    out_path = OUT / "croissant.json"
    out_path.write_text(
        json.dumps(croissant, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"\nWrote: {out_path}")
    print("\nNext step: push this file to HF:")
    print("  hf upload SimVer-ano/simverse2026 hf_dataset/croissant.json croissant.json --repo-type dataset")


if __name__ == "__main__":
    main()
