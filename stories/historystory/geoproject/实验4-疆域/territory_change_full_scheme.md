# 疆域变化动态渲染：融合 geoBoundaries ADM3 完整技术实行方案

## 一、总体架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              数据输入层                                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────────────────┐ │
│  │ city.json   │  │ events.json │  │ geoBoundaries CHN ADM3              │ │
│  │ 城池控制点   │  │ 战争事件序列 │  │ 县级面数据 (~2800个 Polygon)         │ │
│  │ (lat/lon)   │  │ (year排序)  │  │ WGS84 / EPSG:4326                   │ │
│  └──────┬──────┘  └──────┬──────┘  └──────────────┬──────────────────────┘ │
│         │                  │                        │                        │
│         └──────────────────┼────────────────────────┘                        │
│                            ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    疆域生成引擎（Python Pipeline）                    │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐   │   │
│  │  │ 空间关联      │  │ 时间断面计算  │  │ 国家疆域面生成            │   │   │
│  │  │ (sjoin)      │  │ (事件驱动)   │  │ (Dissolve + 属性赋值)      │   │   │
│  │  │ 点→面映射     │  │ 归属状态更新  │  │ 输出 GeoJSON              │   │   │
│  │  └──────┬───────┘  └──────┬───────┘  └───────────┬──────────────┘   │   │
│  │         │                 │                      │                    │   │
│  │         └─────────────────┼──────────────────────┘                    │   │
│  │                           ▼                                            │   │
│  │              ┌─────────────────────────────┐                            │   │
│  │              │  time_slice_YYYY.geojson    │                            │   │
│  │              │  (每个时间断面一个文件)       │                            │   │
│  │              └─────────────────────────────┘                            │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                            │                                               │
│                            ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    前端渲染层（MapLibre GL JS）                        │   │
│  │  本地瓦片底图 + GeoJSON Fill 层(疆域面) + Line 层(行军) + Circle(城池) │   │
│  │  时间轴控制器：同步切换疆域面 + 行军路线                              │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 二、核心数据规范

### 2.1 city.json —— 城池控制点 Master 表

```json
{
  "cities": [
    {
      "id": "city_001",
      "ancient_name": "安邑",
      "modern_name": "山西省运城市夏县",
      "lat": 35.1416,
      "lon": 111.2203,
      "period": "战国",
      "type": "都城",
      "initial_owner": "魏国",
      "confidence": "high",
      "note": "魏国早期都城"
    },
    {
      "id": "city_002",
      "ancient_name": "咸阳",
      "modern_name": "陕西省咸阳市",
      "lat": 34.3296,
      "lon": 108.7089,
      "period": "战国",
      "type": "都城",
      "initial_owner": "秦国",
      "confidence": "high"
    }
  ]
}
```

**关键字段说明**：
- `lat/lon`：WGS84 坐标，用于空间关联到县级面
- `type`：`都城/郡治/县治/关隘/要塞` —— 决定一县多城时的归属优先级
- `initial_owner`：该时期起始归属国家
- `confidence`：`high` 正常渲染，`medium` 半透明，`low` 虚线边框

### 2.2 events.json —— 战争事件序列（单一事实来源）

```json
{
  "events": [
    {
      "id": "evt_001",
      "year": -354,
      "title": "安邑之战",
      "changes": [
        {
          "city_id": "city_001",
          "from": "魏国",
          "to": "秦国",
          "type": "占领"
        }
      ]
    },
    {
      "id": "evt_002",
      "year": -293,
      "title": "伊阙之战",
      "changes": [
        {"city_id": "city_003", "from": "韩国", "to": "秦国", "type": "占领"},
        {"city_id": "city_004", "from": "魏国", "to": "秦国", "type": "占领"}
      ]
    }
  ]
}
```

**设计原则**：
- 一个事件可改变多个城池归属
- `year` 用于排序，支持同一年多个事件
- 只记录「有史可考」的城池得失，不推测
- **行军系统与疆域系统共用此文件**作为事件源

