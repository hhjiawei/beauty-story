#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
山河裂变 · 离线预处理管线
输入: data_raw/{china_counties.geojson, dem/*.png, ne_*, events_src.json}
输出: data/{heightmap.png, terrain.json, relief.jpg, counties.bin, county_lines.json,
        boundaries/*.json, timeline.json, cities.json, factions.json, geo/*.json}

操作流程
1 复制一份项目目录（data/ 里的 heightmap、counties.bin、county_lines、geo 可以保留，删掉 timeline、boundaries、cities、factions 让管线重新生成）
2 改 preprocess.py 的势力/城池表 + 写好新的事件 JSON
3 重跑 python3 tools/preprocess.py（只跑 replay 阶段的话几分钟，全量重跑约十几分钟）
4 起服务打开即是一个新专题

"""
import json, math, os, struct
from collections import defaultdict
from pathlib import Path

import numpy as np
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point
from PIL import Image
import mapbox_earcut as earcut

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data_raw"
OUT = ROOT / "data"

BBOX = [73.0, 17.9, 135.1, 53.6]
HM_W, HM_H = 2048, 1152
DEM_Z = 7
NEUTRAL_FILL_MAX_DIST = 0.8
SIMPLIFY_COUNTY = 0.001
SMOOTH_BUF, SMOOTH_SIMPLIFY = 0.008, 0.005
MIN_FRAGMENT_AREA = 0.001
VASSAL_LIGHTEN = 0.3
TIER_PRIORITY = {1: 4, 2: 3, 3: 2}

CITIES = [
    {"id":"bo","name":"亳","location":[115.65,34.45],"owner":"shang","tier":1,"note":"商汤之都（今河南商丘北）"},
    {"id":"xiao","name":"嚣","location":[113.65,34.75],"owner":"shang","tier":2,"note":"隞都，郑州商城"},
    {"id":"yin","name":"殷","location":[114.35,36.10],"owner":"shang","tier":2,"note":"今河南安阳殷墟"},
    {"id":"zhaoge","name":"朝歌","location":[114.20,35.60],"owner":"shang","tier":2,"note":"纣之行都（今河南淇县）"},
    {"id":"youli","name":"羑里","location":[114.37,35.92],"owner":"shang","tier":3,"note":"今河南汤阴北"},
    {"id":"mengjin","name":"孟津","location":[112.43,34.83],"owner":"shang","tier":3,"note":"黄河渡口"},
    {"id":"muye","name":"牧野","location":[113.90,35.40],"owner":"shang","tier":3,"note":"今河南新乡北郊"},
    {"id":"li","name":"黎","location":[113.12,36.20],"owner":"shang","tier":3,"note":"黎国（今山西长治西南）"},
    {"id":"zhenxun","name":"斟鄩","location":[113.02,34.75],"owner":"xia","tier":1,"note":"夏都（今河南巩义西南）"},
    {"id":"anyi","name":"安邑","location":[111.22,35.14],"owner":"xia","tier":2,"note":"夏都之一（今山西运城夏县）"},
    {"id":"xibo","name":"西亳","location":[112.78,34.72],"owner":"xia","tier":2,"note":"今河南偃师"},
    {"id":"gec","name":"葛","location":[115.32,34.45],"owner":"ge","tier":3,"note":"葛国（今河南宁陵北）"},
    {"id":"weic","name":"韦","location":[114.55,35.58],"owner":"wei","tier":3,"note":"豕韦（今河南滑县东南）"},
    {"id":"guc","name":"顾","location":[115.50,35.85],"owner":"gu","tier":3,"note":"顾国（今山东范县东南）"},
    {"id":"kunwuc","name":"昆吾","location":[115.03,35.76],"owner":"kunwu","tier":3,"note":"昆吾（今河南濮阳）"},
    {"id":"guifangzhai","name":"鬼方","location":[110.80,37.60],"owner":"guifang","tier":3,"note":"晋陕高原方国"},
    {"id":"yucheng","name":"虞","location":[111.20,34.85],"owner":"yu","tier":3,"note":"虞国（今山西平陆北）"},
    {"id":"ruicheng","name":"芮","location":[110.70,34.70],"owner":"rui","tier":3,"note":"芮国（今山西芮城）"},
    {"id":"feng","name":"丰","location":[108.72,34.20],"owner":"zhou","tier":1,"note":"周都（今陕西西安西南）"},
    {"id":"hao","name":"镐","location":[108.85,34.26],"owner":"zhou","tier":2,"note":"今陕西西安西"},
]
FACTIONS = [
    {"id":"shang","name":"商","color":"#a63a2b","founded":-1600,"fallen":None},
    {"id":"xia","name":"夏","color":"#4a5560","founded":-2070,"fallen":None},
    {"id":"ge","name":"葛","color":"#7a6c4f","founded":None,"fallen":None},
    {"id":"wei","name":"韦","color":"#5d7052","founded":None,"fallen":None},
    {"id":"gu","name":"顾","color":"#8c6a3f","founded":None,"fallen":None},
    {"id":"kunwu","name":"昆吾","color":"#6b4f6e","founded":None,"fallen":None},
    {"id":"guifang","name":"鬼方","color":"#7d7a63","founded":None,"fallen":None},
    {"id":"yu","name":"虞","color":"#5e7a8a","founded":None,"fallen":None},
    {"id":"rui","name":"芮","color":"#8a5e6e","founded":None,"fallen":None},
    {"id":"zhou","name":"周","color":"#b0762a","founded":None,"fallen":None},
]
EVENTS = json.loads((RAW / "events_src.json").read_text(encoding="utf-8"))["events"]

def lighten(h, f=0.3):
    h = h.lstrip("#"); r,g,b = int(h[0:2],16),int(h[2:4],16),int(h[4:6],16)
    return "#{:02X}{:02X}{:02X}".format(int(r+(255-r)*f),int(g+(255-g)*f),int(b+(255-b)*f))
def darken(h, f=0.25):
    h = h.lstrip("#"); r,g,b = int(h[0:2],16),int(h[2:4],16),int(h[4:6],16)
    return "#{:02X}{:02X}{:02X}".format(int(r*(1-f)),int(g*(1-f)),int(b*(1-f)))
def smooth_geom(g):
    try:
        return g.buffer(SMOOTH_BUF, resolution=8).simplify(SMOOTH_SIMPLIFY, preserve_topology=True).buffer(-SMOOTH_BUF*0.6, resolution=8)
    except Exception:
        return g
def drop_fragments(g, min_area=MIN_FRAGMENT_AREA):
    if g.is_empty or g.area < min_area: return g
    if g.geom_type == "MultiPolygon":
        from shapely.geometry import MultiPolygon
        keep = [p for p in g.geoms if p.area > min_area]
        return MultiPolygon(keep) if keep else max(g.geoms, key=lambda p: p.area)
    return g
def lonlat_to_tilexy(lon, lat, z):
    n = 2 ** z
    x = (lon + 180.0) / 360.0 * n
    r = math.radians(lat)
    y = (1.0 - math.log(math.tan(r) + 1.0/math.cos(r)) / math.pi) / 2.0 * n
    return x, y

def bake_heightmap():
    print("[A] 烘焙高程...")
    tiles = {}
    for f in os.listdir(RAW / "dem"):
        z, x, y = f.replace(".png","").split("_")
        tiles[(int(x), int(y))] = Image.open(RAW / "dem" / f).convert("RGB")
    xs = [t[0] for t in tiles]; ys = [t[1] for t in tiles]
    tx0, tx1, ty0, ty1 = min(xs), max(xs), min(ys), max(ys)
    mw, mh = (tx1-tx0+1)*256, (ty1-ty0+1)*256
    mosaic = np.zeros((mh, mw, 3), dtype=np.uint8)
    for (x, y), im in tiles.items():
        mosaic[(y-ty0)*256:(y-ty0+1)*256, (x-tx0)*256:(x-tx0+1)*256] = np.asarray(im)
    dem = mosaic[:,:,0].astype(np.float32)*256 + mosaic[:,:,1].astype(np.float32) + mosaic[:,:,2].astype(np.float32)/256.0 - 32768.0
    out = np.full((HM_H, HM_W), -500.0, dtype=np.float32)
    lons = BBOX[0] + (np.arange(HM_W)+0.5)/HM_W * (BBOX[2]-BBOX[0])
    lats = BBOX[3] - (np.arange(HM_H)+0.5)/HM_H * (BBOX[3]-BBOX[1])
    for j, lat in enumerate(lats):
        tx, ty = lonlat_to_tilexy(lons, lat, DEM_Z)
        px = np.clip(((tx - tx0) * 256).astype(int), 0, mw-1)
        py = min(max(int((ty - ty0) * 256), 0), mh-1)
        out[j] = dem[py, px]
    out[out < -400] = 0.0
    out = np.maximum(out, 0.0)
    hmin, hmax = float(out.min()), float(out.max())
    print(f"    高程: {hmin:.0f}~{hmax:.0f}m")
    enc16 = (out / hmax * 65535).astype(np.uint16)
    rgb = np.zeros((HM_H, HM_W, 3), dtype=np.uint8)
    rgb[:,:,0] = (enc16 >> 8).astype(np.uint8)
    rgb[:,:,1] = (enc16 & 0xFF).astype(np.uint8)
    Image.fromarray(rgb, mode="RGB").save(OUT / "heightmap.png")
    (OUT / "terrain.json").write_text(json.dumps({
        "bbox": BBOX, "min": hmin, "max": hmax, "encoding": "rgb-split",
        "width": HM_W, "height": HM_H}, ensure_ascii=False, indent=2), encoding="utf-8")
    # relief
    gy, gx = np.gradient(out)
    slope = np.sqrt(gx**2 + gy**2)
    shade = np.clip(1.0 - slope/40.0, 0.35, 1.0)
    c = np.zeros((HM_H, HM_W, 3), dtype=np.float32)
    stops = [(0,(58,74,66)),(500,(96,92,64)),(1500,(120,100,72)),(3000,(110,104,96)),(5000,(150,148,142)),(9000,(215,215,212))]
    for i in range(len(stops)-1):
        h0,c0 = stops[i]; h1,c1 = stops[i+1]
        m = (out>=h0)&(out<h1)
        t = np.clip((out[m]-h0)/max(h1-h0,1),0,1)
        for k in range(3): c[:,:,k][m] = c0[k]+(c1[k]-c0[k])*t
    c *= shade[:,:,None]
    Image.fromarray((c*0.8).clip(0,255).astype(np.uint8)).save(OUT/"relief.jpg", quality=85)
    print(f"    heightmap {os.path.getsize(OUT/'heightmap.png')//1024}KB, relief {os.path.getsize(OUT/'relief.jpg')//1024}KB")

def bake_geo():
    print("[B] 水系/海岸线...")
    import glob
    pad = 3.0
    bb = (BBOX[0]-pad, BBOX[1]-pad, BBOX[2]+pad, BBOX[3]+pad)
    def clip_save(src, dst, keep=None):
        g = gpd.read_file(src, bbox=bb)
        if keep:
            g = g[[c for c in keep if c in g.columns]+["geometry"]]
        feats = json.loads(g.to_json())["features"]
        json.dump({"type":"FeatureCollection","features":feats}, open(dst,"w",encoding="utf-8"), ensure_ascii=False)
        print(f"    {Path(dst).name}: {len(feats)}")
    clip_save(glob.glob(str(RAW/"ne_coastline"/"*.shp"))[0], OUT/"geo"/"coastline.json")
    clip_save(glob.glob(str(RAW/"ne_rivers"/"*.shp"))[0], OUT/"geo"/"rivers.json", ["name","name_zh"])
    clip_save(glob.glob(str(RAW/"ne_lakes"/"*.shp"))[0], OUT/"geo"/"lakes.json", ["name"])

def bake_counties():
    print("[C] 县面三角化...")
    gdf = gpd.read_file(RAW / "china_counties.geojson")
    gdf = gdf.set_crs("EPSG:4326", allow_override=True)
    gdf["geometry"] = gdf.geometry.apply(lambda g: g.buffer(0) if not g.is_valid else g)
    gdf["geometry"] = gdf.geometry.simplify(SIMPLIFY_COUNTY, preserve_topology=True)
    gdf["county_idx"] = range(len(gdf))
    gdf["cx"] = gdf.geometry.centroid.x
    gdf["cy"] = gdf.geometry.centroid.y
    lines, tri_list, vmap, vlist = [], [], {}, []
    for row in gdf.itertuples():
        geoms = [row.geometry] if row.geometry.geom_type == "Polygon" else list(row.geometry.geoms)
        for poly in geoms:
            rings = [np.array(poly.exterior.coords, dtype=np.float64)]
            if len(rings[0]) < 4: continue
            rings += [np.array(r.coords, dtype=np.float64) for r in poly.interiors]
            for r in rings: lines.append(r.tolist())
            flat = np.concatenate(rings)
            ring_end = np.cumsum([len(r) for r in rings]).astype(np.uint32)
            try:
                tris = earcut.triangulate_float64(flat.reshape(-1,2), ring_end)
            except Exception:
                continue
            for t in tris:
                pt = flat[t]
                key = (round(pt[0],6), round(pt[1],6), row.county_idx)
                if key not in vmap:
                    vmap[key] = len(vlist)
                    vlist.append((pt[0], pt[1], row.county_idx))
                tri_list.append(vmap[key])
    vlist = np.array(vlist, dtype=np.float32)
    tri_arr = np.array(tri_list, dtype=np.uint32)
    print(f"    顶点 {len(vlist)}, 三角形 {len(tri_arr)//3}")
    header = json.dumps({"count": len(vlist), "triangles": len(tri_arr)//3, "bbox": BBOX}).encode()
    with open(OUT/"counties.bin","wb") as f:
        f.write(struct.pack("<I", len(header))); f.write(header)
        f.write(vlist[:,:2].astype(np.float32).tobytes())
        f.write(vlist[:,2].astype(np.uint16).tobytes())
        f.write(tri_arr.tobytes())
    rounded = [[[round(x,3),round(y,3)] for x,y in ring] for ring in lines]
    json.dump(rounded, open(OUT/"county_lines.json","w",encoding="utf-8"), separators=(",",":"))
    gdf[["county_idx","name","adcode","cx","cy"]].to_json(OUT/"counties_meta.json", force_ascii=False, orient="records")
    print(f"    counties.bin {os.path.getsize(OUT/'counties.bin')//1048576}MB")
    return gdf

def replay(gdf):
    print("[D] 城池关联 + 事件回放...")
    cities = [dict(c) for c in CITIES]
    cg = gpd.GeoDataFrame(cities, geometry=[Point(c["location"][0],c["location"][1]) for c in cities], crs="EPSG:4326")
    j = gpd.sjoin(cg, gdf[["county_idx","name","geometry"]].rename(columns={"name":"county_name"}), predicate="within", how="left")
    failed = []
    for r in j.itertuples():
        idx_val = r.county_idx if pd.notna(r.county_idx) else -1
        for c in cities:
            if c["id"] == r.id:
                c["county_idx"] = int(idx_val)
                c["county_name"] = r.county_name if pd.notna(r.county_idx) else None
        if idx_val < 0: failed.append({"id": r.id})
    print(f"    关联失败: {failed if failed else '无'}")
    if failed: json.dump(failed, open(OUT/"failed_cities.json","w",encoding="utf-8"), ensure_ascii=False, indent=2)
    county_cities = defaultdict(list)
    for c in cities:
        if c["county_idx"] >= 0: county_cities[c["county_idx"]].append(c["id"])
    json.dump([{**f, "vassal_color": lighten(f["color"],VASSAL_LIGHTEN), "stroke": darken(f["color"],0.25)} for f in FACTIONS],
              open(OUT/"factions.json","w",encoding="utf-8"), ensure_ascii=False, indent=2)
    cents = gdf.geometry.centroid
    cx_arr, cy_arr = cents.x.values, cents.y.values
    def county_state(cs):
        st = {}
        for idx in range(len(gdf)):
            ids = county_cities.get(idx, [])
            st[idx] = max((cs[i] for i in ids), key=lambda c: TIER_PRIORITY[c["tier"]])["owner"] if ids else "neutral"
        cps = [(c["location"][0],c["location"][1],c["owner"]) for c in cs.values() if c["county_idx"]>=0]
        for idx in range(len(gdf)):
            if st[idx] != "neutral": continue
            best, bd = None, NEUTRAL_FILL_MAX_DIST
            for x,y,o in cps:
                d = math.hypot(cx_arr[idx]-x, cy_arr[idx]-y)
                if d < bd: bd, best = d, o
            if best: st[idx] = best
        return st
    def boundaries_for(st, key_fn=None):
        g = gdf.copy()
        g["owner"] = [st[i] for i in range(len(gdf))]
        g = g[g["owner"] != "neutral"]
        g["grp"] = [key_fn(o) if key_fn else o for o in g["owner"]]
        dis = g.dissolve(by="grp", as_index=False)
        out = {}
        for row in dis.itertuples():
            geo = drop_fragments(smooth_geom(row.geometry))
            rings = []
            polys = [geo] if geo.geom_type == "Polygon" else list(geo.geoms)
            for p in polys:
                rings.append([[round(x,4),round(y,4)] for x,y in p.exterior.coords])
            out[row.grp] = rings
        return out
    def dump_boundaries(st, path):
        json.dump({"owner": boundaries_for(st), "bloc": boundaries_for(st, key_fn=lambda o: vassal.get(o,o))},
                  open(path,"w",encoding="utf-8"), separators=(",",":"))
    city_state = {c["id"]: dict(c) for c in cities}
    vassal, fallen, capitals = {}, set(), {f["id"]: None for f in FACTIONS}
    for c in cities:
        if c["tier"] == 1 and capitals.get(c["owner"]) is None:
            capitals[c["owner"]] = c["id"]
    st0 = county_state(city_state)
    timeline = {"initial": {"year": EVENTS[0]["year"], "capitals": dict(capitals),
        "states": [{"county_idx":i,"owner":o,"vassal_of":vassal.get(o)} for i,o in st0.items() if o!="neutral"]},
        "events": []}
    dump_boundaries(st0, OUT/"boundaries"/"initial.json")
    print(f"    初始: {len([1 for o in st0.values() if o!='neutral'])} 县有主")
    prev = st0
    for ev in sorted(EVENTS, key=lambda e: e["seq"]):
        vassals_set, vassals_clear, capital_moves = [], [], []
        changed = []
        for oc in ev.get("outcomes", []):
            t = oc["type"]
            if t == "occupy": changed.append((oc["city"], oc["to"]))
            elif t == "conquer":
                for c in city_state.values():
                    if c["owner"] == oc["faction"]: changed.append((c["id"], oc["by"]))
                fallen.add(oc["faction"]); vassal.pop(oc["faction"], None)
            elif t == "submit":
                for c in city_state.values():
                    if c["owner"] == oc["faction"]: changed.append((c["id"], oc["to"]))
            elif t == "rebel":
                for cid in oc.get("cities", []): changed.append((cid, oc["to"]))
            elif t == "ally":
                for m in oc.get("members", []):
                    vassal[m] = oc["leader"]; vassals_set.append({"faction":m,"suzerain":oc["leader"]})
            elif t == "ally_break":
                for m in oc.get("members", []):
                    vassal.pop(m, None); vassals_clear.append(m)
            elif t == "move_capital":
                capitals[oc["faction"]] = oc["to"]
                capital_moves.append({"faction":oc["faction"],"from":oc["from"],"to":oc["to"]})
        for cid, o in changed:
            if cid in city_state: city_state[cid]["owner"] = o
        new_st = county_state(city_state)
        delta = [{"county_idx":i,"owner":new_st[i],"vassal_of":vassal.get(new_st[i])}
                 for i in range(len(gdf)) if new_st[i]!=prev.get(i)]
        # 附庸关系变化但未易主的县也要写入（ally / ally_break）
        changed_idx_set = {d["county_idx"] for d in delta}
        for vs in vassals_set:
            for i in range(len(gdf)):
                if new_st[i]==vs["faction"] and i not in changed_idx_set:
                    delta.append({"county_idx":i,"owner":vs["faction"],"vassal_of":vs["suzerain"]})
        for vc in vassals_clear:
            for i in range(len(gdf)):
                if new_st[i]==vc and i not in changed_idx_set:
                    delta.append({"county_idx":i,"owner":vc,"vassal_of":None})
        dump_boundaries(new_st, OUT/"boundaries"/f"{ev['id']}.json")
        timeline["events"].append({
            "id":ev["id"],"seq":ev["seq"],"year":ev["year"],"yearLabel":ev["yearLabel"],
            "title":ev["title"],"type":ev["type"],"category":ev.get("category"),
            "summary":ev.get("summary"),"quote":ev.get("quote"),"actors":ev.get("actors"),
            "routes":ev.get("routes",[]),"battle":ev.get("battle"),"camera":ev.get("camera"),
            "outcomes":ev.get("outcomes",[]),"changes":delta,"fallen":sorted(fallen),
            "vassals_set":vassals_set,"vassals_clear":vassals_clear,
            "capital_moves":capital_moves,"capitals":dict(capitals)})
        print(f"    {ev['yearLabel']} {ev['title']}: Δ{len(delta)}县")
        prev = new_st
    json.dump(timeline, open(OUT/"timeline.json","w",encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(cities, open(OUT/"cities.json","w",encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"    timeline 完成, {len(timeline['events'])} 事件")

def main():
    (OUT/"boundaries").mkdir(parents=True, exist_ok=True)
    (OUT/"geo").mkdir(parents=True, exist_ok=True)
    bake_heightmap()
    bake_geo()
    gdf = bake_counties()
    replay(gdf)
    print("\n✅ 完成 →", OUT)

if __name__ == "__main__":
    main()
