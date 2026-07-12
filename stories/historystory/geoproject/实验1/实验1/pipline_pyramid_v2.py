#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Terrarium DEM → MapLibre Relief Tiles + DEM Pyramid (Python Pipeline)
修改版：同时生成：
  1. 彩色地形瓦片金字塔 (tiles/relief/, z=4,5,6, WebP)
  2. DEM 高程瓦片金字塔 (tiles/dem/, z=4,5,6, PNG) 供 MapLibre 3D Terrain 使用

  彩色地形瓦片（tiles/relief/）：把地形画成彩色的（绿色平原、棕色山地、白色雪山），加上光影效果，看起来像卫星图但比卫星图更清晰地显示了地势。格式是 webp（体积小）。

  纯高程瓦片（tiles/dem/）：保留最原始的“高度数字”（不染色），专门给 MapLibre 地图引擎做 3D 立体地形 用的（让山真的凸起来）。格式是 png（无损）。





















"""

import os
import math
import json
import io
import asyncio
import aiohttp
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
import geopandas as gpd
from shapely.geometry import shape
import rasterio
from rasterio.features import rasterize
from rasterio.transform import from_bounds
from scipy.ndimage import gaussian_filter

# ========================== 配置区 ==========================

BOUNDS = (73.0, 54.0, 136.0, 18.0)
ZOOM = 6
RELIEF_OUT_DIR = "tiles/relief"
DEM_OUT_DIR = "tiles/dem"
os.makedirs(RELIEF_OUT_DIR, exist_ok=True)
os.makedirs(DEM_OUT_DIR, exist_ok=True)

TERRARIUM_URL = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
NE_LAND_PATH = "../../land/ne_10m_land_scale_rank.shp"

ELEVATION_STOPS = np.array([-200, 0, 250, 700, 1200, 2000, 3000, 4200, 5400, 6200])
COLOR_STOPS = np.array([
    [160, 210, 140], [180, 220, 160], [210, 210, 150],
    [220, 200, 130], [200, 180, 120], [190, 170, 140],
    [210, 200, 190], [230, 230, 230], [240, 240, 240], [255, 255, 255]
], dtype=np.float32)

AZIMUTH = 315.0
ALTITUDE = 48.0
Z_FACTOR = 1.0
SEA_COLOR = np.array([210, 220, 230], dtype=np.float32)
PAPER_COLOR = np.array([245, 240, 230], dtype=np.float32)
SEA_MIX = 0.82
SHADE_WEIGHT = 0.38
SHADE_BASE = 0.72
WEBP_QUALITY = 88


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


async def fetch_tile_async(session, z, x, y):
    """下载 Terrarium 瓦片：保存原始 PNG 到 tiles/dem/，同时解码用于 hillshade"""
    url = TERRARIUM_URL.format(z=z, x=x, y=y)
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            if resp.status == 200:
                data = await resp.read()

                # 保存原始 DEM PNG（无损，供 MapLibre 3D Terrain 使用）
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
    """仅下载并保存 DEM 瓦片（不解码），用于 z=4,5 金字塔"""
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


async def download_dem_pyramid(session, bounds, zooms=[4, 5]):
    """下载指定层级的 DEM 瓦片金字塔（仅保存，不用于 hillshade）"""
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


def create_land_mask(bounds, width, height):
    if not os.path.exists(NE_LAND_PATH):
        print(f"⚠️  未找到 {NE_LAND_PATH}，生成全陆地mask")
        return np.ones((height, width), dtype=np.float32)

    gdf = gpd.read_file(NE_LAND_PATH)
    w, n, e, s = bounds
    bbox = gpd.GeoDataFrame(
        geometry=[shape({"type": "Polygon", "coordinates": [[[w, s], [e, s], [e, n], [w, n], [w, s]]]})],
        crs="EPSG:4326"
    )
    gdf_clipped = gpd.overlay(gdf, bbox, how='intersection')

    transform = from_bounds(w, s, e, n, width, height)
    mask = rasterize(
        [(geom, 255) for geom in gdf_clipped.geometry],
        out_shape=(height, width), transform=transform, fill=0, dtype=np.uint8, all_touched=True
    )
    mask_img = Image.fromarray(mask)
    mask_img = mask_img.filter(ImageFilter.GaussianBlur(0.35))
    return np.array(mask_img, dtype=np.float32) / 255.0


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
    从 source_zoom 的大图下采样生成 target_zoom 的瓦片
    source_zoom > target_zoom
    """
    zoom_diff = source_zoom - target_zoom
    scale = 1.0 / (2 ** zoom_diff)

    # 下采样大图
    h, w = image_rgb.shape[:2]
    new_h, new_w = int(h * scale), int(w * scale)
    img_pil = Image.fromarray((image_rgb * 255).astype(np.uint8))
    img_down = img_pil.resize((new_w, new_h), Image.LANCZOS)
    downsampled = np.array(img_down, dtype=np.float32) / 255.0

    # 计算 target_zoom 的瓦片范围
    x0, x1, y0, y1 = get_tile_range(target_zoom, bounds)

    # 切片
    os.makedirs(f"{out_dir}/{target_zoom}", exist_ok=True)
    tile_size = 256
    count = 0

    for ty in range(y1 - y0):
        for tx in range(x1 - x0):
            px = tx * tile_size
            py = ty * tile_size
            if px + tile_size > new_w or py + tile_size > new_h:
                continue
            tile = downsampled[py:py + tile_size, px:px + tile_size]
            tile_uint8 = (tile * 255).astype(np.uint8)
            img = Image.fromarray(tile_uint8)
            tile_dir = f"{out_dir}/{target_zoom}/{x0 + tx}"
            os.makedirs(tile_dir, exist_ok=True)
            img.save(f"{tile_dir}/{y0 + ty}.webp", "WEBP", quality=WEBP_QUALITY, method=6)
            count += 1

    print(f"✅ z={target_zoom} 下采样切片完成: {count} 张 → {out_dir}/{target_zoom}/")
    return count