### 2.3 color_map.json —— 国家配色方案

```json
{
  "colors": {
    "秦国": {"fill": "#1a5276", "stroke": "#154360", "fill_opacity": 0.65},
    "魏国": {"fill": "#7b241c", "stroke": "#641e16", "fill_opacity": 0.65},
    "赵国": {"fill": "#1e8449", "stroke": "#196f3d", "fill_opacity": 0.65},
    "韩国": {"fill": "#9a7d0a", "stroke": "#7d6608", "fill_opacity": 0.65},
    "楚国": {"fill": "#6c3483", "stroke": "#5b2c6f", "fill_opacity": 0.65},
    "齐国": {"fill": "#a04000", "stroke": "#873600", "fill_opacity": 0.65},
    "燕国": {"fill": "#5d6d7e", "stroke": "#4a5a6b", "fill_opacity": 0.65},
    "neutral": {"fill": "#888888", "stroke": "#666666", "fill_opacity": 0.15}
  }
}
```

### 2.4 time_slice_YYYY.geojson —— 输出文件（每个时间断面一个）

```json
{
  "type": "FeatureCollection",
  "metadata": {
    "year": -354,
    "event_triggered": "evt_001",
    "period": "战国",
    "total_counties": 2843,
    "controlled_counties": 156
  },
  "features": [
    {
      "type": "Feature",
      "properties": {
        "country": "秦国",
        "color": "#1a5276",
        "stroke_color": "#154360",
        "stroke_width": 1.5,
        "county_count": 42,
        "fill_opacity": 0.65
      },
      "geometry": {
        "type": "MultiPolygon",
        "coordinates": [[[[...], [...], [...], [...]]]]
      }
    },
    {
      "type": "Feature",
      "properties": {
        "country": "neutral",
        "color": "#888888",
        "stroke_color": "#666666",
        "stroke_width": 0.5,
        "county_count": 2763,
        "fill_opacity": 0.15
      },
      "geometry": {...}
    }
  ]
}
```

---

## 三、技术选型

| 层级 | 工具/库 | 用途 | 状态 |
|------|---------|------|------|
| **数据下载** | `requests` + `zipfile` | 下载 geoBoundaries ZIP 并解压 | 标准库 |
| **矢量处理** | `GeoPandas` | Shapefile/GeoJSON 读写、空间关联、Dissolve | 已有 |
| **几何计算** | `Shapely` | Point/Polygon 操作、空间判断 | 已有 |
| **空间关联** | `GeoPandas.sjoin()` | 城池点 → 县级面关联（核心） | 已有 |
| **面合并** | `GeoPandas.dissolve()` | 同国家县级面合并为国家疆域 | 已有 |
| **输出格式** | `GeoPandas` → GeoJSON | 时间断面文件 | 已有 |
| **前端渲染** | `MapLibre GL JS` | Fill 层渲染 + 时间轴切换 | 已有 |
| **底图服务** | `python -m http.server` + 本地瓦片 | 底图提供 | 已有 |

**无新增依赖**，全部基于现有工具链。

---

## 四、五阶段执行 Pipeline

### 阶段 0：数据预处理（一次性执行）

**目标**：下载 geoBoundaries 数据，加载为 GeoDataFrame，建立县级面索引。

**输入**：geoBoundaries CHN ADM3 ZIP 文件
**输出**：`china_adm3.geojson`（标准化后的县级面数据）

**步骤**：
1. 下载 ZIP 并解压
2. 读取 Shapefile 为 GeoDataFrame
3. 确认坐标系为 EPSG:4326（WGS84），如不是则转换
4. 保留核心字段：`geometry`（必须）、`shapeName`（参考）、`shapeID`（唯一标识）
5. 添加 `county_idx` 列（整数索引，0~N-1，用于后续快速查找）
6. 保存为 `china_adm3.geojson`

