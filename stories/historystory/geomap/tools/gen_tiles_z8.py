#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""山河战图 · 河南古风地形瓦片生成器（z6/7/8，含 DEM 金字塔）
基于用户提供的生成器改写：同步 requests 版本，DEM 低层级由 z8 矩阵下采样重编码。
"""
import os, math, io
import numpy as np
import requests
from PIL import Image

BOUNDS = (110.0, 37.0, 117.0, 31.0)  # w, n, e, s
BASE_ZOOM = 8
LOW_ZOOMS = [7, 6]
OUT = "/tmp/shanhe"
RELIEF_DIR = f"{OUT}/tiles/henan_relief"
DEM_DIR = f"{OUT}/tiles/henan_dem"

TERRARIUM_URL = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"

ELEVATION_STOPS = np.array([-200, 0, 50, 200, 600, 1200, 2000, 3000, 4500, 6000])
COLOR_STOPS = np.array([
    [160, 175, 165], [210, 195, 165], [218, 203, 172], [195, 172, 138],
    [168, 145, 115], [148, 132, 112], [178, 168, 158], [208, 203, 198],
    [228, 225, 222], [245, 243, 240]
], dtype=np.float32)
WEBP_QUALITY = 92


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


def decode_terrarium(rgb):
    r = rgb[:, :, 0].astype(np.float32)
    g = rgb[:, :, 1].astype(np.float32)
    b = rgb[:, :, 2].astype(np.float32)
    return r * 256.0 + g + b / 256.0 - 32768.0


def encode_terrarium(elev):
    v = elev + 32768.0
    r = np.floor(v / 256.0)
    rem = v - r * 256.0
    g = np.floor(rem)
    b = np.round((rem - g) * 256.0)
    out = np.stack([r, g, b], axis=-1)
    return np.clip(out, 0, 255).astype(np.uint8)


def colorize(elevation):
    h, w = elevation.shape
    rgb = np.zeros((h, w, 3), dtype=np.float32)
    for ch in range(3):
        rgb[:, :, ch] = np.interp(elevation, ELEVATION_STOPS, COLOR_STOPS[:, ch])
    return rgb / 255.0


def slice_matrix(img_rgb, zoom, x0, x1, y0, y1, out_dir, fmt="WEBP", quality=95):
    tile = 256
    count = 0
    for ty in range(y1 - y0):
        for tx in range(x1 - x0):
            px, py = tx * tile, ty * tile
            t = img_rgb[py:py + tile, px:px + tile]
            if t.shape[0] != tile or t.shape[1] != tile:
                continue
            arr = (t * 255).astype(np.uint8) if t.dtype != np.uint8 else t
            d = f"{out_dir}/{zoom}/{x0 + tx}"
            os.makedirs(d, exist_ok=True)
            im = Image.fromarray(arr)
            if fmt == "WEBP":
                im.save(f"{d}/{y0 + ty}.webp", "WEBP", quality=quality, method=6)
            else:
                im.save(f"{d}/{y0 + ty}.png", "PNG")
            count += 1
    print(f"  z={zoom} -> {out_dir}: {count} tiles ({fmt})")
    return count


def downsample_rgb(img_rgb, target_w, target_h):
    im = Image.fromarray((img_rgb * 255).astype(np.uint8))
    im2 = im.resize((target_w, target_h), Image.LANCZOS)
    return np.array(im2, dtype=np.float32) / 255.0


def downsample_elev(elev, target_w, target_h):
    im = Image.fromarray(elev.astype(np.float32), mode="F")
    im2 = im.resize((target_w, target_h), Image.BILINEAR)
    return np.array(im2, dtype=np.float32)


def main():
    x0, x1, y0, y1 = get_tile_range(BASE_ZOOM, BOUNDS)
    total = (x1 - x0) * (y1 - y0)
    print(f"z{BASE_ZOOM} range x[{x0},{x1}] y[{y0},{y1}] = {total} tiles")
    W, H = (x1 - x0) * 256, (y1 - y0) * 256
    elev = np.zeros((H, W), dtype=np.float32)

    sess = requests.Session()
    ok = 0
    for x in range(x0, x1):
        for y in range(y0, y1):
            url = TERRARIUM_URL.format(z=BASE_ZOOM, x=x, y=y)
            try:
                r = sess.get(url, timeout=30)
                if r.status_code == 200:
                    img = Image.open(io.BytesIO(r.content)).convert("RGB")
                    arr = np.array(img)
                    elev[(y - y0) * 256:(y - y0 + 1) * 256, (x - x0) * 256:(x - x0 + 1) * 256] = decode_terrarium(arr)
                    d = f"{DEM_DIR}/{BASE_ZOOM}/{x}"
                    os.makedirs(d, exist_ok=True)
                    with open(f"{d}/{y}.png", "wb") as f:
                        f.write(r.content)
                    ok += 1
                else:
                    print(f"  HTTP {r.status_code} {url}")
            except Exception as e:
                print(f"  fail {url}: {e}")
    print(f"downloaded {ok}/{total}; elev range [{elev.min():.0f},{elev.max():.0f}] m")

    relief = colorize(elev)
    slice_matrix(relief, BASE_ZOOM, x0, x1, y0, y1, RELIEF_DIR, "WEBP", WEBP_QUALITY)

    for z in LOW_ZOOMS:
        zx0, zx1, zy0, zy1 = get_tile_range(z, BOUNDS)
        tw, th = (zx1 - zx0) * 256, (zy1 - zy0) * 256
        relief_z = downsample_rgb(relief, tw, th)
        slice_matrix(relief_z, z, zx0, zx1, zy0, zy1, RELIEF_DIR, "WEBP", WEBP_QUALITY)
        elev_z = downsample_elev(elev, tw, th)
        dem_rgb = encode_terrarium(elev_z)
        slice_matrix(dem_rgb, z, zx0, zx1, zy0, zy1, DEM_DIR, "PNG")

    print("DONE")


if __name__ == "__main__":
    main()
