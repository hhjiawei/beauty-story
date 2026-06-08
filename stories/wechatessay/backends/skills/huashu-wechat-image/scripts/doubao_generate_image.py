#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "openai>=1.0.0",
#     "pillow>=10.0.0",
#     "requests>=2.0.0",
# ]
# ///

"""
Generate images for WeChat Official Account (公众号) articles using Doubao Seedream 5.0.

Supports multiple aspect ratios:
  --aspect cover    → 2.35:1 (3136x1344@2K / 4704x2016@3K, 头条封面)
  --aspect wide     → 16:9 (2848x1600@2K / 4096x2304@3K, 正文宽图)
  --aspect standard → 4:3 (2304x1728@2K / 3456x2592@3K, 正文方图)
  --aspect square   → 1:1 (2048x2048@2K / 3072x3072@3K, 方图)

Seedream 5.0 supports 2K and 3K only. For 4K, use Seedream 4.5.

Usage:
    uv run generate_image.py --prompt "description" --filename "output.png" [--aspect cover|wide|standard|square] [--size 2K|3K]
    uv run generate_image.py --prompt "edit instructions" --filename "output.png" --input-image "input.png"
"""

import argparse
import base64
import io
import os
import sys
from pathlib import Path

import requests
from openai import OpenAI
from PIL import Image

import config.config
from wechatessay.config import IMAGE_KEY

# Aspect ratio presets for WeChat, mapped to Doubao Seedream recommended pixel values
# Source: https://www.volcengine.com/docs/82379/1541523
ASPECT_PRESETS = {
    "cover": {
        "ratio": "2.35:1",
        "pixels_2k": "3136x1344",  # 21:9 ≈ 2.33:1, closest to 2.35:1
        "pixels_3k": "4704x2016",  # 21:9 3K
        "desc": "头条封面 ultra-wide landscape",
    },
    "wide": {
        "ratio": "16:9",
        "pixels_2k": "2848x1600",
        "pixels_3k": "4096x2304",
        "desc": "正文宽图 landscape",
    },
    "standard": {
        "ratio": "4:3",
        "pixels_2k": "2304x1728",
        "pixels_3k": "3456x2592",
        "desc": "正文方图 landscape",
    },
    "square": {
        "ratio": "1:1",
        "pixels_2k": "2048x2048",
        "pixels_3k": "3072x3072",
        "desc": "方图",
    },
}


def get_api_key():
    """Get API key from argument first, then environment."""
    return IMAGE_KEY.get("OPENAI_API_KEY")


def _image_to_base64(image_path: Path) -> str:
    """Convert local image to base64 data URI."""
    with open(image_path, "rb") as f:
        data = f.read()
    ext = image_path.suffix.lower().replace(".", "")
    if ext in ("jpg", "jpeg"):
        mime = "image/jpeg"
    elif ext == "png":
        mime = "image/png"
    elif ext == "webp":
        mime = "image/webp"
    else:
        mime = "image/jpeg"
    b64 = base64.b64encode(data).decode("utf-8")
    return f"data:{mime};base64,{b64}"