**伪代码**：
```python
import geopandas as gpd

# 读取 geoBoundaries ADM3
counties = gpd.read_file('china_adm3.shp')

# 确保坐标系
if counties.crs != 'EPSG:4326':
    counties = counties.to_crs('EPSG:4326')

# 建立整数索引
counties['county_idx'] = range(len(counties))

# 保存
counties[['county_idx', 'shapeName', 'geometry']].to_file(
    'data/china_adm3.geojson', driver='GeoJSON'
)
```

---

### 阶段 1：空间关联（一次性执行）

**目标**：将 city.json 中的每个城池点，通过空间关联（`sjoin`）映射到对应的县级面。

**核心洞察**：**不需要名称映射**。城池有 `lat/lon`，县级面有 `geometry`，直接用 `GeoPandas.sjoin(predicate='within')` 即可判断「这个点落在哪个面里」。

**输入**：`city.json` + `china_adm3.geojson`
**输出**：`county_city_map.json`（县 → 城池列表映射）+ `city.json`（补充 `county_idx` 字段）

**步骤**：
1. 读取 `city.json`，提取 `lat/lon`，创建 `GeoDataFrame`（`geometry = Point(lon, lat)`）
2. 读取 `china_adm3.geojson`
3. 执行空间关联：`sjoin(cities_gdf, counties_gdf, predicate='within', how='left')`
4. 结果中 `index_right` 即为城池所属的县级面索引
5. 处理关联失败的城池（坐标错误、境外城池等）：
   - 标记为 `county_idx = -1`
   - 输出警告列表，人工修正
6. 建立反向映射：`county_idx → [city_id_1, city_id_2, ...]`
7. 保存关联关系到 `county_city_map.json`

**伪代码**：
```python
from shapely.geometry import Point
from collections import defaultdict

# 1. 城池转 GeoDataFrame
cities = load_json('data/city.json')
cities_gdf = gpd.GeoDataFrame(
    cities['cities'],
    geometry=[Point(c['lon'], c['lat']) for c in cities['cities']],
    crs='EPSG:4326'
)

# 2. 读取县级面
counties = gpd.read_file('data/china_adm3.geojson')

# 3. 空间关联
joined = gpd.sjoin(cities_gdf, counties, predicate='within', how='left')

# 4. 提取关联结果
for idx, row in joined.iterrows():
    city_id = row['id']
    county_idx = row['county_idx']  # 可能为 NaN
    if pd.isna(county_idx):
        print(f'警告：城池 {city_id} 未关联到任何县级面')
        county_idx = -1
    update_city(city_id, 'county_idx', int(county_idx))

# 5. 建立反向映射
county_to_cities = defaultdict(list)
for city in cities['cities']:
    if city['county_idx'] >= 0:
        county_to_cities[city['county_idx']].append(city['id'])

save_json('data/county_city_map.json', dict(county_to_cities))
```

**关键说明**：
- 空间关联只做一次，后续所有时间断面复用此映射
- 如果某县包含多个城池，映射中会记录所有 `city_id`
- 关联失败的城池（`county_idx = -1`）不纳入疆域计算，但仍在地图上以点形式显示

---

### 阶段 2：时间断面生成（批量执行）

**目标**：按时间顺序遍历事件，每个事件后生成一个疆域面 GeoJSON。

**输入**：`city.json`（含 `county_idx`）+ `events.json` + `county_city_map.json` + `color_map.json`
**输出**：`time_slice_*.geojson`（每个事件后一个文件）

**核心算法**：

```
初始化：
  每个城池 owner = initial_owner
  每个县级面 owner = resolve_owner(该面内所有城池)
  生成 time_slice_initial.geojson

遍历 events（按 year 排序）：
  事件触发 → 更新受影响城池的 owner
         → 重新计算受影响县级面的 owner
         → 按国家 dissolve 所有县级面
         → 输出 time_slice_{year}.geojson
```

**归属优先级规则**（一县多城冲突解决）：

