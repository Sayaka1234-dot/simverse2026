"""Rename HF references in dataset text files from old username to new.

Pulls all text files (README.md, datasheet.md, per-config READMEs, example_load.py,
croissant.json) from the HF repo, replaces the old username with the new one,
and saves them under hf_dataset/ ready for re-upload.

Data files (test.jsonl, images, videos) are NOT touched — they don't reference
the username and don't need re-upload.
"""
from __future__ import annotations

from pathlib import Path

OLD_USER = "SimVer-ano"
NEW_USER = "SimVer-ano"
DATASET_NAME = "simverse2026"

# HF still serves the old URL via redirect, but to be safe we also support
# pulling from the new URL after rename.
SRC_REPO_ID = f"{NEW_USER}/{DATASET_NAME}"  # post-rename canonical
PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT = PROJECT_ROOT / "hf_dataset"

# Text files we want to update. Path on HF (== path under hf_dataset/ locally).
TEXT_FILES = [
    "README.md",
    "datasheet.md",
    "example_load.py",
    "voi/README.md",
    "cube1/README.md",
    "cube2/README.md",
    "lamp/README.md",
    "cutrope/README.md",
]


def main() -> None:
    from huggingface_hub import hf_hub_download

    OUT.mkdir(exist_ok=True)
    print(f"Replacing '{OLD_USER}' -> '{NEW_USER}' in HF repo text files\n")

    # Patch the local croissant.json that already exists (don't re-download — we
    # just patched it with sha256/citeAs/etc and it's the latest).
    croissant_path = OUT / "croissant.json"
    if croissant_path.exists():
        text = croissant_path.read_text(encoding="utf-8")
        new_text = text.replace(OLD_USER, NEW_USER)
        if text != new_text:
            croissant_path.write_text(new_text, encoding="utf-8")
            print(f"Patched local: {croissant_path.relative_to(PROJECT_ROOT)}")
        else:
            print(f"No change needed: {croissant_path.relative_to(PROJECT_ROOT)}")
    else:
        print(f"WARNING: {croissant_path} not present locally, skipping")

    # Download + patch each text file from HF
    for rel in TEXT_FILES:
        print(f"\nFetching {rel}...")
        try:
            local = Path(hf_hub_download(
                repo_id=SRC_REPO_ID,
                filename=rel,
                repo_type="dataset",
            ))
        except Exception as exc:
            print(f"  SKIP: {exc}")
            continue

        text = local.read_text(encoding="utf-8")
        new_text = text.replace(OLD_USER, NEW_USER)
        if text == new_text:
            print(f"  no change needed (no '{OLD_USER}' in file)")
            continue
        out_path = OUT / rel
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(new_text, encoding="utf-8")
        print(f"  wrote {out_path.relative_to(PROJECT_ROOT)} ({text.count(OLD_USER)} replacements)")

    print("\n=== Files prepared for re-upload ===")
    files_to_upload = []
    for rel in ["croissant.json"] + TEXT_FILES:
        p = OUT / rel
        if p.exists():
            files_to_upload.append(rel)
            print(f"  {rel}")
    print(f"\nTotal: {len(files_to_upload)} file(s)")
    print("\n=== Upload commands (new HF user-name) ===\n")
    for rel in files_to_upload:
        local = (OUT / rel).resolve()
        print(
            f'hf upload {NEW_USER}/{DATASET_NAME} "{local}" {rel} '
            f'--repo-type dataset --commit-message "Rename owner refs to {NEW_USER}"'
        )


if __name__ == "__main__":
    main()