def download_image(url: str, output_path: Path) -> Path:
    """Download image from URL and save to local path."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.0"
    }
    resp = requests.get(url, headers=headers, timeout=120)
    resp.raise_for_status()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(resp.content)
    return output_path


def main():

    SCRIPT_DIR = Path(__file__).resolve().parent  # .../scripts
    WORKSPACES_DIR = SCRIPT_DIR.parents[3] / "backends" / "workspaces"  #

    parser = argparse.ArgumentParser(
        description="Generate images for WeChat (公众号) using Doubao Seedream 5.0"
    )
    parser.add_argument(
        "--prompt", "-p",
        # required=True,
        default="画一只猫",
        help="Image description/prompt (Chinese supported and recommended for Doubao)"
    )
    parser.add_argument(
        "--filename", "-f",
        # required=True,
        default="cat.png",
        help="Output filename (e.g., wechat-cover.png)"
    )
    parser.add_argument(
        "--input-image", "-i",
        help="Optional input image path for image-to-image editing"
    )
    parser.add_argument(
        "--aspect", "-a",
        choices=["cover", "wide", "standard", "square"],
        default="wide",
        help="Aspect ratio preset: cover (2.35:1), wide (16:9, default), standard (4:3), square (1:1)"
    )
    parser.add_argument(
        "--size", "-s",
        choices=["2K", "3K"],
        default="2K",
        help="Output resolution: 2K (default) or 3K. Seedream 5.0 does not support 4K or 1K."
    )
    parser.add_argument(
        "--api-key", "-k",
        help="Ark API key (overrides ARK_API_KEY env var)"
    )
    parser.add_argument(
        "--watermark", "-w",
        action="store_true",
        default=False,
        help="Add watermark to generated image (default: False)"
    )
    parser.add_argument(
        "--response-format",
        choices=["url", "b64_json"],
        default="url",
        help="Response format: url (default) or b64_json"
    )

    args = parser.parse_args()

    # Get API key
    api_key = get_api_key()
    if not api_key:
        print("Error: No API key provided.", file=sys.stderr)
        print("Please either:", file=sys.stderr)
        print("  1. Provide --api-key argument", file=sys.stderr)
        print("  2. Set ARK_API_KEY environment variable", file=sys.stderr)
        sys.exit(1)

    # Initialize OpenAI-compatible client for Doubao Ark
    client = OpenAI(
        base_url="https://ark.cn-beijing.volces.com/api/v3",
        api_key=api_key,
    )

    # ========== 改动开始：输出路径解析 ==========
    filename_path = Path(args.filename)
    if len(filename_path.parts) == 1:
        # 用户只给了纯文件名（如 cat.png），自动落到 workspaces
        output_path = WORKSPACES_DIR / filename_path.name
    else:
        # 用户指定了路径（如 ./tmp/cover.png），尊重原路径
        output_path = filename_path
    # ========== 改动结束 ==========

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Get aspect ratio info and resolve pixel size
    aspect = ASPECT_PRESETS[args.aspect]
    pixel_size = aspect[f"pixels_{args.size.lower()}"]

    # Build extra_body for Doubao-specific parameters
    extra_body: dict = {}
    if args.watermark:
        extra_body["watermark"] = True

    # Handle input image for image-to-image
    if args.input_image:
        input_path = Path(args.input_image)
        if not input_path.exists():
            print(f"Error: Input image not found: {args.input_image}", file=sys.stderr)
            sys.exit(1)
        extra_body["image"] = _image_to_base64(input_path)
        print(f"Loaded input image: {args.input_image}")

    print(f"Generating WeChat image ({aspect['desc']}, {aspect['ratio']}) with size {args.size} ({pixel_size})...")

    try:
        response = client.images.generate(
            model="doubao-seedream-5-0-260128",
            prompt=args.prompt,
            size=pixel_size,
            response_format=args.response_format,
            extra_body=extra_body,
        )

        image_saved = False
        for idx, img_data in enumerate(response.data):
            if args.response_format == "url":
                url = img_data.url
                if not url:
                    continue
                # Save first image to primary output path, subsequent images get suffix
                if idx == 0:
                    target_path = output_path
                else:
                    stem = output_path.stem
                    suffix = output_path.suffix
                    target_path = output_path.with_name(f"{stem}_{idx + 1}{suffix}")

                download_image(url, target_path)
            else:
                # b64_json format
                b64_data = img_data.b64_json
                if not b64_data:
                    continue
                img_bytes = base64.b64decode(b64_data)
                img = Image.open(io.BytesIO(img_bytes))

                if idx == 0:
                    target_path = output_path
                else:
                    stem = output_path.stem
                    suffix = output_path.suffix
                    target_path = output_path.with_name(f"{stem}_{idx + 1}{suffix}")

                # Ensure RGB mode for PNG
                if img.mode in ("RGBA", "P"):
                    rgb_img = Image.new("RGB", img.size, (255, 255, 255))
                    rgb_img.paste(img, mask=img.split()[3] if img.mode == "RGBA" else None)
                    rgb_img.save(str(target_path), "PNG")
                elif img.mode == "RGB":
                    img.save(str(target_path), "PNG")
                else:
                    img.convert("RGB").save(str(target_path), "PNG")

            # Verify saved image
            saved_img = Image.open(str(target_path))
            w, h = saved_img.size
            actual_ratio = w / h

            ratio_parts = aspect["ratio"].split(":")
            expected_ratio = float(ratio_parts[0]) / float(ratio_parts[1])

            print(f"\nImage saved: {target_path.resolve()}")
            print(f"Dimensions: {w}x{h} (ratio: {actual_ratio:.2f}, expected {aspect['ratio']} = {expected_ratio:.2f})")

            if abs(actual_ratio - expected_ratio) > 0.15:
                print(
                    f"⚠️  Warning: Image ratio {actual_ratio:.2f} differs from expected {aspect['ratio']} ({expected_ratio:.2f}).")

            if args.aspect == "cover":
                print(
                    f"📌 Cover safe zone reminder: Core content must be within the center {h}x{h} square area for WeChat Moments cropping.")

            image_saved = True

        if not image_saved:
            print("Error: No image was generated in the response.", file=sys.stderr)
            sys.exit(1)

    except Exception as e:
        print(f"Error generating image: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()