| 优先级 | 城池类型 | 权重 | 说明 |
|--------|---------|------|------|
| 1 | 都城 | 最高 | 一国之都，必然代表该国控制 |
| 2 | 郡治 | 高 | 郡级行政中心 |
| 3 | 县治 | 中 | 县级行政中心 |
| 4 | 关隘 | 低 | 军事据点，可能被占领但行政归属不变 |
| 5 | 要塞 | 最低 | 临时军事设施 |

**同优先级冲突**：以**最新事件**为准。`cities_state` 中记录 `last_event_time`，时间戳最新者决定归属。

**伪代码**：
```python
# 优先级定义
PRIORITY = {'都城': 4, '郡治': 3, '县治': 2, '关隘': 1, '要塞': 0}

def resolve_county_owner(city_ids, cities_state):
    cities_in_county = [cities_state[cid] for cid in city_ids if cid in cities_state]
    if not cities_in_county:
        return 'neutral'
    
    # 按优先级降序，同优先级按 last_event_time 降序（最新优先）
    cities_in_county.sort(
        key=lambda c: (PRIORITY.get(c['type'], 0), c.get('last_event_time', 0)),
        reverse=True
    )
    return cities_in_county[0]['owner']

# ─────────────────────────────────────────────
# 主流程
# ─────────────────────────────────────────────

# 加载数据
cities_data = load_json('data/city.json')
county_map = load_json('data/county_city_map.json')
counties_gdf = gpd.read_file('data/china_adm3.geojson')
color_map = load_json('data/color_map.json')
events = sorted(load_json('data/events.json')['events'], key=lambda e: e['year'])

# 初始化城池状态
cities_state = {}
for city in cities_data['cities']:
    cities_state[city['id']] = {
        **city,
        'owner': city['initial_owner'],
        'last_event_time': float('-inf')
    }

# 初始化县级面归属
counties_state = {}
for county_idx, city_ids in county_map.items():
    counties_state[int(county_idx)] = resolve_county_owner(city_ids, cities_state)

# 标记无城池的县为 neutral
for idx in range(len(counties_gdf)):
    if idx not in counties_state:
        counties_state[idx] = 'neutral'

# 生成初始断面
generate_time_slice(counties_gdf, counties_state, color_map, 'output/time_slice_initial.geojson')

# 遍历事件
for event in events:
    affected_counties = set()
    
    # 更新城池归属
    for change in event['changes']:
        cid = change['city_id']
        cities_state[cid]['owner'] = change['to']
        cities_state[cid]['last_event_time'] = event['year']
        
        county_idx = cities_state[cid]['county_idx']
        if county_idx >= 0:
            affected_counties.add(county_idx)
    
    # 重新计算受影响县的归属
    for county_idx in affected_counties:
        city_ids = county_map.get(str(county_idx), [])
        counties_state[county_idx] = resolve_county_owner(city_ids, cities_state)
    
    # 生成该时间断面
    year_str = str(event['year']).replace('-', 'BC')
    generate_time_slice(
        counties_gdf, counties_state, color_map,
        f'output/time_slice_{year_str}.geojson',
        metadata={'year': event['year'], 'event': event['id'], 'title': event['title']}
    )
```

