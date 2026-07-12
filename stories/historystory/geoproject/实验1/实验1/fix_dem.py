#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DEM 瓦片诊断与修复：一键补全缺失的 z=4,5,6 Terrarium PNG
"""

import os
import math
import asyncio
import aiohttp

BOUNDS = (73.0, 54.0, 136.0, 18.0)
TERRARIUM_URL = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
DEM_DIR = "tiles/dem"


def lat2tiley(lat, zoom):
    return (1.0 - math.log(math.tan(math.radians(lat)) + 1.0 / math.cos(math.radians(lat))) / math.pi) / 2.0 * (
                2 ** zoom)


def get_tile_range(zoom, bounds):
    w, n, e, s = bounds
    x0 = int(math.floor((w + 180.0) / 360.0 * (2 ** zoom)))
    x1 = int(math.ceil((e + 180.0) / 360.0 * (2 ** zoom)))
    y0 = int(math.floor(lat2tiley(n, zoom)))
    y1 = int(math.ceil(lat2tiley(s, zoom)))
    return x0, x1, y0, y1


async def fetch_tile(session, z, x, y):
    url = TERRARIUM_URL.format(z=z, x=x, y=y)
    path = f"{DEM_DIR}/{z}/{x}/{y}.png"
    if os.path.exists(path):
        return True, "exist"
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            if resp.status == 200:
                data = await resp.read()
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "wb") as f:
                    f.write(data)
                return True, "downloaded"
            else:
                return False, f"HTTP {resp.status}"
    except Exception as e:
        return False, str(e)


async def main():
    print("=" * 55)
    print("DEM 瓦片诊断与修复")
    print("=" * 55)

    for z in [4, 5, 6]:
        x0, x1, y0, y1 = get_tile_range(z, BOUNDS)
        total = (x1 - x0) * (y1 - y0)
        existing = sum(1 for x in range(x0, x1) for y in range(y0, y1) if os.path.exists(f"{DEM_DIR}/{z}/{x}/{y}.png"))
        print(f"\nz={z}: 已有 {existing}/{total} 张")

        if existing >= total:
            print("  ✅ 完整，无需补全")
            continue

        missing = total - existing
        print(f"  ⬇️  补全缺失的 {missing} 张...")

        connector = aiohttp.TCPConnector(limit=20)
        async with aiohttp.ClientSession(connector=connector) as session:
            tasks = []
            coords = []
            for x in range(x0, x1):
                for y in range(y0, y1):
                    if not os.path.exists(f"{DEM_DIR}/{z}/{x}/{y}.png"):
                        tasks.append(fetch_tile(session, z, x, y))
                        coords.append((x, y))

            if tasks:
                results = await asyncio.gather(*tasks)
                success = sum(1 for r, _ in results if r)
                failed = len(tasks) - success
                print(f"  ✅ 成功: {success} | ❌ 失败: {failed}")
                if failed > 0:
                    for i, (ok, status) in enumerate(results):
                        if not ok:
                            print(f"     {z}/{coords[i][0]}/{coords[i][1]}: {status}")

    print("\n" + "=" * 55)
    print("修复完成。重新启动服务器，访问 xia_3d_story.html")
    print("=" * 55)


if __name__ == "__main__":
    asyncio.run(main())