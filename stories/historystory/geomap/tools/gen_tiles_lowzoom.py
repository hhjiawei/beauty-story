#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""修正版低层级瓦片生成：按墨卡托窗口正确嵌置数据区，外部留白/0m。
从已生成的 z8 DEM 瓦片重建高程矩阵，离线运行。
覆盖：DEM z0–z7（z8 已有）、relief z6/z7（z8 已有）。
"""
import os, math
import numpy as np
from PIL import Image

OUT = "/tmp/shanhe"
RELIEF_DIR = f"{OUT}/tiles/henan_relief"
DEM_DIR = f"{OUT}/tiles/henan_dem"

# z8 数据区的精确瓦片对齐范围
Z8_X0, Z8_X1, Z8_Y0, Z8_Y1 = 206, 212, 99, 105
DATA_L0 = Z8_X0 / 256 * 360 - 180
DATA_L1 = Z8_X1 / 256 * 360 - 180
def tile2lat(y, z): return math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / (2 ** z)))))
DATA_N = tile2lat(Z8_Y0, 8)
DATA_S = tile2lat(Z8_Y1, 8)

BOUNDS = (110.0, 37.0, 117.0, 31.0)
PAPER = np.array([236, 228, 208], dtype=np.float32) / 255.0

ELEVATION_STOPS = np.array([-200, 0, 50, 200, 600, 1200, 2000, 3000, 4500, 6000])
COLOR_STOPS = np.array([
    [160, 175, 165], [210, 195, 165], [218, 203, 172], [195, 172, 138],
    [168, 145, 115], [148, 132, 112], [178, 168, 158], [208, 203, 198],
    [228, 225, 222], [245, 243, 240]
], dtype=np.float32)


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


def merc(lat):
    return math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))


def rebuild_z8_elev():
    W = (Z8_X1 - Z8_X0) * 256
    H = (Z8_Y1 - Z8_Y0) * 256
    elev = np.zeros((H, W), dtype=np.float32)
    for x in range(Z8_X0, Z8_X1):
        for y in range(Z8_Y0, Z8_Y1):
            p = f"{DEM_DIR}/8/{x}/{y}.png"
            arr = np.array(Image.open(p).convert("RGB"))
            elev[(y - Z8_Y0) * 256:(y - Z8_Y0 + 1) * 256, (x - Z8_X0) * 256:(x - Z8_X0 + 1) * 256] = decode_terrarium(arr)
    return elev


def resize_f(arr, w, h):
    return np.array(Image.fromarray(arr.astype(np.float32), mode="F").resize((w, h), Image.BILINEAR), dtype=np.float32)


def resize_rgb(arr, w, h):
    im = Image.fromarray((arr * 255).astype(np.uint8)).resize((w, h), Image.LANCZOS)
    return np.array(im, dtype=np.float32) / 255.0


def slice_save(img, zoom, x0, x1, y0, y1, out_dir, fmt):
    tile = 256
    n = 0
    for ty in range(y1 - y0):
        for tx in range(x1 - x0):
            t = img[ty * tile:(ty + 1) * tile, tx * tile:(tx + 1) * tile]
            arr = (t * 255).astype(np.uint8) if t.dtype != np.uint8 else t
            d = f"{out_dir}/{zoom}/{x0 + tx}"
            os.makedirs(d, exist_ok=True)
            im = Image.fromarray(arr)
            if fmt == "WEBP":
                im.save(f"{d}/{y0 + ty}.webp", "WEBP", quality=92, method=6)
            else:
                im.save(f"{d}/{y0 + ty}.png", "PNG")
            n += 1
    print(f"  z{zoom} -> {out_dir}: {n} ({fmt})")


def gen_low(z, elev, relief):
    x0, x1, y0, y1 = get_tile_range(z, BOUNDS)
    W, H = (x1 - x0) * 256, (y1 - y0) * 256
    L0, L1 = x0 / (2 ** z) * 360 - 180, x1 / (2 ** z) * 360 - 180
    M_top, M_bot = merc(tile2lat(y0, z)), merc(tile2lat(y1, z))  # 北→南
    DM_top, DM_bot = merc(DATA_N), merc(DATA_S)

    px0 = (DATA_L0 - L0) / (L1 - L0) * W
    px1 = (DATA_L1 - L0) / (L1 - L0) * W
    py0 = (M_top - DM_top) / (M_top - M_bot) * H
    py1 = (M_top - DM_bot) / (M_top - M_bot) * H
    wT, hT = max(1, round(px1 - px0)), max(1, round(py1 - py0))
    ox, oy = round(px0), round(py0)

    # relief：纸底 + 数据窗口
    rel = np.repeat(PAPER[None, None, :], H, axis=0).repeat(W, axis=1).copy()
    win = resize_rgb(relief, wT, hT)
    rel[oy:oy + hT, ox:ox + wT] = win
    slice_save(rel, z, x0, x1, y0, y1, RELIEF_DIR, "WEBP")

    # DEM：0m 底 + 数据窗口
    dem = np.zeros((H, W), dtype=np.float32)
    ewin = resize_f(elev, wT, hT)
    dem[oy:oy + hT, ox:ox + wT] = ewin
    slice_save(encode_terrarium(dem), z, x0, x1, y0, y1, DEM_DIR, "PNG")


def main():
    print(f"data coverage lon[{DATA_L0},{DATA_L1}] lat[{DATA_S:.4f},{DATA_N:.4f}]")
    elev = rebuild_z8_elev()
    print("z8 elev rebuilt:", elev.shape, f"[{elev.min():.0f},{elev.max():.0f}] m")
    relief = colorize(elev)
    for z in [7, 6]:
        gen_low(z, elev, relief)
    # 低层级仅 DEM（relief 源 minzoom=6，不会请求更低）
    for z in [5, 4, 3, 2, 1, 0]:
        gen_low(z, elev, relief)
    # 删除低层级多余的 relief（保持目录干净，仅留 z6-8）
    print("DONE")


if __name__ == "__main__":
    main()