**`generate_time_slice` 函数伪代码**：
```python
def generate_time_slice(counties_gdf, counties_state, color_map, output_path, metadata=None):
    # 1. 为县级面添加 owner 列
    gdf = counties_gdf.copy()
    gdf['owner'] = gdf['county_idx'].map(lambda i: counties_state.get(i, 'neutral'))
    
    # 2. 按 owner dissolve（核心操作）
    dissolved = gdf.dissolve(by='owner', as_index=False)
    
    # 3. 添加可视化属性
    dissolved['country'] = dissolved['owner']
    dissolved['color'] = dissolved['owner'].map(
        lambda o: color_map['colors'].get(o, {}).get('fill', '#cccccc'))
    dissolved['stroke_color'] = dissolved['owner'].map(
        lambda o: color_map['colors'].get(o, {}).get('stroke', '#999999'))
    dissolved['stroke_width'] = dissolved['owner'].map(
        lambda o: 1.5 if o != 'neutral' else 0.5)
    dissolved['fill_opacity'] = dissolved['owner'].map(
        lambda o: color_map['colors'].get(o, {}).get('fill_opacity', 0.5))
    dissolved['county_count'] = dissolved['owner'].map(
        lambda o: sum(1 for v in counties_state.values() if v == o))
    
    # 4. 构建 FeatureCollection
    feature_collection = {
        'type': 'FeatureCollection',
        'metadata': metadata or {},
        'features': json.loads(dissolved[
            ['country', 'color', 'stroke_color', 'stroke_width', 'fill_opacity', 'county_count', 'geometry']
        ].to_json())['features']
    }
    
    # 5. 保存
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(feature_collection, f, ensure_ascii=False)
```

---

### 阶段 3：输出优化（可选）

**目标**：减少输出文件数量，优化前端加载性能。

**策略**：
1. **只输出有变化的时间断面**：如果某年没有事件，疆域状态与上一年相同，不重复生成文件
2. **增量索引**：生成 `slice_index.json`，记录每个时间断面文件对应的 year 和事件
3. **GeoJSON 压缩**：对输出文件进行简化（`GeoPandas.simplify(tolerance=0.001)`），减少顶点数，文件体积可缩小 50-70%

**伪代码**：
```python
# 简化几何（可选，如果文件太大）
gdf_simplified = gdf.copy()
gdf_simplified['geometry'] = gdf_simplified['geometry'].simplify(
    tolerance=0.001, preserve_topology=True)

# 生成索引
slice_index = []
for event in events:
    year_str = str(event['year']).replace('-', 'BC')
    slice_index.append({
        'year': event['year'],
        'event_id': event['id'],
        'file': f'time_slice_{year_str}.geojson',
        'title': event['title']
    })

save_json('output/slice_index.json', slice_index)
```

---

### 阶段 4：前端渲染（与现有系统整合）

**目标**：MapLibre 加载时间断面 GeoJSON，与行军路线、城池点联动。

**图层顺序**（从底到顶）：
1. **本地瓦片底图**（你已有的 `start_server_v2.py`）
2. **疆域 Fill 层**（`time_slice_*.geojson`，半透明着色）
3. **行军路线 Line 层**（你已有代码）
4. **城池点 Circle 层**（`city.json`，按类型区分大小）

**MapLibre 疆域层配置**：
```javascript
// 加载疆域数据源
map.addSource('territory', {
  type: 'geojson',
  data: '/data/time_slice_initial.geojson'
});

// 填充层
map.addLayer({
  id: 'territory-fill',
  type: 'fill',
  source: 'territory',
  paint: {
    'fill-color': ['get', 'color'],
    'fill-opacity': ['get', 'fill_opacity'],
    'fill-outline-color': ['get', 'stroke_color']
  }
});

// 边界线层（国家间边界）
map.addLayer({
  id: 'territory-border',
  type: 'line',
  source: 'territory',
  filter: ['!=', ['get', 'country'], 'neutral'],
  paint: {
    'line-color': ['get', 'stroke_color'],
    'line-width': ['get', 'stroke_width'],
    'line-opacity': 0.8
  }
});

// 时间轴切换函数
function switchTimeSlice(year) {
  const yearStr = year < 0 ? `BC${Math.abs(year)}` : `${year}`;
  const file = `/data/time_slice_${yearStr}.geojson`;
  map.getSource('territory').setData(file);
  // 同步更新行军路线（你已有逻辑）
  updateMarchingRoutes(year);
}
```

---

## 五、关键算法详解

### 5.1 空间关联：为什么比名称映射更可靠

**问题**：geoBoundaries 的县级面名称是英文/拼音（如 'Xia'），而你的 `city.json` 是中文（如 '夏县'）。

