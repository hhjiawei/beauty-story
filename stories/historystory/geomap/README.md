# 山河战图 · 3D 历史战争地图

在 3D 地形中国地图上，按 `data/events.json` 中的一朝事件库，动画演绎行军、会战、占领、灭国、联盟、反叛、归附、迁都、继位、称王等历史事件。支持编年列表点选单播、时间轴跳转与自动连播。

## 运行

无需任何构建步骤，在项目根目录启动任意静态服务器即可：

```bash
python -m http.server 8000
# 浏览器访问 http://localhost:8000
```

校验数据：

```bash
python tools/validate_data.py
```

## 目录结构

```
├── index.html                    # UI 骨架与全部古风 CSS
├── main.js                       # 地图引擎：状态机 / 图层 / 动画 / 播放器
├── data/
│   ├── factions.json             # 势力与配色
│   ├── cities.json               # 城市坐标与初始归属
│   ├── events.json               # 长 JSON：一朝全部事件（当前内置 14 件商代事件）
│   └── geo/                      # 河流 / 湖泊 / 海岸线（Natural Earth 10m 裁剪）
├── geoBoundaries-CHN-ADM3_simplified.geojson  # 现代政区参考界（默认隐藏，图例可开）
├── tiles/
│   ├── china_relief/{z}/{x}/{y}.webp   # 全国古风渲染瓦片 z0–z7（约 3.9 MB）
│   ├── china_dem/{z}/{x}/{y}.png       # 全国 Terrarium DEM z0–z7（驱动 3D 地形）
│   └── henan_relief/{z}/{x}/{y}.webp   # 河南核心区 z8 细节叠加层（z≥7.2 淡入）
└── tools/
    ├── validate_data.py          # 数据校验（仅标准库）
    ├── gen_china_tiles.py        # 全国瓦片：下载 z7 Terrarium（约 391 张）并切 z0–z7 金字塔
    ├── gen_tiles_z8.py           # 河南 z8 细节层
    └── gen_tiles_lowzoom.py      # 低层级金字塔（墨卡托窗口正确嵌置）
```

## 地图视图与地形

- **全国视图**：点击时间轴右侧「全国」按钮，平滑飞到全中国俯眺视角（zoom≈3.2，pitch 38°，自动避开两侧面板）。全国瓦片覆盖 [70.3, 16.6]–[135, 54.2]，之外以旧纸色承接；`CONFIG.maxBounds` 限制可拖拽范围。
- **地形夸张系数**：`main.js` 顶部 `CONFIG.terrainExaggeration`（当前 `2.2`）。调大山峰更挺拔，调小更接近真实比例；改动即时生效，无需重新生成瓦片。
- **行军标记**：军队为立体幡旗——波浪旗面带布料褶皱光影，旗面书势力名（商、夏、周……），随行进方向转动，旗杆扎地行进；「称王」事件另有升旗特效。旗帜为 canvas 程序化雪碧图，可在 `main.js` 的 `drawFlagIcon` 中改形；旗面文字缺省取势力名首字，也可在 `factions.json` 中为势力加 `glyph` 字段自定义（如 `"glyph": "商"`）。

## 如何向 events.json 追加事件

事件按 `seq` 顺序播放。字段：

| 字段 | 说明 |
| --- | --- |
| `id` / `seq` | 唯一 id；seq 从 1 递增，是全库排序键 |
| `year` / `yearLabel` | 数值年（公元前为负）；展示文案如「约前1046年」 |
| `title` / `category` / `type` | 标题；`国际`/`国内`；类型见下 |
| `actors` | `{primary, target, supporters[]}`，取 factions.json 的 id |
| `routes[]` | `[{faction, from(城市id), toCity 或 toPoint, waypoints[]}]`；waypoints 缺省自动成弧 |
| `battle` | `{name, location, note}`，`type=battle` 必填 |
| `outcomes[]` | 状态变更：`occupy{city,to}`、`conquer{faction,by}`、`submit{faction,to}`、`rebel{faction,to,cities?}`、`ally{leader,members[]}`、`ally_break{leader}`、`move_capital{faction,from,to}`、`ruler_change{faction,ruler,title}`、`proclaim{faction,ruler,title}` |
| `summary` / `quote` | 叙述；引文须注明出处，无把握请省略 |
| `camera` | 可选 `{zoom, pitch}`，覆盖自动取景 |

`type` 决定动画编排：`march 行军`、`battle 会战`、`occupy 占领`、`conquer 灭国`、`ally 联盟`、`rebel 反叛`、`submit 归附`、`move_capital 迁都`、`succeed 继位`、`proclaim 称王`、`other 大事`。`type` 管「怎么演」，`outcomes` 管「地图变成什么样」，二者分离（如鸣条之战 = battle + conquer 夏 + occupy 两城）。

新城市/势力分别加入 `cities.json` / `factions.json` 后，运行 `python tools/validate_data.py` 必须 0 错误。

## 替换为自己的素材

- **瓦片**：将你自己的渲染瓦片与 Terrarium DEM 放入 `tiles/`，并在 `main.js` 顶部 `CONFIG` 中修改路径、缩放范围与 `tileSourceBounds`（瓦片实际覆盖范围）。重新生成全国瓦片：`python tools/gen_china_tiles.py`（需联网下载 Terrarium，约 391 张，12 线程约数分钟）。
- **县界**：`geoBoundaries-CHN-ADM3_simplified.geojson` 当前为 DataV 省级数据（轻量），可直接替换为你的 geoBoundaries ADM3 原文件，代码无需改动。
- **坐标说明**：鬼方等方国位置为示意。

## 操作

- 右侧编年列表：搜索 / 类型筛选 / 势力筛选，点击任意事件单播（地图先瞬时回到该事件之前的状态，再播动画）。
- 底部时间轴：播放/暂停（空格）、上/下一事件（←/→）、0.5/1/2/4 倍速、连播开关；刻度可点，灭国为大方点。
- 图例：势力存亡与都城、联盟分组；可开关势力范围 / 现代政区界 / 城市标签。
