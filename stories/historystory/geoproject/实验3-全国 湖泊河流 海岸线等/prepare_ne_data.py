#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
预处理 Natural Earth 数据：裁剪中国区域，转 GeoJSON
"""

import os
import geopandas as gpd
from shapely.geometry import box

from historystory.config import root_path

# ==================== 配置 ====================
NE_PHYSICAL_DIR = root_path + "/land"
OUTPUT_DIR = "../geojson"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 中国大致边界（含周边海洋，确保海岸线完整）
CHINA_BOUNDS = (70, 15, 140, 55)  # minx, miny, maxx, maxy

# 古风配色（供前端参考）
COLORS = {
    "ocean": "#8ba89a",
    "lake": "#9bb8aa",
    "river": "#7a9a8a",
    "coastline": "#5a7a6a",
}


# ==================== 裁剪函数 ====================
def clip_to_china(gdf, bounds=CHINA_BOUNDS):
    minx, miny, maxx, maxy = bounds
    bbox = gpd.GeoDataFrame(
        geometry=[box(minx, miny, maxx, maxy)],
        crs="EPSG:4326"
    )
    if gdf.crs is None:
        gdf.set_crs("EPSG:4326", inplace=True)
    elif gdf.crs.to_string() != "EPSG:4326":
        gdf = gdf.to_crs("EPSG:4326")

    clipped = gpd.overlay(gdf, bbox, how='intersection')
    return clipped


# ==================== 处理海洋 ====================
print("处理海洋...")
ocean_path = os.path.join(NE_PHYSICAL_DIR, "ne_10m_ocean.shp")
if os.path.exists(ocean_path):
    gdf = gpd.read_file(ocean_path)
    clipped = clip_to_china(gdf)
    out = os.path.join(OUTPUT_DIR, "ocean.json")
    clipped.to_file(out, driver="GeoJSON")
    print(f"  ✅ 海洋: {len(clipped)} 个面 → {out}")
else:
    print("  ⚠️ 未找到 ne_10m_ocean.shp")

# ==================== 处理湖泊 ====================
print("处理湖泊...")
lakes_path = os.path.join(NE_PHYSICAL_DIR, "ne_10m_lakes.shp")
if os.path.exists(lakes_path):
    gdf = gpd.read_file(lakes_path)
    # 过滤小湖泊，只保留面积大的（>50km²）
    gdf = gdf[gdf.geometry.area > 0.05]
    clipped = clip_to_china(gdf)
    out = os.path.join(OUTPUT_DIR, "lakes.json")
    clipped.to_file(out, driver="GeoJSON")
    print(f"  ✅ 湖泊: {len(clipped)} 个面 → {out}")
else:
    print("  ⚠️ 未找到 ne_10m_lakes.shp")

# ==================== 处理河流 ====================
print("处理河流...")
rivers_path = os.path.join(NE_PHYSICAL_DIR, "ne_10m_rivers_lake_centerlines.shp")
if os.path.exists(rivers_path):
    gdf = gpd.read_file(rivers_path)
    # 只保留主要河流（有名称的，或长度较长的）
    if 'name' in gdf.columns:
        gdf = gdf[gdf['name'].notna() | (gdf.geometry.length > 0.5)]
    clipped = clip_to_china(gdf)
    out = os.path.join(OUTPUT_DIR, "rivers.json")
    clipped.to_file(out, driver="GeoJSON")
    print(f"  ✅ 河流: {len(clipped)} 条线 → {out}")
else:
    print("  ⚠️ 未找到 ne_10m_rivers_lake_centerlines.shp")

# ==================== 处理海岸线 ====================
print("处理海岸线...")
coast_path = os.path.join(NE_PHYSICAL_DIR, "ne_10m_coastline.shp")
if os.path.exists(coast_path):
    gdf = gpd.read_file(coast_path)
    clipped = clip_to_china(gdf)
    out = os.path.join(OUTPUT_DIR, "coastline.json")
    clipped.to_file(out, driver="GeoJSON")
    print(f"  ✅ 海岸线: {len(clipped)} 条线 → {out}")
else:
    print("  ⚠️ 未找到 ne_10m_coastline.shp")

print(f"\n全部完成！GeoJSON 输出在: {os.path.abspath(OUTPUT_DIR)}/")
print("启动服务器后，地图会自动加载这些图层。")