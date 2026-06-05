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
    python3 upload_image.py "/path/to/image.png"
    python3 upload_image.py "/path/to/image.png" --api-key "your_key"
    python3 upload_image.py "/path/a.png" "/path/b.png"  # 批量上传

Environment:
    IMGBB_API_KEY - ImgBB API key (get from https://api.imgbb.com/)
"""

import argparse
import base64
import os
import sys
from pathlib import Path

import requests

IMGBB_UPLOAD_URL = "https://api.imgbb.com/1/upload"
DEFAULT_EXPIRATION = 0  # 0 = never expire


def get_api_key(provided: str | None) -> str | None:
    """Get API key from arg first, then env var."""
    if provided:
        return provided
    return os.environ.get("IMGBB_API_KEY")


def upload_to_imgbb(image_path: Path, api_key: str, expiration: int = 0) -> str:
    """
    Upload a single image to ImgBB.

    Args:
        image_path: Path to local image file
        api_key: ImgBB API key
        expiration: Seconds until image deletion (0 = never)

    Returns:
        Permanent URL of the uploaded image
    """
    if not image_path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    # Read and encode image to base64
    with open(image_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode("utf-8")

    payload = {
        "key": api_key,
        "image": image_data,
        "expiration": expiration,
        "name": image_path.stem,  # 保留原文件名作为图片名
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

        return url

    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Network error during upload: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Upload images to ImgBB and get permanent URLs"
    )
    parser.add_argument(
        "paths",
        nargs="+",
        help="One or more image file paths to upload"
    )
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

    api_key = get_api_key(args.api_key)
    if not api_key:
        print("Error: No ImgBB API key provided.", file=sys.stderr)
        print("Please either:", file=sys.stderr)
        print("  1. Provide --api-key argument", file=sys.stderr)
        print("  2. Set IMGBB_API_KEY environment variable", file=sys.stderr)
        print("  Get free key at: https://api.imgbb.com/", file=sys.stderr)
        sys.exit(1)

    # Upload all images
    urls = []
    for path_str in args.paths:
        image_path = Path(path_str).expanduser().resolve()
        try:
            url = upload_to_imgbb(image_path, api_key, args.expiration)
            urls.append(url)
        except Exception as e:
            print(f"  ❌ Failed: {e}", file=sys.stderr)
            urls.append(None)

    # Final summary
    print(f"\n{'=' * 50}")
    print("UPLOAD SUMMARY")
    print(f"{'=' * 50}")
    for i, (path_str, url) in enumerate(zip(args.paths, urls), 1):
        status = "✅" if url else "❌"
        print(f"{status} [{i}] {Path(path_str).name}")
        if url:
            print(f"    {url}")
    print(f"{'=' * 50}")

    # Return non-zero if any failed
    if any(u is None for u in urls):
        sys.exit(1)


if __name__ == "__main__":
    main()