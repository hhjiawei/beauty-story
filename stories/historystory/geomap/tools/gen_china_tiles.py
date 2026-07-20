#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全中国古风地形瓦片：z7 Terrarium 下载 → relief/DEM z7 + z0-z6 下采样金字塔（墨卡托窗口）。
输出 tiles/china_relief/{z}/{x}/{y}.webp 与 tiles/china_dem/{z}/{x}/{y}.png。
"""
import os, math, io
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import requests
from PIL import Image

BOUNDS = (73.0, 54.0, 135.0, 17.0)  # w, n, e, s（全中国含海南台湾）
BASE_Z = 7
OUT = "/tmp/shanhe"
RELIEF_DIR = f"{OUT}/tiles/china_relief"
DEM_DIR = f"{OUT}/tiles/china_dem"
URL = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"

ELEVATION_STOPS = np.array([-200, 0, 50, 200, 600, 1200, 2000, 3000, 4500, 6000])
COLOR_STOPS = np.array([
    [160, 175, 165], [210, 195, 165], [218, 203, 172], [195, 172, 138],
    [168, 145, 115], [148, 132, 112], [178, 168, 158], [208, 203, 198],
    [228, 225, 222], [245, 243, 240]
], dtype=np.float32)
PAPER = np.array([236, 228, 208], dtype=np.float32) / 255.0


def lonlat_to_tilexy(lon, lat, z):
    x = (lon + 180.0) / 360.0 * (2 ** z)
    y = (1.0 - math.log(math.tan(math.radians(lat)) + 1.0 / math.cos(math.radians(lat))) / math.pi) / 2.0 * (2 ** z)
    return x, y


def tile_range(z, bounds):
    w, n, e, s = bounds
    return (int(math.floor(lonlat_to_tilexy(w, n, z)[0])), int(math.ceil(lonlat_to_tilexy(e, s, z)[0])),
            int(math.floor(lonlat_to_tilexy(w, n, z)[1])), int(math.ceil(lonlat_to_tilexy(e, s, z)[1])))


def tile2lat(y, z):
    return math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / (2 ** z)))))


def merc(lat):
    return math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))


def decode_terrarium(rgb):
    return (rgb[:, :, 0].astype(np.float32) * 256.0 + rgb[:, :, 1].astype(np.float32)
            + rgb[:, :, 2].astype(np.float32) / 256.0 - 32768.0)


def encode_terrarium(elev):
    v = elev + 32768.0
    r = np.floor(v / 256.0)
    rem = v - r * 256.0
    g = np.floor(rem)
    b = np.round((rem - g) * 256.0)
    return np.clip(np.stack([r, g, b], axis=-1), 0, 255).astype(np.uint8)


def colorize(elevation):
    rgb = np.zeros((*elevation.shape, 3), dtype=np.float32)
    for ch in range(3):
        rgb[:, :, ch] = np.interp(elevation, ELEVATION_STOPS, COLOR_STOPS[:, ch])
    return rgb / 255.0


def fetch(x, y, sess_local):
    url = URL.format(z=BASE_Z, x=x, y=y)
    for _ in range(3):
        try:
            r = sess_local.get(url, timeout=40)
            if r.status_code == 200:
                return x, y, r.content
        except Exception:
            pass
    print("  FAIL", url)
    return x, y, None


def slice_save(img, z, x0, x1, y0, y1, out_dir, fmt):
    n = 0
    for ty in range(y1 - y0):
        for tx in range(x1 - x0):
            t = img[ty * 256:(ty + 1) * 256, tx * 256:(tx + 1) * 256]
            if t.shape[0] != 256 or t.shape[1] != 256:
                continue
            arr = (t * 255).astype(np.uint8) if t.dtype != np.uint8 else t
            d = f"{out_dir}/{z}/{x0 + tx}"
            os.makedirs(d, exist_ok=True)
            im = Image.fromarray(arr)
            if fmt == "WEBP":
                im.save(f"{d}/{y0 + ty}.webp", "WEBP", quality=90, method=5)
            else:
                im.save(f"{d}/{y0 + ty}.png", "PNG")
            n += 1
    print(f"  z{z} -> {out_dir}: {n} ({fmt})")


def gen_low(z, elev, relief, data_cov):
    """data_cov = (L0, L1, N, S) z7 矩阵的精确覆盖范围。"""
    x0, x1, y0, y1 = tile_range(z, BOUNDS)
    W, H = (x1 - x0) * 256, (y1 - y0) * 256
    L0, L1 = x0 / (2 ** z) * 360 - 180, x1 / (2 ** z) * 360 - 180
    M_top, M_bot = merc(tile2lat(y0, z)), merc(tile2lat(y1, z))
    DL0, DL1, DN, DS = data_cov
    DM_top, DM_bot = merc(DN), merc(DS)
    px0 = (DL0 - L0) / (L1 - L0) * W
    px1 = (DL1 - L0) / (L1 - L0) * W
    py0 = (M_top - DM_top) / (M_top - M_bot) * H
    py1 = (M_top - DM_bot) / (M_top - M_bot) * H
    wT, hT = max(1, round(px1 - px0)), max(1, round(py1 - py0))
    ox, oy = max(0, round(px0)), max(0, round(py0))

    rel = np.repeat(np.repeat(PAPER[None, None, :], H, axis=0), W, axis=1).copy()
    win_r = np.array(Image.fromarray((relief * 255).astype(np.uint8)).resize((wT, hT), Image.LANCZOS), dtype=np.float32) / 255.0
    hh, ww = min(hT, H - oy), min(wT, W - ox)
    rel[oy:oy + hh, ox:ox + ww] = win_r[:hh, :ww]
    slice_save(rel, z, x0, x1, y0, y1, RELIEF_DIR, "WEBP")

    dem = np.zeros((H, W), dtype=np.float32)
    win_e = np.array(Image.fromarray(elev.astype(np.float32), mode="F").resize((wT, hT), Image.BILINEAR), dtype=np.float32)
    dem[oy:oy + hh, ox:ox + ww] = win_e[:hh, :ww]
    slice_save(encode_terrarium(dem), z, x0, x1, y0, y1, DEM_DIR, "PNG")


def main():
    x0, x1, y0, y1 = tile_range(BASE_Z, BOUNDS)
    total = (x1 - x0) * (y1 - y0)
    print(f"z{BASE_Z} range x[{x0},{x1}) y[{y0},{y1}) = {total} tiles")
    W, H = (x1 - x0) * 256, (y1 - y0) * 256
    elev = np.zeros((H, W), dtype=np.float32)

    sess = requests.Session()
    adapter = requests.adapters.HTTPAdapter(pool_connections=16, pool_maxsize=16)
    sess.mount("https://", adapter)
    jobs = [(x, y) for x in range(x0, x1) for y in range(y0, y1)]
    ok = 0
    with ThreadPoolExecutor(max_workers=12) as ex:
        for fx, fy, content in ex.map(lambda a: fetch(a[0], a[1], sess), jobs):
            if content is None:
                continue
            arr = np.array(Image.open(io.BytesIO(content)).convert("RGB"))
            elev[(fy - y0) * 256:(fy - y0 + 1) * 256, (fx - x0) * 256:(fx - x0 + 1) * 256] = decode_terrarium(arr)
            d = f"{DEM_DIR}/{BASE_Z}/{fx}"
            os.makedirs(d, exist_ok=True)
            with open(f"{d}/{fy}.png", "wb") as f:
                f.write(content)
            ok += 1
            if ok % 60 == 0:
                print(f"  {ok}/{total}")
    print(f"downloaded {ok}/{total}; elev [{elev.min():.0f},{elev.max():.0f}] m")

    relief = colorize(elev)
    slice_save(relief, BASE_Z, x0, x1, y0, y1, RELIEF_DIR, "WEBP")

    # z7 矩阵的精确覆盖范围（瓦片对齐）
    cov = (x0 / (2 ** BASE_Z) * 360 - 180, x1 / (2 ** BASE_Z) * 360 - 180,
           tile2lat(y0, BASE_Z), tile2lat(y1, BASE_Z))
    print("data coverage:", [round(c, 4) for c in cov])
    for z in [6, 5, 4, 3, 2, 1, 0]:
        gen_low(z, elev, relief, cov)
    print("DONE")


if __name__ == "__main__":
    main()