# ========================== 主流程 ==========================

async def main():
    print("=" * 60)
    print("Terrarium DEM → Relief Tiles + DEM Pyramid (z=4,5,6)")
    print("=" * 60)

    # [0/5] 下载 DEM 金字塔 z=4,5（z=6 会在下一步自动保存）
    print("\n[0/5] 下载 DEM 高程瓦片金字塔 (z=4,5)...")
    connector = aiohttp.TCPConnector(limit=20)
    async with aiohttp.ClientSession(connector=connector) as session:
        await download_dem_pyramid(session, BOUNDS, zooms=[4, 5])

    print("\n[1/5] 异步下载 Terrarium DEM 瓦片 (z=6)...")
    elevation, (x0, x1, y0, y1) = await build_elevation_matrix_async(ZOOM, BOUNDS)
    print(f"  高程矩阵: {elevation.shape}, 范围: [{elevation.min():.0f}, {elevation.max():.0f}] m")

    print("\n[2/5] 计算山体阴影...")
    shade = hillshade(elevation, AZIMUTH, ALTITUDE, Z_FACTOR)
    print(f"  阴影范围: [{shade.min():.3f}, {shade.max():.3f}]")

    print("\n[3/5] 高程着色与合成...")
    land_color = colorize(elevation)
    land_rgb = land_color * (SHADE_BASE + shade[:, :, None] * SHADE_WEIGHT)
    land_rgb = np.clip(land_rgb, 0, 1)
    print(f"  陆地颜色范围: [{land_rgb.min():.3f}, {land_rgb.max():.3f}]")

    print("\n[4/5] 创建陆海遮罩...")
    h, w = elevation.shape
    land_mask = create_land_mask(BOUNDS, w, h)
    print(f"  陆地占比: {np.mean(land_mask):.1%}")

    final_rgb = composite(land_rgb, land_mask)
    print(f"  最终图像: {final_rgb.shape}")

    print("\n[5/5] 生成彩色瓦片金字塔...")

    # z=6 原始切片
    slice_to_tiles(final_rgb, ZOOM, x0, x1, y0, y1, RELIEF_OUT_DIR)

    # z=5 下采样（50%）
    generate_lower_zoom_tiles(final_rgb, ZOOM, 5, BOUNDS, RELIEF_OUT_DIR)

    # z=4 下采样（25%）
    generate_lower_zoom_tiles(final_rgb, ZOOM, 4, BOUNDS, RELIEF_OUT_DIR)

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
    with open("maplibre_style.json", "w", encoding="utf-8") as f:
        json.dump(style, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 60)
    print("全部完成！")
    print("=" * 60)
    print(f"彩色瓦片金字塔 (tiles/relief):")
    for z in [4, 5, 6]:
        z_dir = f"{RELIEF_OUT_DIR}/{z}"
        if os.path.exists(z_dir):
            count = sum(1 for _, _, files in os.walk(z_dir) for f in files if f.endswith('.webp'))
            print(f"  z={z}: {count} 张")
    print(f"\nDEM 瓦片金字塔 (tiles/dem):")
    for z in [4, 5, 6]:
        z_dir = f"{DEM_OUT_DIR}/{z}"
        if os.path.exists(z_dir):
            count = sum(1 for _, _, files in os.walk(z_dir) for f in files if f.endswith('.png'))
            print(f"  z={z}: {count} 张")
    print(f"\n样式文件: maplibre_style.json")
    print(f"\n启动服务器:")
    print(f"  python -m http.server 8000")
    print(f"  3D 地图访问: http://localhost:8000/xia_3d_terrain.html")
    print(f"  2D 地图访问: http://localhost:8000/index.html")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())