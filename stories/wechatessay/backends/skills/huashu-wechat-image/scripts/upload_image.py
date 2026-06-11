#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "requests>=2.0.0",
# ]
# ///

"""
Upload local images to image hosting (ImgBB) and return permanent URLs.

Usage:
    uv run upload_image.py image.png
    uv run upload_image.py image.png --api-key "your_key"
    uv run upload_image.py              # 不传则自动扫描 workspaces 下所有图片
    uv run upload_image.py --latest     # 只上传 workspaces 下最新的一张图

Environment:
    IMGBB_API_KEY - ImgBB API key (get from https://api.imgbb.com/)
"""

import argparse
import base64
import json
import os
import sys
from pathlib import Path

import requests

# Fix import: add project root to sys.path
_project_root = Path(__file__).resolve().parent.parent.parent.parent.parent  # goes up to /
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import importlib
config_mod = importlib.import_module("config")
IMAGE_KEY = config_mod.IMAGE_KEY

IMGBB_UPLOAD_URL = "https://api.imgbb.com/1/upload"
DEFAULT_EXPIRATION = 0  # 0 = never expire


def get_api_key() -> str | None:
    return IMAGE_KEY.get("IMGBB_API_KEY")


def upload_to_imgbb(image_path: Path, api_key: str, expiration: int = 0) -> dict:
    """
    Upload a single image to ImgBB.

    Args:
        image_path: Path to local image file
        api_key: ImgBB API key
        expiration: Seconds until image deletion (0 = never)

    Returns:
        Dictionary with keys:
            name (str): original file name
            url  (str): permanent image URL
    """
    if not image_path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    if image_path.is_dir():
        raise IsADirectoryError(f"Path is a directory, not a file: {image_path}")

    # Read and encode image to base64
    with open(image_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode("utf-8")

    payload = {
        "key": api_key,
        "image": image_data,
        "expiration": expiration,
        "name": image_path.stem,
    }
    print(f"Uploading {image_path.name} ({image_path.stat().st_size / 1024:.1f} KB) ...")

    try:
        resp = requests.post(IMGBB_UPLOAD_URL, data=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()

        if not data.get("success"):
            error_msg = data.get("error", {}).get("message", "Unknown error")
            raise RuntimeError(f"ImgBB upload failed: {error_msg}")

        result = data["data"]
        url = result["url"]
        display_url = result.get("display_url", url)
        delete_url = result.get("delete_url", "N/A")

        print(f"  ✅ Upload successful")
        print(f"  📎 URL: {url}")
        print(f"  🖼️  Display: {display_url}")
        print(f"  🗑️  Delete: {delete_url}")

        return {"name": image_path.name, "url": url}

    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Network error during upload: {e}")


def main() -> dict:
    # ========== 改动 1：修正 workspaces 路径 ==========
    SCRIPT_DIR = Path(__file__).resolve().parent  # .../scripts
    # scripts → huashu-wechat-image → skills → backends → wechatessay → workspaces
    WORKSPACES_DIR = SCRIPT_DIR.parents[2] / "workspaces"  # 去掉 / "backends"
    # ========== 改动结束 ==========

    parser = argparse.ArgumentParser(
        description="Upload images to ImgBB and get permanent URLs"
    )
    # # ========== 改动 2：添加位置参数接收图片路径 ==========
    # parser.add_argument(
    #     "images",
    #     nargs="*",
    #     help="Image file path(s) to upload. If omitted, scans workspaces directory."
    # )
    # parser.add_argument(
    #     "--latest", "-l",
    #     action="store_true",
    #     help="Upload only the most recently modified image in workspaces (when no images specified)"
    # )
    # ========== 改动结束 ==========
    parser.add_argument(
        "--api-key", "-k",
        help="ImgBB API key (overrides IMGBB_API_KEY env var)"
    )
    parser.add_argument(
        "--expiration", "-e",
        type=int,
        default=0,
        help="Image expiration in seconds (0 = never expire, default)"
    )

    args = parser.parse_args()

    api_key = get_api_key()
    if not api_key:
        print("Error: No ImgBB API key provided.", file=sys.stderr)
        print("Please either:", file=sys.stderr)
        print("  1. Provide --api-key argument", file=sys.stderr)
        print("  2. Set IMGBB_API_KEY environment variable", file=sys.stderr)
        print("  Get free key at: https://api.imgbb.com/", file=sys.stderr)
        sys.exit(1)

    # ========== 改动 3：解析要上传的文件列表（文件，不是目录） ==========
    image_paths: list[Path] = []

    extensions = ("*.png", "*.jpg", "*.jpeg", "*.gif", "*.webp", "*.bmp")
    candidates = []
    for ext in extensions:
        candidates.extend(WORKSPACES_DIR.glob(ext))

    if not candidates:
        print(f"Error: No images found in {WORKSPACES_DIR}", file=sys.stderr)
        sys.exit(1)

        # 全部上传
    image_paths = candidates
    print(f"Found {len(candidates)} image(s) in workspaces, uploading all...")
    # ========== 改动结束 ==========

    # Upload all images and collect results as {name: url}
    results = {}
    for image_path in image_paths:
        try:
            info = upload_to_imgbb(image_path, api_key, args.expiration)
            results[info["name"]] = info["url"]
        except Exception as e:
            print(f"  ❌ Failed: {e}", file=sys.stderr)
            # Mark failure with None (or skip entirely)
            results[image_path.name] = None

    # Output final dictionary as JSON (for programmatic use)
    print("\n📋 Upload results (JSON):")
    print(json.dumps(results, ensure_ascii=False, indent=2))

    # Non-zero exit if any upload failed
    if any(v is None for v in results.values()):
        sys.exit(1)

    return results


if __name__ == "__main__":
    main()