**传统方案**：做「中文 → 拼音」对照表，然后字符串匹配。

**问题**：
- 多音字问题（如 '长平' 是 Changping 还是 Zhangping？）
- 古今县名变更（如 '安邑县' 今已撤销，无法直接对应）
- 同音不同字（如 '夏县' vs '峡县'）

**我们的方案**：**空间关联（Spatial Join）**

```
city.json 中的 lat/lon  →  GeoPandas sjoin(predicate='within')  →  落在哪个县级面内
```

**优势**：
- 不依赖名称，完全基于地理位置
- 即使县名变更、撤销，只要城池坐标正确，就能关联到正确的现代地理单元
- 自动化，无需维护庞大的名称映射表

**局限与处理**：
- 坐标偏移：如果 `lat/lon` 有偏差，可能落入邻县 → 关联后人工抽查核心城池（都城、郡治）
- 境外城池：如箕子朝鲜的城池可能在现代朝鲜境内 → `sjoin` 返回空，标记为 `county_idx = -1`，不纳入疆域计算
- 边界点：城池恰好在两县边界上 → `sjoin` 可能随机分配，建议对边界城池手动校验

### 5.2 一县多城的冲突解决

**场景**：一个县级面内包含多个城池，且归属不同国家。

**示例**：某县内有魏国县治 + 秦国关隘，该算谁的？

**解决规则**：按优先级排序，同优先级以最新事件为准。详见阶段 2 的 `resolve_county_owner` 函数。

**示例**：
- 县内有魏国县治（初始 owner=魏，last_event=-500）
- 秦国占领关隘（owner=秦，last_event=-354）
- 优先级：县治(2) > 关隘(1)，所以该面归属魏国
- 如果秦国后来占领了县治（last_event=-300），则归属秦国

### 5.3 无人控制县的处理

**场景**：geoBoundaries 有 2800+ 个县级面，但你的 `city.json` 可能只覆盖几百个核心城池。大量县级面内没有任何城池点。

**方案**：标记为 `owner = 'neutral'`，渲染时：
- `fill_opacity` 极低（0.1-0.15）
- 颜色灰色（`#888888`）
- 不显示边界线（或极淡）

**效果**：
- 地图上大部分区域是浅灰色半透明
- 有城池的县显示为国家颜色
- 视觉上自然呈现「势力范围」——有控制点的区域着色，无人区留白

**进阶处理（可选）**：
如果你希望视觉上更「完整」（即所有县都有归属），可以对 neutral 县根据邻县颜色做「空间扩散」填充。但这属于**推测**，建议只在视频后期手动处理核心区域，不要自动化。

### 5.4 Dissolve 性能优化

**问题**：每次事件后都对 2800+ 个面做 `dissolve`，如果事件有 100 个，总时间可能数分钟。

**优化策略**：

| 优化点 | 方案 | 效果 |
|--------|------|------|
| **只处理有变化的县** | 事件只影响少数县，但 `dissolve` 需要全量。可缓存上一次的 dissolve 结果，只替换变化的部分 | 复杂，收益有限 |
| **几何简化** | 输出前对 MultiPolygon 做 `simplify(tolerance=0.001)` | 文件体积减少 50-70%，渲染更快 |
| **并行处理** | 不同战区的事件序列独立处理 | 先秦可按战区拆分 |
| **预计算** | 所有时间断面在视频制作前一次性生成，前端只加载 | 前端零计算负担 |

**实际评估**：
- GeoPandas dissolve 2800 个面 ≈ 1-3 秒（取决于硬件）
- 100 个事件 ≈ 3-5 分钟总生成时间
- 对视频制作来说完全可接受（预计算，不实时）

---

## 六、先秦 vs 秦以后：差异化策略

