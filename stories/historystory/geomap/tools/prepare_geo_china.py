#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全国范围地理数据裁剪：河流/湖泊/海岸线/海洋 + 省级界。"""
import json, os

OUT = "/tmp/shanhe"
GEO_DIR = f"{OUT}/data/geo"
DL = "/tmp/shanhe_work/dl"
BBOX = (70.0, 15.0, 138.0, 56.0)


def geom_bbox(g):
    xs, ys = [], []
    def walk(c):
        if isinstance(c[0], (int, float)):
            xs.append(c[0]); ys.append(c[1])
        else:
            for p in c: walk(p)
    walk(g["coordinates"])
    return min(xs), min(ys), max(xs), max(ys)


def inter(b1, b2):
    return not (b1[2] < b2[0] or b1[0] > b2[2] or b1[3] < b2[1] or b1[1] > b2[3])


def quant(c, nd=4):
    if isinstance(c[0], (int, float)):
        return [round(c[0], nd), round(c[1], nd)]
    return [quant(x, nd) for x in c]


def process(fc, bbox, keep, out):
    feats = []
    for f in fc.get("features", []):
        g = f.get("geometry")
        if not g:
            continue
        try:
            if not inter(geom_bbox(g), bbox):
                continue
        except Exception:
            continue
        props = {k: f["properties"][k] for k in keep if f.get("properties", {}).get(k) is not None}
        feats.append({"type": "Feature", "properties": props,
                      "geometry": {"type": g["type"], "coordinates": quant(g["coordinates"])}})
    with open(out, "w", encoding="utf-8") as fp:
        json.dump({"type": "FeatureCollection", "features": feats}, fp, ensure_ascii=False, separators=(",", ":"))
    print(f"{out}: {len(feats)} feats, {os.path.getsize(out)/1e6:.2f} MB")


def load(p):
    with open(p, encoding="utf-8") as fp:
        return json.load(fp)


process(load(f"{DL}/ne_10m_rivers_lake_centerlines.geojson"), BBOX, ["name"], f"{GEO_DIR}/rivers.json")
process(load(f"{DL}/ne_10m_lakes.geojson"), BBOX, ["name"], f"{GEO_DIR}/lakes.json")
process(load(f"{DL}/ne_10m_coastline.geojson"), BBOX, [], f"{GEO_DIR}/coastline.json")
process(load(f"{DL}/ne_10m_ocean.geojson"), BBOX, [], f"{GEO_DIR}/ocean.json")

prov = load(f"{DL}/china_provinces.json")
for f in prov["features"]:
    f["properties"] = {"shapeName": f.get("properties", {}).get("name", "")}
process(prov, BBOX, ["shapeName"], f"{OUT}/geoBoundaries-CHN-ADM3_simplified.geojson")
print("DONE")
