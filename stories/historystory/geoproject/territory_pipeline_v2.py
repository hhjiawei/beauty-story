#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
历史疆域变化动态渲染 Pipeline —— 增强版 v2.0
============================================
新增功能：
1. 事件分类系统：占领/灭国/联盟/反叛/归附
2. 联盟颜色：联盟国显示为宗主国浅色版
3. 灭国处理：被灭势力全部城市归属变更
4. 归附处理：某势力全部城市归于目标势力
5. 反叛处理：反叛势力脱离原宗主
6. 城市动效数据：为前端生成变化标记

用法: python territory_pipeline_v2.py
"""

import json
import os
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

from historystory.config import root_path

# ============================================================================
# 配置区
# ============================================================================

CONFIG = {
    "city_json": root_path / "geoproject" / "data" / "city_xia.json",
    "events_json": root_path / "geoproject" / "data" / "events" / "events_xia_classified.json",
    "color_map_json": root_path / "geoproject" / "data" / "color_map_xia.json",
    "counties_geojson": root_path / "geoproject" / "data" / "china_adm3.geojson",
    "output_dir": root_path / "geoproject" / "output",

    "sjoin_predicate": "within",
    "simplify_tolerance": 0.001,
    "simplify_preserve_topology": True,

    "priority_map": {
        "都城": 4,
        "郡治": 3,
        "县治": 2,
        "关隘": 1,
        "要塞": 0,
    },

    "vassal_lighten_factor": 0.3,
    "allied_lighten_factor": 0.5,  # 联盟颜色淡化程度

    # neutral 晕染参数
    "enable_neutral_fill": True,
    "neutral_fill_max_distance": 0.8,

    # 边界平滑参数
    "enable_boundary_smooth": True,
    "smooth_buffer_size": 0.008,
    "smooth_simplify": 0.005,

    # 删除小碎片
    "remove_small_fragments": True,
    "min_fragment_area": 0.001,
}


# ============================================================================
# 工具函数
# ============================================================================

def lighten_color(hex_color: str, factor: float = 0.3) -> str:
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    r = int(r + (255 - r) * factor)
    g = int(g + (255 - g) * factor)
    b = int(b + (255 - b) * factor)
    return f"#{r:02X}{g:02X}{b:02X}"


def load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: str, data: dict):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def ensure_crs_wgs84(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    elif gdf.crs.to_string() != "EPSG:4326":
        gdf = gdf.to_crs("EPSG:4326")
    return gdf


# ============================================================================
# 阶段 0：加载县级面
# ============================================================================

def stage_0_load_counties(config: dict) -> gpd.GeoDataFrame:
    counties_path = config["counties_geojson"]

    if os.path.exists(counties_path):
        print(f"[阶段0] 加载县级面: {counties_path}")
        counties = gpd.read_file(counties_path)
    else:
        import zipfile
        zip_path = input("未找到预处理县级面，请输入 geoBoundaries ZIP 路径: ")
        extract_dir = "data/geoBoundaries_CHN_ADM3"
        with zipfile.ZipFile(zip_path, 'r') as z:
            z.extractall(extract_dir)

        shp_file = None
        for root, dirs, files in os.walk(extract_dir):
            for f in files:
                if f.endswith('.shp') and 'CHN' in f and 'ADM3' in f:
                    shp_file = os.path.join(root, f)
                    break
            if shp_file:
                break

        if not shp_file:
            raise FileNotFoundError("未找到 CHN ADM3 Shapefile")

        counties = gpd.read_file(shp_file)
        counties = ensure_crs_wgs84(counties)
        counties['county_idx'] = range(len(counties))
        counties[['county_idx', 'shapeName', 'geometry']].to_file(counties_path, driver="GeoJSON")
        print(f"[阶段0] 已预处理并保存: {counties_path}")

    print(f"[阶段0] ✅ 完成: {len(counties)} 个县级面")
    return counties


# ============================================================================
# 阶段 1：空间关联
# ============================================================================

def stage_1_spatial_join(config: dict, counties: gpd.GeoDataFrame) -> tuple[dict, dict, list]:
    print("\n[阶段1] 空间关联: 城池点 → 县级面")

    city_data = load_json(config["city_json"])
    cities_list = city_data["cities"]

    cities_gdf = gpd.GeoDataFrame(
        cities_list,
        geometry=[Point(c["lon"], c["lat"]) for c in cities_list],
        crs="EPSG:4326",
    )

    counties = ensure_crs_wgs84(counties)
    joined = gpd.sjoin(cities_gdf, counties, predicate=config["sjoin_predicate"], how="left")

    failed_cities = []
    for idx, row in joined.iterrows():
        city_id = row["id"]
        county_idx = row.get("county_idx")

        if pd.isna(county_idx):
            failed_cities.append({
                "id": city_id,
                "ancient_name": row["ancient_name"],
                "lat": row["lat"],
                "lon": row["lon"],
                "reason": "坐标不在任何县级面内",
            })
            cities_list[idx]["county_idx"] = -1
        else:
            cities_list[idx]["county_idx"] = int(county_idx)

    if failed_cities:
        print(f"⚠️  关联失败: {len(failed_cities)} 个")
        for fc in failed_cities:
            print(f"    {fc['ancient_name']} ({fc['id']})")
        failed_path = os.path.join(config["output_dir"], "failed_cities.json")
        save_json(failed_path, failed_cities)
    else:
        print("✅ 所有城池关联成功")

    county_city_map = defaultdict(list)
    for city in cities_list:
        idx = city.get("county_idx", -1)
        if idx >= 0:
            county_city_map[idx].append(city["id"])

    city_with_idx_path = os.path.join(os.path.dirname(config["city_json"]) or ".", "city_with_idx.json")
    save_json(city_with_idx_path, city_data)

    county_map_path = os.path.join(os.path.dirname(config["city_json"]) or ".", "county_city_map.json")
    save_json(county_map_path, dict(county_city_map))

    print(f"[阶段1] ✅ 完成: {len(county_city_map)} 个县级面包含城池")
    return city_data, dict(county_city_map), failed_cities


# ============================================================================
# 阶段 1.5：neutral 晕染
# ============================================================================

def fill_neutral_counties(
    counties_gdf: gpd.GeoDataFrame,
    cities_state: dict,
    max_distance: float = 0.8,
) -> gpd.GeoDataFrame:
    print(f"\n[阶段1.5] neutral 晕染: 空白县归属最近控制点...")

    control_points = []
    for city in cities_state.values():
        idx = city.get("county_idx", -1)
        if idx >= 0:
            control_points.append({
                "point": Point(city["lon"], city["lat"]),
                "owner": city["owner"],
                "vassal_of": city.get("vassal_of"),
                "allied_to": city.get("allied_to"),
            })

    print(f"  控制点: {len(control_points)} 个")

    filled_count = 0
    for idx, row in counties_gdf.iterrows():
        if row["owner"] != "neutral":
            continue

        centroid = row.geometry.centroid
        min_dist = float("inf")
        nearest = None

        for cp in control_points:
            dist = centroid.distance(cp["point"])
            if dist < min_dist and dist < max_distance:
                min_dist = dist
                nearest = cp

        if nearest:
            counties_gdf.at[idx, "owner"] = nearest["owner"]
            counties_gdf.at[idx, "vassal_of"] = nearest.get("vassal_of")
            counties_gdf.at[idx, "allied_to"] = nearest.get("allied_to")
            counties_gdf.at[idx, "is_vassal"] = nearest.get("vassal_of") is not None
            counties_gdf.at[idx, "is_allied"] = nearest.get("allied_to") is not None
            filled_count += 1

    print(f"  ✅ 晕染完成: {filled_count} 个 neutral 县被填充")
    return counties_gdf


# ============================================================================
# 阶段 2：时间断面生成（增强版，支持事件分类）
# ============================================================================

def resolve_county_owner(city_ids, cities_state, priority_map):
    cities_in_county = []
    for cid in city_ids:
        if cid not in cities_state:
            continue
        c = cities_state[cid]
        if c.get("county_idx", -1) < 0:
            continue
        cities_in_county.append(c)

    if not cities_in_county:
        return "neutral", None, False, False

    def sort_key(c):
        p = priority_map.get(c.get("type", ""), 0)
        t = c.get("last_event_time", float("-inf"))
        is_vassal = 1 if c.get("vassal_of") else 0
        is_allied = 1 if c.get("allied_to") else 0
        return (p, -is_vassal, -is_allied, t)

    cities_in_county.sort(key=sort_key, reverse=True)

    winner = cities_in_county[0]
    owner = winner["owner"]
    vassal_of = winner.get("vassal_of", None)
    allied_to = winner.get("allied_to", None)
    is_vassal = vassal_of is not None
    is_allied = allied_to is not None

    return owner, vassal_of, is_vassal, is_allied


def get_color(owner, vassal_of, allied_to, is_vassal, is_allied, color_map, config):
    colors = color_map.get("colors", color_map)

    # 联盟颜色：宗主国颜色的淡化版
    if is_allied and allied_to in colors:
        suzerain = colors[allied_to]
        allied_fill = lighten_color(suzerain.get("fill", "#CCCCCC"), config["allied_lighten_factor"])
        allied_stroke = lighten_color(suzerain.get("stroke", "#999999"), config["allied_lighten_factor"] * 0.8)
        return {
            "fill": allied_fill,
            "stroke": allied_stroke,
            "fill_opacity": suzerain.get("allied_fill_opacity", 0.45),
            "stroke_width": 0.6,
            "is_vassal": False,
            "is_allied": True,
            "suzerain": allied_to,
        }

    # 附庸颜色
    if is_vassal and vassal_of in colors:
        suzerain = colors[vassal_of]
        vassal_fill = suzerain.get("vassal_fill")
        if not vassal_fill:
            vassal_fill = lighten_color(suzerain.get("fill", "#CCCCCC"), config["vassal_lighten_factor"])
        vassal_stroke = suzerain.get("vassal_stroke")
        if not vassal_stroke:
            vassal_stroke = lighten_color(suzerain.get("stroke", "#999999"), config["vassal_lighten_factor"] * 0.8)

        return {
            "fill": vassal_fill,
            "stroke": vassal_stroke,
            "fill_opacity": suzerain.get("vassal_fill_opacity", 0.60),
            "stroke_width": 0.8,
            "is_vassal": True,
            "is_allied": False,
            "suzerain": vassal_of,
        }
    elif owner in colors:
        c = colors[owner]
        return {
            "fill": c.get("fill", "#CCCCCC"),
            "stroke": c.get("stroke", "#999999"),
            "fill_opacity": c.get("fill_opacity", 0.65),
            "stroke_width": 0.8 if owner != "neutral" else 0.3,
            "is_vassal": False,
            "is_allied": False,
            "suzerain": None,
        }
    else:
        return {
            "fill": "#CCCCCC",
            "stroke": "#999999",
            "fill_opacity": 0.3,
            "stroke_width": 0.3,
            "is_vassal": False,
            "is_allied": False,
            "suzerain": None,
        }


def smooth_boundary(geometry, buffer_size=0.008, simplify_tol=0.005):
    if geometry.is_empty or geometry is None:
        return geometry

    try:
        expanded = geometry.buffer(buffer_size, resolution=8)
        simplified = expanded.simplify(simplify_tol, preserve_topology=True)
        contracted = simplified.buffer(-buffer_size * 0.6, resolution=8)
        return contracted
    except Exception:
        return geometry


def remove_small_fragments(geometry, min_area):
    if geometry.is_empty or geometry.area < min_area:
        return geometry

    if geometry.geom_type == "MultiPolygon":
        significant = [p for p in geometry.geoms if p.area > min_area]
        if significant:
            from shapely.geometry import MultiPolygon
            return MultiPolygon(significant)
        else:
            return max(geometry.geoms, key=lambda p: p.area)

    return geometry


def generate_time_slice(
    counties_gdf: gpd.GeoDataFrame,
    counties_state: dict,
    color_map: dict,
    config: dict,
    output_path: str,
    metadata: dict | None = None,
):
    gdf = counties_gdf.copy()

    gdf["owner"] = gdf["county_idx"].map(lambda i: counties_state.get(i, {}).get("owner", "neutral"))
    gdf["vassal_of"] = gdf["county_idx"].map(lambda i: counties_state.get(i, {}).get("vassal_of", None))
    gdf["allied_to"] = gdf["county_idx"].map(lambda i: counties_state.get(i, {}).get("allied_to", None))
    gdf["is_vassal"] = gdf["county_idx"].map(lambda i: counties_state.get(i, {}).get("is_vassal", False))
    gdf["is_allied"] = gdf["county_idx"].map(lambda i: counties_state.get(i, {}).get("is_allied", False))

    dissolved = gdf.dissolve(by="owner", as_index=False)

    if config["enable_boundary_smooth"]:
        dissolved["geometry"] = dissolved.geometry.apply(
            lambda g: smooth_boundary(g, config["smooth_buffer_size"], config["smooth_simplify"])
        )

    if config["remove_small_fragments"]:
        dissolved["geometry"] = dissolved.geometry.apply(
            lambda g: remove_small_fragments(g, config["min_fragment_area"])
        )

    def get_dominant_props(owner_val):
        mask = gdf["owner"] == owner_val
        if not mask.any():
            return None, False, False
        subset = gdf[mask].copy()
        subset["area"] = subset.geometry.area
        dominant = subset.sort_values("area", ascending=False).iloc[0]
        return dominant["vassal_of"], dominant["allied_to"], dominant["is_vassal"], dominant["is_allied"]

    color_props = []
    for _, row in dissolved.iterrows():
        owner = row["owner"]
        vassal_of, allied_to, is_vassal, is_allied = get_dominant_props(owner)
        color = get_color(owner, vassal_of, allied_to, is_vassal, is_allied, color_map, config)
        color_props.append(color)

    for key in ["fill", "stroke", "fill_opacity", "stroke_width", "is_vassal", "is_allied", "suzerain"]:
        dissolved[key] = [c[key] for c in color_props]

    dissolved["county_count"] = dissolved["owner"].map(
        lambda o: sum(1 for s in counties_state.values() if s.get("owner") == o)
    )
    dissolved["country"] = dissolved["owner"]

    if config["simplify_tolerance"] > 0:
        dissolved["geometry"] = dissolved["geometry"].simplify(
            tolerance=config["simplify_tolerance"],
            preserve_topology=True,
        )

    export_cols = ["country", "owner", "fill", "stroke", "fill_opacity", "stroke_width",
                   "is_vassal", "is_allied", "suzerain", "county_count", "geometry"]
    features = json.loads(dissolved[[c for c in export_cols if c in dissolved.columns]].to_json())["features"]

    feature_collection = {
        "type": "FeatureCollection",
        "metadata": metadata or {},
        "features": features,
    }

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(feature_collection, f, ensure_ascii=False)

    return len(features)


def stage_2_generate_slices(config: dict, city_data: dict, county_city_map: dict, counties_gdf: gpd.GeoDataFrame):
    print("\n[阶段2] 生成时间断面...")

    events_data = load_json(config["events_json"])
    color_map = load_json(config["color_map_json"])
    events = sorted(events_data.get("events", []), key=lambda e: e["year"])

    # 1. 初始化城池状态
    cities_state = {}
    for city in city_data["cities"]:
        cities_state[city["id"]] = {
            **city,
            "owner": city["initial_owner"],
            "last_event_time": float("-inf"),
        }

    # 2. 初始化县级面归属
    counties_state = {}
    for idx in range(len(counties_gdf)):
        if idx in county_city_map:
            city_ids = county_city_map[idx]
            owner, vassal_of, is_vassal, is_allied = resolve_county_owner(city_ids, cities_state, config["priority_map"])
        else:
            owner, vassal_of, is_vassal, is_allied = "neutral", None, False, False

        counties_state[idx] = {
            "owner": owner,
            "vassal_of": vassal_of,
            "allied_to": None,
            "is_vassal": is_vassal,
            "is_allied": is_allied,
        }

    # neutral 晕染（初始状态）
    if config["enable_neutral_fill"]:
        counties_gdf_copy = counties_gdf.copy()
        counties_gdf_copy["owner"] = counties_gdf_copy["county_idx"].map(
            lambda i: counties_state.get(i, {}).get("owner", "neutral")
        )
        counties_gdf_copy["vassal_of"] = counties_gdf_copy["county_idx"].map(
            lambda i: counties_state.get(i, {}).get("vassal_of", None)
        )
        counties_gdf_copy["allied_to"] = counties_gdf_copy["county_idx"].map(
            lambda i: counties_state.get(i, {}).get("allied_to", None)
        )
        counties_gdf_copy["is_vassal"] = counties_gdf_copy["county_idx"].map(
            lambda i: counties_state.get(i, {}).get("is_vassal", False)
        )
        counties_gdf_copy["is_allied"] = counties_gdf_copy["county_idx"].map(
            lambda i: counties_state.get(i, {}).get("is_allied", False)
        )

        counties_gdf_copy = fill_neutral_counties(
            counties_gdf_copy, cities_state, config["neutral_fill_max_distance"]
        )

        for idx, row in counties_gdf_copy.iterrows():
            counties_state[idx] = {
                "owner": row["owner"],
                "vassal_of": row["vassal_of"] if pd.notna(row["vassal_of"]) else None,
                "allied_to": row["allied_to"] if pd.notna(row["allied_to"]) else None,
                "is_vassal": row["is_vassal"] if pd.notna(row["is_vassal"]) else False,
                "is_allied": row["is_allied"] if pd.notna(row["is_allied"]) else False,
            }

        print(f"  初始状态晕染完成")

    output_dir = config["output_dir"]
    os.makedirs(output_dir, exist_ok=True)

    # 3. 生成初始时间断面
    initial_path = os.path.join(output_dir, "time_slice_initial.geojson")
    n_features = generate_time_slice(
        counties_gdf, counties_state, color_map, config,
        initial_path,
        metadata={"year": events[0]["year"] if events else 0, "event": "initial", "title": "初始状态", "type": "initial"},
    )
    print(f"  ✅ 初始断面: {n_features} 个国家/势力")

    # 4. 遍历事件
    slice_index = []
    animation_events = []  # 记录城市变化动画数据

    for event in events:
        event_type = event.get("type", "占领")
        affected_counties = set()
        changed_cities = []  # 记录本次事件变化的城市

        # 处理不同类型的事件
        if event_type == "灭国":
            # 灭国：被灭势力的所有城市归于进攻者
            for change in event.get("changes", []):
                target_power = change["from"]  # 被灭的势力
                conqueror = change["to"]       # 进攻者

                # 找到所有属于被灭势力的城市
                for cid, city in cities_state.items():
                    if city["owner"] == target_power:
                        cities_state[cid]["owner"] = conqueror
                        cities_state[cid]["last_event_time"] = event["year"]
                        cities_state[cid]["vassal_of"] = None
                        cities_state[cid]["allied_to"] = None
                        changed_cities.append({
                            "city_id": cid,
                            "from": target_power,
                            "to": conqueror,
                            "type": "灭国"
                        })
                        county_idx = cities_state[cid].get("county_idx", -1)
                        if county_idx >= 0:
                            affected_counties.add(county_idx)

        elif event_type == "归附":
            # 归附：某势力的所有城市归于目标势力
            for change in event.get("changes", []):
                target_power = change["from"]  # 归附的势力
                new_owner = change["to"]       # 目标势力

                for cid, city in cities_state.items():
                    if city["owner"] == target_power:
                        cities_state[cid]["owner"] = new_owner
                        cities_state[cid]["last_event_time"] = event["year"]
                        cities_state[cid]["vassal_of"] = change.get("vassal_of")
                        changed_cities.append({
                            "city_id": cid,
                            "from": target_power,
                            "to": new_owner,
                            "type": "归附"
                        })
                        county_idx = cities_state[cid].get("county_idx", -1)
                        if county_idx >= 0:
                            affected_counties.add(county_idx)

        elif event_type == "反叛":
            # 反叛：反叛的势力脱离原宗主
            for change in event.get("changes", []):
                cid = change["city_id"]
                if cid in cities_state:
                    old_owner = cities_state[cid]["owner"]
                    cities_state[cid]["owner"] = change["to"]
                    cities_state[cid]["last_event_time"] = event["year"]
                    cities_state[cid]["vassal_of"] = None
                    cities_state[cid]["allied_to"] = None
                    changed_cities.append({
                        "city_id": cid,
                        "from": old_owner,
                        "to": change["to"],
                        "type": "反叛"
                    })
                    county_idx = cities_state[cid].get("county_idx", -1)
                    if county_idx >= 0:
                        affected_counties.add(county_idx)

        elif event_type == "联盟":
            # 联盟：联盟国变为同一颜色的浅色系
            for change in event.get("changes", []):
                cid = change["city_id"]
                if cid in cities_state:
                    cities_state[cid]["allied_to"] = change.get("allied_to")
                    cities_state[cid]["vassal_of"] = change.get("vassal_of")
                    cities_state[cid]["last_event_time"] = event["year"]
                    changed_cities.append({
                        "city_id": cid,
                        "from": change["from"],
                        "to": change["to"],
                        "type": "联盟",
                        "allied_to": change.get("allied_to")
                    })
                    county_idx = cities_state[cid].get("county_idx", -1)
                    if county_idx >= 0:
                        affected_counties.add(county_idx)

        else:  # 占领（默认）
            for change in event.get("changes", []):
                cid = change["city_id"]
                if cid not in cities_state:
                    print(f"    ⚠️ 警告: city_id {cid} 不存在")
                    continue

                cities_state[cid]["owner"] = change["to"]
                cities_state[cid]["last_event_time"] = event["year"]

                if "vassal_of" in change:
                    cities_state[cid]["vassal_of"] = change["vassal_of"]
                if "allied_to" in change:
                    cities_state[cid]["allied_to"] = change["allied_to"]

                changed_cities.append({
                    "city_id": cid,
                    "from": change["from"],
                    "to": change["to"],
                    "type": "占领"
                })

                county_idx = cities_state[cid].get("county_idx", -1)
                if county_idx >= 0:
                    affected_counties.add(county_idx)

        # 重新计算受影响县的归属
        for county_idx in affected_counties:
            city_ids = county_city_map.get(county_idx, [])
            owner, vassal_of, is_vassal, is_allied = resolve_county_owner(city_ids, cities_state, config["priority_map"])
            counties_state[county_idx] = {
                "owner": owner,
                "vassal_of": vassal_of,
                "allied_to": None,  # 县级面不直接存 allied_to，由城市决定
                "is_vassal": is_vassal,
                "is_allied": is_allied,
            }

        # 每次事件后重新晕染
        if config["enable_neutral_fill"] and affected_counties:
            temp_gdf = counties_gdf.copy()
            temp_gdf["owner"] = temp_gdf["county_idx"].map(
                lambda i: counties_state.get(i, {}).get("owner", "neutral")
            )
            temp_gdf["vassal_of"] = temp_gdf["county_idx"].map(
                lambda i: counties_state.get(i, {}).get("vassal_of", None)
            )
            temp_gdf["allied_to"] = temp_gdf["county_idx"].map(
                lambda i: counties_state.get(i, {}).get("allied_to", None)
            )
            temp_gdf["is_vassal"] = temp_gdf["county_idx"].map(
                lambda i: counties_state.get(i, {}).get("is_vassal", False)
            )
            temp_gdf["is_allied"] = temp_gdf["county_idx"].map(
                lambda i: counties_state.get(i, {}).get("is_allied", False)
            )

            temp_gdf = fill_neutral_counties(temp_gdf, cities_state, config["neutral_fill_max_distance"])

            for idx, row in temp_gdf.iterrows():
                if row["owner"] != "neutral":
                    counties_state[idx] = {
                        "owner": row["owner"],
                        "vassal_of": row["vassal_of"] if pd.notna(row["vassal_of"]) else None,
                        "allied_to": row["allied_to"] if pd.notna(row["allied_to"]) else None,
                        "is_vassal": row["is_vassal"] if pd.notna(row["is_vassal"]) else False,
                        "is_allied": row["is_allied"] if pd.notna(row["is_allied"]) else False,
                    }

        # 生成时间断面
        year = event["year"]
        year_str = f"BC{abs(year)}" if year < 0 else str(year)
        filename = f"time_slice_{year_str}_{event['id']}.geojson"
        filepath = os.path.join(output_dir, filename)

        n_features = generate_time_slice(
            counties_gdf, counties_state, color_map, config,
            filepath,
            metadata={"year": year, "event": event["id"], "title": event["title"], "type": event_type},
        )

        # 记录动画事件
        animation_events.append({
            "year": year,
            "event_id": event["id"],
            "title": event["title"],
            "type": event_type,
            "file": filename,
            "changed_cities": changed_cities,
            "note": event.get("note", ""),
            "source": event.get("source", ""),
        })

        slice_index.append({
            "year": year,
            "event_id": event["id"],
            "title": event["title"],
            "type": event_type,
            "file": filename,
            "changes_count": len(event.get("changes", [])),
            "features_count": n_features,
        })

        print(f"  ✅ {event['year']}年 {event['title']} [{event_type}]: {filename} ({n_features} 个国家)")

    # 5. 保存索引
    index_path = os.path.join(output_dir, "slice_index.json")
    save_json(index_path, slice_index)

    # 6. 保存动画事件数据（供前端使用）
    anim_path = os.path.join(output_dir, "animation_events.json")
    save_json(anim_path, animation_events)

    print(f"\n[阶段2] ✅ 全部完成！共 {len(slice_index) + 1} 个时间断面")
    print(f"  索引: {index_path}")
    print(f"  动画数据: {anim_path}")

    return slice_index


# ============================================================================
# 主流程
# ============================================================================

def main():
    print("=" * 60)
    print("历史疆域变化动态渲染 Pipeline —— 增强版 v2.0")
    print(f"开始: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print(f"\n功能开关:")
    print(f"  neutral 晕染: {'✅ 开启' if CONFIG['enable_neutral_fill'] else '❌ 关闭'}")
    print(f"  边界平滑: {'✅ 开启' if CONFIG['enable_boundary_smooth'] else '❌ 关闭'}")
    print(f"  删除小碎片: {'✅ 开启' if CONFIG['remove_small_fragments'] else '❌ 关闭'}")
    print(f"\n事件分类支持: 占领 | 灭国 | 联盟 | 反叛 | 归附")

    counties_gdf = stage_0_load_counties(CONFIG)
    city_data, county_city_map, failed = stage_1_spatial_join(CONFIG, counties_gdf)
    slice_index = stage_2_generate_slices(CONFIG, city_data, county_city_map, counties_gdf)

    print("\n" + "=" * 60)
    print("Pipeline 执行完成！")
    print("=" * 60)
    print(f"\n输出文件:")
    print(f"  📁 {CONFIG['output_dir']}/")
    print(f"     ├── time_slice_initial.geojson")
    for s in slice_index:
        print(f"     ├── {s['file']}")
    print(f"     ├── slice_index.json")
    print(f"     └── animation_events.json")
    print(f"\n下一步:")
    print(f"  1. 在 QGIS 中打开 time_slice_initial.geojson 验证")
    print(f"  2. 启动前端页面查看动效")


if __name__ == "__main__":
    main()