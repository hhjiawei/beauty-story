## 一、`10m_physical` vs `10m_cultural` 的区别

| 文件夹 | 内容 | 对你有什么用 |
|--------|------|-------------|
| **`10m_physical`** | **自然地理** — 海岸线、陆地、海洋、河流、湖泊、冰川、海底地形、山脉等 | **核心素材**。你要的河流、海洋、湖泊全在这里 |
| **`10m_cultural`** | **人文地理** — 国家边界、省界、城市、道路、铁路、机场、人口聚居区等 | 做历史地图**基本不用**。除非你要画现代省界或城市点位 |

**对你有用的 `10m_physical` 具体文件：**

| 文件名 | 内容 | 古风地图用途 |
|--------|------|-------------|
| `ne_10m_coastline.shp` | 海岸线（线） | 画海陆边界 |
| `ne_10m_ocean.shp` | 海洋面（多边形） | 填充海洋底色 |
| `ne_10m_lakes.shp` | 湖泊面（多边形） | 鄱阳湖、洞庭湖、太湖等 |
| `ne_10m_rivers_lake_centerlines.shp` | 河流中心线（线） | **黄河、长江、淮河**等 |
| `ne_10m_land.shp` | 陆地轮廓（多边形） | 精确裁剪海陆边界（比你之前用的 `land_scale_rank` 更精细） |

---

## 二、怎么把河流/海洋加进你的地图？

**推荐方案：前端叠加 GeoJSON**，不用重新跑瓦片工厂。

思路：
1. 用 Python 读取 Natural Earth 的 shapefile
2. 裁剪到**中国区域**（或你的河南区域）
3. 转成 GeoJSON 文件
4. 在 `henan_3d.html` 里直接加载这些 GeoJSON，叠加在 3D 地形上

**为什么不用后端画进瓦片？**
- 河流海洋是**平面**的，不需要参与 3D 地形计算
- 前端叠加可以**独立控制颜色、宽度**，随时调整古风配色
- 不用重新跑几小时的 `pipline_henan.py`

---

## 三、数据预处理代码

把这段保存为 `prepare_ne_data.py`，运行一次即可：

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
预处理 Natural Earth 数据：裁剪中国区域，转 GeoJSON
"""

import os
import geopandas as gpd
from shapely.geometry import box

# ==================== 配置 ====================
NE_PHYSICAL_DIR = r"D:\Natural_Earth_quick_start\packages\Natural_Earth_quick_start\10m_physical"
OUTPUT_DIR = "geojson"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 中国大致边界（含周边海洋，确保海岸线完整）
CHINA_BOUNDS = (105, 18, 125, 42)  # minx, miny, maxx, maxy

# 古风配色（供前端参考）
COLORS = {
    "ocean": "#8ba89a",      # 古水青灰
    "lake": "#9bb8aa",       # 湖泊略浅
    "river": "#7a9a8a",      # 河流青灰
    "coastline": "#5a7a6a",  # 海岸线深青
}

# ==================== 裁剪函数 ====================
def clip_to_china(gdf, bounds=CHINA_BOUNDS):
    """用矩形裁剪数据"""
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
    gdf = gdf[gdf.geometry.area > 0.05]  # 粗略过滤
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
        # 保留有名的大河，或长度属性大的
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
```

运行后生成：
```
geojson/
├── ocean.json      # 海洋面
├── lakes.json      # 湖泊面
├── rivers.json     # 河流线
└── coastline.json  # 海岸线
```

---

## 四、前端 HTML 修改

在 `henan_3d.html`（或 `start_henan_fix.py` 生成的 HTML）的 `map.on('load', ...)` 里，**在 `initLandmarks()` 之前**添加：

```javascript
// ==================== 加载自然地理要素 ====================
function initNaturalFeatures() {
  // 1. 海洋（填充面）
  map.addSource('ocean', {
    type: 'geojson',
    data: 'http://localhost:8000/geojson/ocean.json'
  });
  map.addLayer({
    id: 'ocean-fill',
    type: 'fill',
    source: 'ocean',
    paint: {
      'fill-color': '#8ba89a',      // 古水青灰
      'fill-opacity': 0.85
    }
  });

  // 2. 湖泊（填充面）
  map.addSource('lakes', {
    type: 'geojson',
    data: 'http://localhost:8000/geojson/lakes.json'
  });
  map.addLayer({
    id: 'lakes-fill',
    type: 'fill',
    source: 'lakes',
    paint: {
      'fill-color': '#9bb8aa',      // 比海洋略浅
      'fill-opacity': 0.8
    }
  });

  // 3. 河流（线）
  map.addSource('rivers', {
    type: 'geojson',
    data: 'http://localhost:8000/geojson/rivers.json'
  });
  map.addLayer({
    id: 'rivers-line',
    type: 'line',
    source: 'rivers',
    paint: {
      'line-color': '#7a9a8a',      // 河流青灰
      'line-width': [
        'interpolate', ['linear'], ['zoom'],
        4, 0.5,
        6, 1,
        8, 1.5,
        10, 2.5,
        12, 4
      ],
      'line-opacity': 0.9
    }
  });

  // 4. 海岸线（粗线，勾勒海陆边界）
  map.addSource('coastline', {
    type: 'geojson',
    data: 'http://localhost:8000/geojson/coastline.json'
  });
  map.addLayer({
    id: 'coastline-line',
    type: 'line',
    source: 'coastline',
    paint: {
      'line-color': '#5a7a6a',      // 深青
      'line-width': 2,
      'line-opacity': 0.8
    }
  });
}
```

然后在 `map.on('load', ...)` 里调用：
```javascript
map.on('load', () => {
  document.getElementById('loading').classList.add('hidden');
  checkDEMAndFallback();
  initNaturalFeatures();  // ← 加这一行
  initLandmarks();
  // ...
});
```

---

## 五、效果预览

加上之后，你的地图会有：
- **海洋**：古水青灰色，替代原来单调的「陆地延伸」
- **黄河/长江**：青灰色线条蜿蜒穿过平原，历史感拉满
- **湖泊**：鄱阳湖、洞庭湖等显示为水面色块
- **海岸线**：清晰的深青色边界，让地图有「版图」感

**注意：** 因为你在河南 Demo 里把 bounds 锁死了 `(110, 31, 117, 37)`，**海洋可能看不到**（河南不靠海）。如果你想看完整效果，建议把 bounds 放宽到 `(105, 18, 125, 42)`，或者单独做一个**全国版**古风地图。

---

## 六、如果你要做全国版

直接把 `pipline_henan.py` 里的 `BOUNDS` 改成：
```python
BOUNDS = (105.0, 42.0, 125.0, 18.0)  # 中国全图
```
zoom 保持 8~10，然后运行 `prepare_ne_data.py`（已经是中国范围），海洋、河流、湖泊都会完整显示。

但全国版瓦片数量会多很多（z=10 可能几千张），建议先确认河南版跑通了再扩区。