#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""山河战图 · 数据校验脚本（仅标准库）
用法：python tools/validate_data.py
存在错误时以非零码退出；坐标超出瓦片核心区给警告。
"""
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")

WORLD_BOUNDS = (107.5, 30.5, 119.5, 38.5)  # w, s, e, n
TILE_BOUNDS = (73.0, 17.0, 135.0, 54.0)    # 全国瓦片覆盖（china_relief/china_dem z0–z7）

TYPE_META = {
    "march": "国际", "battle": "国际", "occupy": "国际", "conquer": "国际",
    "ally": "国际", "rebel": "国际", "submit": "国际",
    "move_capital": "国内", "succeed": "国内", "proclaim": "国内", "other": "国内",
}
OUTCOME_REQUIRED = {
    "occupy": ["city", "to"], "conquer": ["faction", "by"], "submit": ["faction", "to"],
    "ally": ["leader", "members"], "rebel": ["faction", "to"], "ally_break": ["leader"],
    "move_capital": ["faction", "from", "to"], "ruler_change": ["faction", "ruler"],
    "proclaim": ["faction"],
}
OUTCOME_FACTION_KEYS = {
    "occupy": ["to"], "conquer": ["faction", "by"], "submit": ["faction", "to"],
    "rebel": ["faction", "to"], "ally": ["leader"], "ally_break": ["leader"],
    "move_capital": ["faction"], "ruler_change": ["faction"], "proclaim": ["faction"],
}
OUTCOME_CITY_KEYS = {"occupy": ["city"], "move_capital": ["from", "to"]}


def load(name):
    with open(os.path.join(DATA, name), encoding="utf-8") as f:
        return json.load(f)


def in_bounds(p, b):
    return isinstance(p, list) and len(p) == 2 and b[0] <= p[0] <= b[2] and b[1] <= p[1] <= b[3]


def main():
    errors, warns = [], []
    try:
        factions = load("factions.json")
        cities = load("cities.json")
        events = load("events.json")["events"]
    except Exception as e:
        print(f"❌ JSON 解析失败: {e}")
        sys.exit(1)

    fids = {f["id"] for f in factions}
    cids = {c["id"] for c in cities}
    if len(fids) != len(factions):
        errors.append("factions.json: id 重复")
    if len(cids) != len(cities):
        errors.append("cities.json: id 重复")

    for c in cities:
        if not in_bounds(c["location"], WORLD_BOUNDS):
            errors.append(f"cities.json: {c['id']} 坐标超出 worldBounds")
        elif not in_bounds(c["location"], TILE_BOUNDS):
            warns.append(f"cities.json: {c['id']} 在瓦片核心区之外（以旧纸背景承接）")
        if c.get("owner") is not None and c["owner"] not in fids:
            errors.append(f"cities.json: {c['id']} owner \"{c['owner']}\" 不存在")

    seqs, last_year = set(), None
    for ev in events:
        pre = f"events.json[{ev.get('id', '?')}]"
        for k in ["id", "seq", "year", "yearLabel", "title", "category", "type"]:
            if k not in ev:
                errors.append(f"{pre}: 缺字段 {k}")
        if ev.get("seq") in seqs:
            errors.append(f"{pre}: seq {ev.get('seq')} 重复")
        seqs.add(ev.get("seq"))
        if last_year is not None and ev.get("year", 0) < last_year:
            warns.append(f"{pre}: 年份 {ev.get('year')} 早于前一事件（以 seq 定序）")
        last_year = ev.get("year", last_year)

        t = ev.get("type")
        if t not in TYPE_META:
            errors.append(f"{pre}: 未知 type \"{t}\"")
            continue
        if ev.get("category") != TYPE_META[t]:
            errors.append(f"{pre}: type {t} 与 category {ev.get('category')} 归类不一致")

        if t == "battle":
            if not ev.get("battle") or not in_bounds(ev["battle"].get("location"), WORLD_BOUNDS):
                errors.append(f"{pre}: battle 缺 battle.location 或越界")
            if len(ev.get("routes", [])) < 2:
                errors.append(f"{pre}: battle 需 ≥2 条 routes")

        for r in ev.get("routes", []):
            if r.get("faction") not in fids:
                errors.append(f"{pre}: route.faction \"{r.get('faction')}\" 不存在")
            if r.get("from") not in cids:
                errors.append(f"{pre}: route.from \"{r.get('from')}\" 不存在")
            if r.get("toCity") and r["toCity"] not in cids:
                errors.append(f"{pre}: route.toCity \"{r.get('toCity')}\" 不存在")
            if not r.get("toCity") and not in_bounds(r.get("toPoint"), WORLD_BOUNDS):
                errors.append(f"{pre}: route 终点缺失或越界")

        for oc in ev.get("outcomes", []):
            ot = oc.get("type")
            if ot not in OUTCOME_REQUIRED:
                errors.append(f"{pre}: 未知 outcome \"{ot}\"")
                continue
            for k in OUTCOME_REQUIRED[ot]:
                if k not in oc:
                    errors.append(f"{pre}: outcome {ot} 缺字段 {k}")
            for k in OUTCOME_FACTION_KEYS.get(ot, []):
                if k in oc and oc[k] not in fids:
                    errors.append(f"{pre}: outcome 引用势力 \"{oc[k]}\" 不存在")
            for k in OUTCOME_CITY_KEYS.get(ot, []):
                if k in oc and oc[k] not in cids:
                    errors.append(f"{pre}: outcome 引用城市 \"{oc[k]}\" 不存在")
            if ot == "ally":
                for m in oc.get("members", []):
                    if m not in fids:
                        errors.append(f"{pre}: ally 成员 \"{m}\" 不存在")
            if ot == "rebel":
                for cid in oc.get("cities", []):
                    if cid not in cids:
                        errors.append(f"{pre}: rebel 城市 \"{cid}\" 不存在")

    print("=" * 56)
    print(f"事件 {len(events)} 件 · 城市 {len(cities)} 座 · 势力 {len(factions)} 支")
    print("=" * 56)
    for w in warns:
        print(f"  ⚠️  {w}")
    if errors:
        for e in errors:
            print(f"  ❌ {e}")
        print(f"\n校验未通过：{len(errors)} 个错误，{len(warns)} 个警告")
        sys.exit(1)
    print(f"✅ 0 错误，{len(warns)} 个警告，校验通过")


if __name__ == "__main__":
    main()
