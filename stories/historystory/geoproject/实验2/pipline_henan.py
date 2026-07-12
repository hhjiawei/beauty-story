#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
河南地区古风 3D 地形瓦片生成器
- 区域：河南及周边（110°E-117°E, 31°N-37°N）
- 层级：z=8,9,10 金字塔
- 风格：古风赭石/土黄/旧纸配色，降低2D阴影干扰
"""

import os
import math
import json
import io
import asyncio
import aiohttp
import numpy as np
from PIL import Image, ImageFilter
from scipy.ndimage import gaussian_filter

# ========================== 配置区 ==========================
# 河南区域：西到三门峡，东到商丘，北到太行山，南到南阳
BOUNDS = (110.0, 37.0, 117.0, 31.0)  # w, n, e, s
ZOOM = 10

RELIEF_OUT_DIR = "../tiles/henan_relief"
DEM_OUT_DIR = "../tiles/henan_dem"
os.makedirs(RELIEF_OUT_DIR, exist_ok=True)
os.makedirs(DEM_OUT_DIR, exist_ok=True)

TERRARIUM_URL = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"

# --- 古风配色：青灰水 → 暖土黄 → 赭石 → 褐 → 灰白 ---
ELEVATION_STOPS = np.array([-200, 0, 50, 200, 600, 1200, 2000, 3000, 4500, 6000])
COLOR_STOPS = np.array([
    [160, 175, 165],  # 低于海平面：青灰水色
    [210, 195, 165],  # 0-50m 平原：暖土黄
    [218, 203, 172],  # 50-200m 台地：浅土黄
    [195, 172, 138],  # 200-600m 丘陵：赭石
    [168, 145, 115],  # 600-1200m 低山：深赭
    [148, 132, 112],  # 1200-2000m 中山：褐色
    [178, 168, 158],  # 2000-3000m 高山：灰褐
    [208, 203, 198],  # 3000-4500m 极高山：浅灰
    [228, 225, 222],  # 4500-6000m 雪线：灰白
    [245, 243, 240]  # 6000m+ 雪峰：白
], dtype=np.float32)

# 光源：更低角度，阴影更长更锐利
AZIMUTH = 315.0
ALTITUDE = 35.0
Z_FACTOR = 2.5

# 海洋与纸张：古地图风格
SEA_COLOR = np.array([165, 180, 170], dtype=np.float32)
PAPER_COLOR = np.array([235, 228, 212], dtype=np.float32)
SEA_MIX = 0.78

# 关键：大幅降低2D阴影权重，避免与MapLibre 3D地形互相干扰
SHADE_WEIGHT = 0.0
SHADE_BASE = 1.0

WEBP_QUALITY = 95


# ========================== 核心函数 ==========================

def lonlat_to_tilexy(lon, lat, zoom):
    x = (lon + 180.0) / 360.0 * (2 ** zoom)
    y = (1.0 - math.log(math.tan(math.radians(lat)) + 1.0 / math.cos(math.radians(lat))) / math.pi) / 2.0 * (2 ** zoom)
    return x, y


def get_tile_range(zoom, bounds):
    w, n, e, s = bounds
    x0 = int(math.floor(lonlat_to_tilexy(w, n, zoom)[0]))
    x1 = int(math.ceil(lonlat_to_tilexy(e, s, zoom)[0]))
    y0 = int(math.floor(lonlat_to_tilexy(w, n, zoom)[1]))
    y1 = int(math.ceil(lonlat_to_tilexy(e, s, zoom)[1]))
    return x0, x1, y0, y1


def decode_terrarium(tile_rgb):
    r = tile_rgb[:, :, 0].astype(np.float32)
    g = tile_rgb[:, :, 1].astype(np.float32)
    b = tile_rgb[:, :, 2].astype(np.float32)
    return r * 256.0 + g + b / 256.0 - 32768.0


def hillshade(elevation, azimuth=315, altitude=48, z_factor=1.0):
    smooth = gaussian_filter(elevation, sigma=1.0)
    gy, gx = np.gradient(smooth)
    slope = np.arctan(z_factor * np.sqrt(gx ** 2 + gy ** 2))
    aspect = np.arctan2(-gy, gx)
    azimuth_rad = np.radians(360.0 - azimuth + 90.0)
    altitude_rad = np.radians(altitude)
    shade = (np.sin(altitude_rad) * np.sin(slope) +
             np.cos(altitude_rad) * np.cos(slope) * np.cos(azimuth_rad - aspect))
    shade = (shade + 1.0) / 2.0
    return np.clip(shade, 0, 1)


def colorize(elevation):
    h, w = elevation.shape
    rgb = np.zeros((h, w, 3), dtype=np.float32)
    for ch in range(3):
        rgb[:, :, ch] = np.interp(elevation, ELEVATION_STOPS, COLOR_STOPS[:, ch])
    return rgb / 255.0


def composite(land_rgb, land_mask):
    sea = (SEA_COLOR * SEA_MIX + PAPER_COLOR * (1 - SEA_MIX)) / 255.0
    mask_3d = land_mask[:, :, None]
    rgb = sea * (1 - mask_3d) + land_rgb * mask_3d
    return np.clip(rgb, 0, 1)


def slice_to_tiles(image_rgb, zoom, x0, x1, y0, y1, out_dir):
    os.makedirs(f"{out_dir}/{zoom}", exist_ok=True)
    h, w = image_rgb.shape[:2]
    tile_size = 256
    count = 0
    for ty in range(y1 - y0):
        for tx in range(x1 - x0):
            x, y = x0 + tx, y0 + ty
            px, py = tx * tile_size, ty * tile_size
            if px + tile_size > w or py + tile_size > h:
                continue
            tile = image_rgb[py:py + tile_size, px:px + tile_size]
            tile_uint8 = (tile * 255).astype(np.uint8)
            img = Image.fromarray(tile_uint8)
            tile_dir = f"{out_dir}/{zoom}/{x}"
            os.makedirs(tile_dir, exist_ok=True)
            img.save(f"{tile_dir}/{y}.webp", "WEBP", quality=WEBP_QUALITY, method=6)
            count += 1
    print(f"✅ z={zoom} 切片完成: {count} 张 → {out_dir}/{zoom}/")
    return count


def generate_lower_zoom_tiles(image_rgb, source_zoom, target_zoom, bounds, out_dir):
    """
    从 source_zoom 大图下采样生成 target_zoom 瓦片
    修复：确保下采样后的图像尺寸精确匹配目标层级的瓦片网格
    """
    zoom_diff = source_zoom - target_zoom

    # 计算目标层级应该有多少个瓦片
    x0, x1, y0, y1 = get_tile_range(target_zoom, bounds)
    target_w = (x1 - x0) * 256
    target_h = (y1 - y0) * 256

    # 下采样到目标层级的精确像素尺寸
    img_pil = Image.fromarray((image_rgb * 255).astype(np.uint8))
    img_down = img_pil.resize((target_w, target_h), Image.LANCZOS)
    downsampled = np.array(img_down, dtype=np.float32) / 255.0

    # 切片
    os.makedirs(f"{out_dir}/{target_zoom}", exist_ok=True)
    tile_size = 256
    count = 0

    for ty in range(y1 - y0):
        for tx in range(x1 - x0):
            px = tx * tile_size
            py = ty * tile_size
            # 现在尺寸精确匹配，不会越界
            tile = downsampled[py:py + tile_size, px:px + tile_size]
            tile_uint8 = (tile * 255).astype(np.uint8)
            img = Image.fromarray(tile_uint8)
            tile_dir = f"{out_dir}/{target_zoom}/{x0 + tx}"
            os.makedirs(tile_dir, exist_ok=True)
            img.save(f"{tile_dir}/{y0 + ty}.webp", "WEBP", quality=WEBP_QUALITY, method=6)
            count += 1

    print(f"✅ z={target_zoom} 下采样切片完成: {count} 张 → {out_dir}/{target_zoom}/")
    return count


# ========================== 异步下载 ==========================

async def fetch_tile_async(session, z, x, y):
    """下载 Terrarium 瓦片：保存原始 DEM PNG，同时解码用于 hillshade"""
    url = TERRARIUM_URL.format(z=z, x=x, y=y)
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            if resp.status == 200:
                data = await resp.read()
                # 保存 DEM
                dem_dir = f"{DEM_OUT_DIR}/{z}/{x}"
                os.makedirs(dem_dir, exist_ok=True)
                with open(f"{dem_dir}/{y}.png", "wb") as f:
                    f.write(data)
                img = Image.open(io.BytesIO(data)).convert('RGB')
                return x, y, np.array(img)
            else:
                print(f"  ⚠️  HTTP {resp.status}: {url}")
                return None
    except Exception as e:
        print(f"  ⚠️  下载失败: {url}, {e}")
        return None


async def fetch_dem_only(session, z, x, y):
    """仅下载 DEM 瓦片（不解码）"""
    url = TERRARIUM_URL.format(z=z, x=x, y=y)
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            if resp.status == 200:
                data = await resp.read()
                dem_dir = f"{DEM_OUT_DIR}/{z}/{x}"
                os.makedirs(dem_dir, exist_ok=True)
                with open(f"{dem_dir}/{y}.png", "wb") as f:
                    f.write(data)
                return True
    except Exception as e:
        print(f"  ⚠️  DEM 下载失败 z={z}/{x}/{y}: {e}")
    return False


async def download_dem_pyramid(session, bounds, zooms=[8, 9]):
    for z in zooms:
        x0, x1, y0, y1 = get_tile_range(z, bounds)
        total = (x1 - x0) * (y1 - y0)
        print(f"\n[DEM z={z}] 瓦片范围: x=[{x0},{x1}], y=[{y0},{y1}], 共 {total} 张")
        tasks = []
        for x in range(x0, x1):
            for y in range(y0, y1):
                tasks.append(fetch_dem_only(session, z, x, y))
        results = await asyncio.gather(*tasks)
        success = sum(1 for r in results if r)
        print(f"  ✅ 成功下载 {success}/{total} 张 DEM 瓦片")


async def build_elevation_matrix_async(zoom, bounds):
    x0, x1, y0, y1 = get_tile_range(zoom, bounds)
    total = (x1 - x0) * (y1 - y0)
    print(f"瓦片范围: x=[{x0},{x1}], y=[{y0},{y1}], 共 {total} 张")

    width = (x1 - x0) * 256
    height = (y1 - y0) * 256
    elevation = np.zeros((height, width), dtype=np.float32)

    tasks = []
    connector = aiohttp.TCPConnector(limit=20)
    async with aiohttp.ClientSession(connector=connector) as session:
        for x in range(x0, x1):
            for y in range(y0, y1):
                tasks.append(fetch_tile_async(session, zoom, x, y))
        results = await asyncio.gather(*tasks)

    success = 0
    for result in results:
        if result is None:
            continue
        x, y, tile_arr = result
        px = (x - x0) * 256
        py = (y - y0) * 256
        elevation[py:py + 256, px:px + 256] = decode_terrarium(tile_arr)
        success += 1

    print(f"  ✅ 成功下载 {success}/{total} 张瓦片")
    return elevation, (x0, x1, y0, y1)


# ========================== 主流程 ==========================

async def main():
    print("=" * 60)
    print("河南古风地形瓦片生成器 (z=8,9,10)")
    print("=" * 60)

    # [0] 下载 DEM 金字塔 z=8,9
    print("\n[0/4] 下载 DEM 高程瓦片金字塔 (z=8,9)...")
    connector = aiohttp.TCPConnector(limit=20)
    async with aiohttp.ClientSession(connector=connector) as session:
        await download_dem_pyramid(session, BOUNDS, zooms=[8, 9])

    # [1] 下载 z=10 DEM + 解码
    print("\n[1/4] 异步下载 Terrarium DEM 瓦片 (z=10)...")
    elevation, (x0, x1, y0, y1) = await build_elevation_matrix_async(ZOOM, BOUNDS)
    print(f"  高程矩阵: {elevation.shape}, 范围: [{elevation.min():.0f}, {elevation.max():.0f}] m")

    # [2] 计算山体阴影（轻量级，避免干扰3D）
    print("\n[2/4] 计算山体阴影...")
    shade = hillshade(elevation, AZIMUTH, ALTITUDE, Z_FACTOR)
    print(f"  阴影范围: [{shade.min():.3f}, {shade.max():.3f}]")

    # [3] 高程着色与合成
    print("\n[3/4] 高程着色与合成...")
    land_color = colorize(elevation)
    land_rgb = land_color * (SHADE_BASE + shade[:, :, None] * SHADE_WEIGHT)
    land_rgb = np.clip(land_rgb, 0, 1)

    # 河南内陆，直接全陆地（无需海陆遮罩）
    final_rgb = land_rgb
    print(f"  最终图像: {final_rgb.shape}")

    # [4] 生成瓦片金字塔
    print("\n[4/4] 生成古风瓦片金字塔...")
    slice_to_tiles(final_rgb, ZOOM, x0, x1, y0, y1, RELIEF_OUT_DIR)
    generate_lower_zoom_tiles(final_rgb, ZOOM, 9, BOUNDS, RELIEF_OUT_DIR)
    generate_lower_zoom_tiles(final_rgb, ZOOM, 8, BOUNDS, RELIEF_OUT_DIR)

    # 生成 style.json
    tile_url = f"http://localhost:8000/{RELIEF_OUT_DIR}/{{z}}/{{x}}/{{y}}.webp"
    w, n, e, s = BOUNDS
    style = {
        "version": 8,
        "sources": {
            "relief": {
                "type": "raster",
                "tiles": [tile_url],
                "tileSize": 256,
                "bounds": [w, s, e, n],
                "attribution": "Terrain Tiles © Mapzen, AWS Open Data"
            }
        },
        "layers": [{"id": "relief-layer", "type": "raster", "source": "relief", "paint": {"raster-opacity": 1.0}}]
    }
    with open("henan_style.json", "w", encoding="utf-8") as f:
        json.dump(style, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 60)
    print("全部完成！")
    for z in [8, 9, 10]:
        z_dir = f"{RELIEF_OUT_DIR}/{z}"
        if os.path.exists(z_dir):
            count = sum(1 for _, _, files in os.walk(z_dir) for f in files if f.endswith('.webp'))
            print(f"  Relief z={z}: {count} 张")
    for z in [8, 9, 10]:
        z_dir = f"{DEM_OUT_DIR}/{z}"
        if os.path.exists(z_dir):
            count = sum(1 for _, _, files in os.walk(z_dir) for f in files if f.endswith('.png'))
            print(f"  DEM z={z}: {count} 张")
    print(f"\n启动服务器: python start_henan.py")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())