| 维度 | 先秦（夏商周春秋战国） | 秦以后（秦—清） |
|------|----------------------|----------------|
| **基础地理单元** | geoBoundaries 现代县级面 | CHGIS 历史府州/县级面 |
| **城池关联方式** | 空间关联到现代县级面 | CHGIS 面内通常包含历史城池坐标，直接关联 |
| **疆域生成** | 县级面按 owner dissolve | 直接用 CHGIS 府州面，或县级面 dissolve |
| **无人区处理** | 大量 neutral 县（浅灰） | CHGIS 面已覆盖历史疆域，neutral 较少 |
| **事件粒度** | 城池得失 → 县级面变色 | 府州得失 → 府州面变色（粒度更粗） |
| **数据准备** | 需自己整理 city.json + 空间关联 | 下载 CHGIS 时间断面数据即可 |
| **前端渲染** | 同一套 MapLibre Fill 层 | 同一套 |

**秦以后建议**：
- 下载 CHGIS V4/V6 的府州级时间序列数据
- 每个府州面有明确的起止年份和归属政权
- 你的 `events.json` 中的城池得失，映射到 CHGIS 府州面 → 局部修正颜色
- 如果 CHGIS 粒度够细（县级），可直接替代 geoBoundaries

---

## 七、与行军系统的衔接

| 衔接点 | 疆域系统 | 行军系统（你已有） |
|--------|---------|-------------------|
| **事件源** | `events.json`（城池得失） | `events.json`（行军路线） |
| **城池坐标** | `city.json`（lat/lon） | `city.json`（route 的 location） |
| **时间轴** | `year` 参数驱动疆域面切换 | `year` 参数驱动路线动画 |
| **底图** | 本地瓦片服务器 | 本地瓦片服务器 |
| **前端框架** | MapLibre Fill 层 | MapLibre Line 层 |

**统一时间轴控制器设计**：
```javascript
const timeController = {
  currentYear: -500,
  
  setYear(year) {
    this.currentYear = year;
    // 同步更新疆域面
    const file = `/data/time_slice_${year < 0 ? 'BC'+Math.abs(year) : year}.geojson`;
    map.getSource('territory').setData(file);
    
    // 同步更新行军路线（你已有逻辑）
    updateMarchingRoutes(year);
    
    // 同步更新城池点样式（高亮当前事件涉及的城池）
    highlightEventCities(year);
  }
};
```

---

## 八、项目目录结构

```
project/
├── data/                              # 数据文件（只读）
│   ├── raw/
│   │   └── geoBoundaries-CHN-ADM3-all.zip   # 原始下载
│   ├── city.json                      # 城池控制点（你维护）
│   ├── events.json                    # 战争事件（你维护，与行军共用）
│   ├── color_map.json                 # 国家配色（你维护）
│   ├── china_adm3.geojson             # 阶段0输出：标准化县级面
│   ├── county_city_map.json           # 阶段1输出：县→城池映射
│   └── chgis/                         # CHGIS 数据（秦以后）
│       └── qin_han/
│
├── pipeline/                          # 生成脚本
│   ├── 00_download_gb.py             # 阶段0：下载 geoBoundaries
│   ├── 01_build_county_map.py          # 阶段1：空间关联
│   ├── 02_generate_slices.py          # 阶段2：批量生成时间断面
│   ├── 03_optimize_output.py          # 阶段3：简化 + 索引（可选）
│   └── 04_merge_chgis.py             # 秦以后：CHGIS 处理（可选）
│
├── output/                            # 生成结果（写入）
│   ├── time_slice_initial.geojson
│   ├── time_slice_BC354.geojson
│   ├── time_slice_BC293.geojson
│   └── slice_index.json               # 时间索引
│
├── web/                               # 前端
│   ├── index.html
│   ├── maplibre/
│   ├── css/
│   └── data/ -> ../output/            # 软链接或复制
│
└── start_server_v2.py                 # 本地瓦片服务器（你已有）
```

---

## 九、性能与优化策略

| 场景 | 问题 | 解决方案 |
|------|------|---------|
| **空间关联阶段** | 2800 个面 × N 个城池，sjoin 可能慢 | 先对县级面做空间索引（GeoPandas 自动），通常秒级 |
| **Dissolve 阶段** | 每次事件全量 dissolve 2800 个面 | 预计算，不实时；100 个事件约 3-5 分钟，可接受 |
| **文件体积** | 每个 GeoJSON 可能 5-10 MB | `simplify(tolerance=0.001)` 可减少 50-70% |
| **前端加载** | 时间轴切换时加载新 GeoJSON 可能有延迟 | 预加载相邻 2-3 个断面到内存；或用 `setData` 而非重载图层 |
| **渲染性能** | 2800 个面合并后可能只剩 7-10 个国家面，MapLibre 无压力 | 无需优化 |
| **多战区并行** | 战国七雄分布广，全国 dissolve 包含大量 neutral 县 | 可按战区拆分生成，但最终展示时合并 |

---

## 十、下一步行动清单

### 本周（数据准备）
- [ ] **Day 1**：运行 `00_download_gb.py`，下载 geoBoundaries 中国 ADM3，验证数据完整性（`len(gdf)` 应 ≈ 2800+）
- [ ] **Day 1**：运行 `01_build_county_map.py`，空间关联你的 `city.json` 到县级面，检查关联失败列表
- [ ] **Day 2-3**：修正关联失败的城池坐标（核心都城/郡治必须关联成功）
- [ ] **Day 4**：整理 `events.json`，确保每个 `city_id` 都在 `city.json` 中存在，且 `year` 排序正确
- [ ] **Day 5**：设计 `color_map.json`，为每个国家分配历史感配色

### 下周（生成与验证）
- [ ] **Day 1**：运行 `02_generate_slices.py`，生成所有时间断面 GeoJSON
- [ ] **Day 2**：抽查 3-5 个时间断面，在 QGIS 中打开验证：
  - 国家面是否正确合并？
  - 边界是否自然蜿蜒？
  - neutral 县是否正确显示为浅灰？
- [ ] **Day 3**：运行 `03_optimize_output.py`（可选），简化几何、生成索引
- [ ] **Day 4**：在 MapLibre 中加载 `time_slice_initial.geojson`，验证 Fill 层渲染效果
- [ ] **Day 5**：实现时间轴切换，与行军路线联动测试

### 第三周（整合与调优）
- [ ] **Day 1-2**：前端时间轴 UI 设计（Slider + 事件标题显示）
- [ ] **Day 3**：调整 `fill_opacity` 和 `stroke_width`，确保疆域面与底图对比度合适
- [ ] **Day 4**：测试 10 个连续事件的切换流畅度
- [ ] **Day 5**：准备秦以后 CHGIS 数据，规划 `04_merge_chgis.py`

---

## 附录：常见问题预判

**Q：古代城池对应的现代县已经撤销/合并，怎么办？**
A：空间关联会自动找到该坐标当前所属的县级面。即使古代县名已消失，只要坐标准确，就会关联到正确的现代地理单元。如果坐标本身对应的是已撤销县，可能落入邻县，这是可接受的误差（你说过位置偏移无所谓）。

**Q：一个县内有多个城池，分别属于不同国家，dissolve 后该县只能有一个颜色，怎么体现？**
A：按 5.2 节的优先级规则，高优先级城池决定该县归属。视觉上该县是单一颜色，但你可以在城池点 Circle 层用不同颜色标注每个城池的实际归属，观众通过城池点颜色就能感知到「该县有争议」。

**Q：geoBoundaries 的县级面包含台湾，但我做先秦视频不涉及，需要处理吗？**
A：不需要。台湾的县级面如果没有城池点关联，会自动标记为 neutral，浅灰色显示，不影响视觉效果。如果你希望彻底移除，可在阶段0用大陆轮廓裁剪。

**Q：为什么不用 CHGIS 直接做先秦？**
A：CHGIS 先秦数据缺失。CHGIS 从秦开始才有完整时间序列，先秦只能用现代地理单元反推。