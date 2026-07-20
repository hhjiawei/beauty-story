/* =========================================================================
 * 山河战图 · 3D 历史战争地图引擎
 * 分节：配置 / 工具 / 类型元数据 / 数据加载 / 校验 / 状态机 / 配色 /
 *       地图搭建 / 标签 / 势力范围 / 图例 / 补间 / 特效 / 军队 / 路线 /
 *       动画（十一类）/ 相机 / 播放器 / UI / 主循环
 * ===================================================================== */

'use strict';

/* ============================== 配置 ============================== */
const CONFIG = {
  reliefTiles: 'tiles/china_relief/{z}/{x}/{y}.webp',   // 全国古风瓦片 z0–z7
  demTiles: 'tiles/china_dem/{z}/{x}/{y}.png',         // 全国 Terrarium DEM z0–z7
  reliefDetailTiles: 'tiles/henan_relief/{z}/{x}/{y}.webp', // 河南核心区 z8 细节层
  dataDir: 'data',
  adm3Url: 'geoBoundaries-CHN-ADM3.geojson',
  tileBounds: [73, 17, 135, 54],                        // w, s, e, n（全国设计范围）
  tileSourceBounds: [70.3126, 16.65, 134.99, 54.14],    // 全国瓦片实际覆盖（略缩，避免边缘 404）
  henanDetailBounds: [109.6876, 30.7514, 118.1249, 37.7185], // 河南 z8 细节层范围
  worldBounds: [107.5, 30.5, 119.5, 38.5],              // 历史数据允许范围
  maxBounds: [[67.0, 13.0], [140.0, 57.5]],
  initialCamera: { center: [113.6, 34.8], zoom: 6.3, pitch: 52, bearing: -12 },
  chinaView: { bounds: [[74.5, 18.5], [134.0, 53.0]], pitch: 38 }, // 全国视图
  terrainExaggeration: 26.2,                             // 地形夸张系数（山峰更挺拔）
  colors: {
    paper: '#ece4d0', ink: '#2b241c', cinnabar: '#a63a2b',
    gold: '#d8b45a', ownerless: '#9a917e', smoke: '#2b241c',
  },
};

/* ============================== 工具 ============================== */
const $ = (id) => document.getElementById(id);

function hexToRgb(hex) {
  const h = hex.replace('#', '');
  return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)];
}
function rgbToHex([r, g, b]) {
  const c = (v) => Math.max(0, Math.min(255, Math.round(v))).toString(16).padStart(2, '0');
  return '#' + c(r) + c(g) + c(b);
}
function lerpColor(a, b, t) {
  const A = hexToRgb(a), B = hexToRgb(b);
  return rgbToHex([A[0] + (B[0] - A[0]) * t, A[1] + (B[1] - A[1]) * t, A[2] + (B[2] - A[2]) * t]);
}
function mixWithWhite(hex, ratio) { return lerpColor(hex, '#ffffff', ratio); }
function hexToRgba(hex, a) { const [r, g, b] = hexToRgb(hex); return `rgba(${r},${g},${b},${a})`; }

const easeInOut = (t) => (t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t);
const easeOut = (t) => 1 - (1 - t) * (1 - t);

async function fetchJSON(url) {
  const resp = await fetch(url);
  if (!resp.ok) throw new Error(`${url} HTTP ${resp.status}`);
  return resp.json();
}
function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}

/* ============================== 事件类型元数据 ============================== */
const TYPE_META = {
  march:        { label: '行军', char: '征', color: '#8c6a3f' },
  battle:       { label: '会战', char: '战', color: '#a63a2b' },
  occupy:       { label: '占领', char: '占', color: '#b03a2e' },
  conquer:      { label: '灭国', char: '灭', color: '#2b241c' },
  ally:         { label: '联盟', char: '盟', color: '#3f6c6b' },
  rebel:        { label: '反叛', char: '叛', color: '#6b4f6e' },
  submit:       { label: '归附', char: '附', color: '#5d7052' },
  move_capital: { label: '迁都', char: '迁', color: '#b0762a' },
  succeed:      { label: '继位', char: '继', color: '#c9a227' },
  proclaim:     { label: '称王', char: '王', color: '#a63a2b' },
  other:        { label: '大事', char: '事', color: '#4a5560' },
};
const INTL_TYPES = new Set(['march', 'battle', 'occupy', 'conquer', 'ally', 'rebel', 'submit']);

/* ============================== 数据仓库 ============================== */
const DB = {
  factions: new Map(), factionList: [],
  cities: new Map(), cityList: [],
  events: [],
};
const cityName = (id) => (DB.cities.get(id) ? DB.cities.get(id).name : id);
const factionName = (id) => (DB.factions.get(id) ? DB.factions.get(id).name : id);
const factionBaseColor = (id) => (DB.factions.get(id) ? DB.factions.get(id).color : '#888888');
const cityLoc = (id) => (DB.cities.get(id) ? DB.cities.get(id).location : null);

/* ============================== 数据校验（浏览器端子集） ============================== */
const OUTCOME_REQUIRED = {
  occupy: ['city', 'to'], conquer: ['faction', 'by'], submit: ['faction', 'to'],
  ally: ['leader', 'members'], rebel: ['faction', 'to'], ally_break: ['leader'],
  move_capital: ['faction', 'from', 'to'], ruler_change: ['faction', 'ruler'],
  proclaim: ['faction'],
};
function validateData(factions, cities, events) {
  const errors = [];
  const fids = new Set(factions.map((f) => f.id));
  const cids = new Set(cities.map((c) => c.id));
  const [w, s, e, n] = CONFIG.worldBounds;
  const inWorld = (p) => Array.isArray(p) && p[0] >= w && p[0] <= e && p[1] >= s && p[1] <= n;

  if (fids.size !== factions.length) errors.push('factions.json: id 重复');
  if (cids.size !== cities.length) errors.push('cities.json: id 重复');
  for (const c of cities) {
    if (!inWorld(c.location)) errors.push(`cities.json: ${c.id} 坐标超出 worldBounds`);
    if (c.owner !== null && !fids.has(c.owner)) errors.push(`cities.json: ${c.id} owner "${c.owner}" 不存在`);
  }
  const seqs = new Set();
  for (const ev of events) {
    const pre = `events.json[${ev.id || '?'}]`;
    for (const k of ['id', 'seq', 'year', 'yearLabel', 'title', 'category', 'type'])
      if (ev[k] === undefined) errors.push(`${pre}: 缺字段 ${k}`);
    if (seqs.has(ev.seq)) errors.push(`${pre}: seq ${ev.seq} 重复`);
    seqs.add(ev.seq);
    if (!TYPE_META[ev.type]) { errors.push(`${pre}: 未知 type "${ev.type}"`); continue; }
    if (ev.category === '国际' && !INTL_TYPES.has(ev.type)) errors.push(`${pre}: type ${ev.type} 与 category 国际 不符`);
    if (ev.category === '国内' && INTL_TYPES.has(ev.type)) errors.push(`${pre}: type ${ev.type} 与 category 国内 不符`);
    if (ev.type === 'battle') {
      if (!ev.battle || !inWorld(ev.battle.location)) errors.push(`${pre}: battle 缺 battle.location`);
      if (!Array.isArray(ev.routes) || ev.routes.length < 2) errors.push(`${pre}: battle 需 ≥2 条 routes`);
    }
    for (const r of ev.routes || []) {
      if (!fids.has(r.faction)) errors.push(`${pre}: route.faction "${r.faction}" 不存在`);
      if (!cids.has(r.from)) errors.push(`${pre}: route.from "${r.from}" 不存在`);
      if (r.toCity && !cids.has(r.toCity)) errors.push(`${pre}: route.toCity "${r.toCity}" 不存在`);
      if (!r.toCity && !inWorld(r.toPoint)) errors.push(`${pre}: route 终点缺失或越界`);
    }
    for (const oc of ev.outcomes || []) {
      const req = OUTCOME_REQUIRED[oc.type];
      if (!req) { errors.push(`${pre}: 未知 outcome "${oc.type}"`); continue; }
      for (const k of req) if (oc[k] === undefined) errors.push(`${pre}: outcome ${oc.type} 缺 ${k}`);
      const factionKeys = {
        occupy: ['to'], conquer: ['faction', 'by'], submit: ['faction', 'to'], rebel: ['faction', 'to'],
        ally: ['leader'], ally_break: ['leader'], move_capital: ['faction'],
        ruler_change: ['faction'], proclaim: ['faction'],
      }[oc.type] || [];
      for (const k of factionKeys) if (oc[k] && !fids.has(oc[k])) errors.push(`${pre}: outcome 引用势力 "${oc[k]}" 不存在`);
      const cityKeys = { occupy: ['city'], move_capital: ['from', 'to'] }[oc.type] || [];
      for (const k of cityKeys) if (oc[k] && !cids.has(oc[k])) errors.push(`${pre}: outcome 引用城市 "${oc[k]}" 不存在`);
      if (oc.type === 'ally') for (const m of oc.members || []) if (!fids.has(m)) errors.push(`${pre}: ally 成员 "${m}" 不存在`);
      if (oc.type === 'rebel') for (const cid of oc.cities || []) if (!cids.has(cid)) errors.push(`${pre}: rebel 城市 "${cid}" 不存在`);
    }
  }
  return errors;
}

/* ============================== 状态机（纯函数） ============================== */
function applyOutcome(state, oc) {
  const { cityOwner, capitals, alliances, demise } = state;
  const citiesOf = (fid) => DB.cityList.filter((c) => cityOwner.get(c.id) === fid).map((c) => c.id);
  const removeFromAlliances = (fid) => {
    for (const [leader, members] of [...alliances]) {
      const idx = members.indexOf(fid);
      if (idx >= 0) members.splice(idx, 1);
      if (leader === fid) alliances.delete(leader);
    }
  };
  switch (oc.type) {
    case 'occupy':
      cityOwner.set(oc.city, oc.to);
      break;
    case 'conquer':
    case 'submit':
      for (const cid of citiesOf(oc.faction)) cityOwner.set(cid, oc.type === 'conquer' ? oc.by : oc.to);
      removeFromAlliances(oc.faction);
      capitals.delete(oc.faction);
      demise.set(oc.faction, oc.type === 'conquer' ? '亡' : '归');
      break;
    case 'rebel':
      for (const cid of oc.cities || citiesOf(oc.faction)) cityOwner.set(cid, oc.to);
      break;
    case 'ally':
      alliances.set(oc.leader, [...(oc.members || [])]);
      break;
    case 'ally_break':
      alliances.delete(oc.leader);
      break;
    case 'move_capital':
      capitals.set(oc.faction, oc.to);
      break;
    case 'ruler_change':
    case 'proclaim':
      state.rulers.set(oc.faction, { name: oc.ruler || '', title: oc.title || '' });
      break;
  }
}

function buildState(uptoSeq) {
  const state = {
    cityOwner: new Map(), capitals: new Map(),
    alliances: new Map(), rulers: new Map(), demise: new Map(),
  };
  for (const c of DB.cityList) state.cityOwner.set(c.id, c.owner);
  for (const c of DB.cityList) if (c.tier === 1 && c.owner) state.capitals.set(c.owner, c.id);
  for (const ev of DB.events) {
    if (ev.seq > uptoSeq) break;
    for (const oc of ev.outcomes || []) applyOutcome(state, oc);
  }
  return state;
}

function factionAlive(state, fid) {
  for (const [, owner] of state.cityOwner) if (owner === fid) return true;
  return false;
}
function citiesOfFaction(state, fid) {
  return DB.cityList.filter((c) => state.cityOwner.get(c.id) === fid).map((c) => c.id);
}

/* 显示色：联盟成员取盟主同色系浅色（第 i 个成员混白 0.38+0.07i，上限 0.62） */
function displayColorOf(state, fid) {
  if (!fid) return CONFIG.colors.ownerless;
  for (const [leader, members] of state.alliances) {
    const idx = members.indexOf(fid);
    if (idx >= 0) return mixWithWhite(factionBaseColor(leader), Math.min(0.38 + 0.07 * (idx + 1), 0.62));
  }
  return factionBaseColor(fid);
}
/* 城市显示层级：都城恒为 1，其余按 tier */
function displayTierOf(state, city) {
  const owner = state.cityOwner.get(city.id);
  if (owner && state.capitals.get(owner) === city.id) return 1;
  return Math.min(Math.max(city.tier, 2), 3);
}

/* ============================== 运行时 ============================== */
const RT = {
  map: null, state: null, seq: 0,
  cityColor: new Map(),      // 当前展示色（动画中可被逐帧改写）
  playing: false, autoplay: false, speed: 1, busy: false, locked: false,
  abort: null, activeSeq: 0, playId: 0,
  labelsOn: true, territoryOn: true, adm3On: false,
  citiesDirty: true, armiesDirty: false,
};

/* ============================== 雪碧图（canvas 程序化生成） ============================== */
function makeCanvas(size) {
  const c = document.createElement('canvas');
  c.width = c.height = size;
  return [c, c.getContext('2d')];
}
function drawStarIcon(fill, stroke) {
  const [c, x] = makeCanvas(48);
  const cx = 24, cy = 24, R = 19, r = 8;
  x.beginPath();
  for (let i = 0; i < 10; i++) {
    const ang = -Math.PI / 2 + (i * Math.PI) / 5;
    const rad = i % 2 === 0 ? R : r;
    const px = cx + rad * Math.cos(ang), py = cy + rad * Math.sin(ang);
    i === 0 ? x.moveTo(px, py) : x.lineTo(px, py);
  }
  x.closePath();
  x.fillStyle = fill; x.fill();
  x.lineWidth = 3; x.strokeStyle = stroke; x.stroke();
  return x.getImageData(0, 0, c.width, c.height);
}
/* 立体幡旗：波浪旗面 + 褶皱光影 + 圆柱旗杆 + 势力名（glyph 缺省取势力名首字） */
function drawFlagIcon(color, glyph) {
  const [c, x] = makeCanvas(72);
  const ink = '#2b241c';
  const paper = '#f6f0e2';

  /* 旗面形状：左缘贴杆，上下边微弧，右缘正弦波浪（迎风飘扬） */
  const flagPath = () => {
    x.beginPath();
    x.moveTo(19, 10);
    x.quadraticCurveTo(40, 6, 62, 11);              // 上边微弯
    x.bezierCurveTo(57, 16, 65, 21, 60, 26);        // 右缘波浪
    x.bezierCurveTo(56, 30, 63, 34, 58, 38);
    x.quadraticCurveTo(38, 34, 19, 36);             // 下边微弯
    x.closePath();
  };

  /* 旗面底色：左上受光 → 右下背光 对角渐变 */
  const grad = x.createLinearGradient(19, 7, 62, 38);
  grad.addColorStop(0, mixWithWhite(color, 0.22));
  grad.addColorStop(0.5, color);
  grad.addColorStop(1, lerpColor(color, '#141008', 0.3));
  flagPath();
  x.fillStyle = grad; x.fill();

  /* 布料褶皱：clip 旗面后交替竖向亮/暗条 */
  x.save();
  flagPath(); x.clip();
  for (let i = 0; i < 5; i++) {
    const px = 25 + i * 8;
    x.fillStyle = i % 2 ? 'rgba(20,16,8,0.16)' : 'rgba(255,250,235,0.15)';
    x.fillRect(px, 0, 4.2, 44);
  }
  /* 底部投影增强体积感 */
  const sh = x.createLinearGradient(0, 26, 0, 38);
  sh.addColorStop(0, 'rgba(20,16,8,0)');
  sh.addColorStop(1, 'rgba(20,16,8,0.22)');
  x.fillStyle = sh; x.fillRect(16, 26, 50, 14);
  x.restore();

  /* 旗面描边 */
  flagPath();
  x.lineWidth = 2.2; x.strokeStyle = ink; x.stroke();

  /* 势力名：宣纸色 + 墨影（先影后字），略有浮凸感 */
  if (glyph) {
    x.font = '900 19px "Noto Serif SC", "Songti SC", serif';
    x.textAlign = 'center'; x.textBaseline = 'middle';
    x.fillStyle = 'rgba(20,16,8,0.75)';
    x.fillText(glyph, 36.2, 22.2);
    x.fillStyle = paper;
    x.fillText(glyph, 35, 21);
  }

  /* 旗杆：深色主杆 + 侧向高光 = 圆柱感 */
  x.lineCap = 'round';
  x.lineWidth = 4.4; x.strokeStyle = ink;
  x.beginPath(); x.moveTo(15, 6); x.lineTo(15, 68); x.stroke();
  x.lineWidth = 1.5; x.strokeStyle = 'rgba(246,240,226,0.45)';
  x.beginPath(); x.moveTo(13.8, 8); x.lineTo(13.8, 66); x.stroke();
  /* 杆顶金珠 */
  x.beginPath(); x.arc(15, 5, 2.8, 0, Math.PI * 2);
  x.fillStyle = '#d8b45a'; x.fill();
  x.lineWidth = 1.2; x.strokeStyle = ink; x.stroke();

  return x.getImageData(0, 0, c.width, c.height);
}
function drawSwordsIcon() {
  const [c, x] = makeCanvas(56);
  x.lineWidth = 5; x.lineCap = 'round'; x.strokeStyle = '#2b241c';
  x.beginPath(); x.moveTo(12, 12); x.lineTo(44, 44); x.stroke();
  x.beginPath(); x.moveTo(44, 12); x.lineTo(12, 44); x.stroke();
  x.lineWidth = 3; x.strokeStyle = '#f6f0e2';
  x.beginPath(); x.moveTo(12, 12); x.lineTo(20, 20); x.stroke();
  x.beginPath(); x.moveTo(44, 12); x.lineTo(36, 20); x.stroke();
  return x.getImageData(0, 0, c.width, c.height);
}

/* ============================== 地图搭建 ============================== */
function createMap() {
  const style = {
    version: 8,
    sources: {},
    fog: {
      range: [2.2, 22], color: '#ded3ba', 'horizon-blend': 0.1,
      'high-color': '#e8dfc8', 'space-color': '#d8ccb2', 'star-intensity': 0,
    },
    layers: [{ id: 'bg', type: 'background', paint: { 'background-color': CONFIG.colors.paper } }],
  };
  const map = new maplibregl.Map({
    container: 'map',
    style,
    center: CONFIG.initialCamera.center,
    zoom: CONFIG.initialCamera.zoom,
    pitch: CONFIG.initialCamera.pitch,
    bearing: CONFIG.initialCamera.bearing,
    minZoom: 3.0, maxZoom: 10.5,
    maxBounds: CONFIG.maxBounds,
    attributionControl: false,
    fadeDuration: 200,
  });
  map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'bottom-right');
  return map;
}

function setupMapLayers(map) {
  /* ---- 底图数据源 ---- */
  map.addSource('relief', {
    type: 'raster', tiles: [CONFIG.reliefTiles], tileSize: 256, maxzoom: 7,
    bounds: CONFIG.tileSourceBounds,
  });
  map.addSource('relief-detail', {
    type: 'raster', tiles: [CONFIG.reliefDetailTiles], tileSize: 256, minzoom: 8, maxzoom: 8,
    bounds: CONFIG.henanDetailBounds,
  });
  map.addSource('dem', {
    type: 'raster-dem', tiles: [CONFIG.demTiles], tileSize: 256, encoding: 'terrarium', maxzoom: 7,
    bounds: CONFIG.tileSourceBounds,
  });
  map.addSource('dem-hs', {
    type: 'raster-dem', tiles: [CONFIG.demTiles], tileSize: 256, encoding: 'terrarium', maxzoom: 7,
    bounds: CONFIG.tileSourceBounds,
  });
  map.addSource('ocean', { type: 'geojson', data: `${CONFIG.dataDir}/geo/ocean.json` });
  map.addSource('lakes', { type: 'geojson', data: `${CONFIG.dataDir}/geo/lakes.json` });
  map.addSource('rivers', { type: 'geojson', data: `${CONFIG.dataDir}/geo/rivers.json` });
  map.addSource('coastline', { type: 'geojson', data: `${CONFIG.dataDir}/geo/coastline.json` });
  map.addSource('adm3', { type: 'geojson', data: CONFIG.adm3Url });

  map.addLayer({ id: 'relief', type: 'raster', source: 'relief',
    paint: { 'raster-opacity': 0.92, 'raster-fade-duration': 300 } });
  map.addLayer({ id: 'relief-detail', type: 'raster', source: 'relief-detail', minzoom: 7.2,
    paint: { 'raster-opacity': 0.94, 'raster-fade-duration': 300 } });
  map.addLayer({ id: 'hillshade', type: 'hillshade', source: 'dem-hs',
    paint: {
      'hillshade-exaggeration': 0.35,
      'hillshade-shadow-color': 'rgba(90, 70, 50, 0.55)',
      'hillshade-highlight-color': 'rgba(255, 250, 235, 0.22)',
      'hillshade-accent-color': 'rgba(120, 90, 60, 0.18)',
    } });
  map.addLayer({ id: 'ocean', type: 'fill', source: 'ocean',
    paint: { 'fill-color': '#9fb0a5', 'fill-opacity': 0.62 } });
  map.addLayer({ id: 'lakes', type: 'fill', source: 'lakes',
    paint: { 'fill-color': '#a7b8ac', 'fill-opacity': 0.55 } });
  map.addLayer({ id: 'rivers', type: 'line', source: 'rivers',
    paint: {
      'line-color': '#8fa39b', 'line-opacity': 0.8,
      'line-width': ['interpolate', ['linear'], ['zoom'], 5, 0.6, 10, 2.2],
    } });
  map.addLayer({ id: 'coastline', type: 'line', source: 'coastline',
    paint: { 'line-color': '#7d918a', 'line-width': 1, 'line-opacity': 0.7 } });
  map.addLayer({ id: 'adm3', type: 'line', source: 'adm3',
    layout: { visibility: 'none' },
    paint: { 'line-color': '#8a7a5c', 'line-width': 0.5, 'line-opacity': 0.35 } });

  /* ---- 3D 地形与古色雾霭（fog 已在 style 中声明） ---- */
  map.setTerrain({ source: 'dem', exaggeration: CONFIG.terrainExaggeration });

  /* ---- 雪碧图 ---- */
  map.addImage('star-ink', drawStarIcon('#2b241c', '#f6f0e2'), { pixelRatio: 2 });
  map.addImage('star-gold', drawStarIcon('#d8b45a', '#2b241c'), { pixelRatio: 2 });
  map.addImage('swords', drawSwordsIcon(), { pixelRatio: 2 });
  for (const f of DB.factionList) {
    map.addImage(`flag-${f.id}`, drawFlagIcon(f.color, f.glyph || (f.name || '')[0]), { pixelRatio: 2 });
  }

  /* ---- 势力范围 / 盟约线 ---- */
  map.addSource('territory', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } });
  map.addLayer({ id: 'territory-fill', type: 'fill', source: 'territory',
    paint: { 'fill-color': ['get', 'color'], 'fill-opacity': 0.08 } });
  map.addLayer({ id: 'territory-line', type: 'line', source: 'territory',
    paint: { 'line-color': ['get', 'color'], 'line-width': 1, 'line-opacity': 0.4, 'line-dasharray': [2, 2] } });
  map.addSource('alliance-lines', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } });
  map.addLayer({ id: 'alliance-lines', type: 'line', source: 'alliance-lines',
    paint: { 'line-color': ['get', 'color'], 'line-width': 1.6, 'line-opacity': 0.25, 'line-dasharray': [2, 2.4] } });

  /* ---- 城市（光晕 + 城心 + 都城星徽） ---- */
  map.addSource('cities', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } });
  map.addLayer({ id: 'city-halo', type: 'circle', source: 'cities',
    paint: {
      'circle-color': ['get', 'color'], 'circle-opacity': 0.26, 'circle-blur': 1,
      'circle-radius': ['interpolate', ['linear'], ['zoom'],
        5, ['match', ['get', 'dtier'], 1, 22, 2, 15, 10],
        10, ['match', ['get', 'dtier'], 1, 52, 2, 36, 24]],
    } });
  map.addLayer({ id: 'city-core', type: 'circle', source: 'cities',
    paint: {
      'circle-color': ['get', 'color'],
      'circle-stroke-color': '#2b241c', 'circle-stroke-width': 1.5,
      'circle-radius': ['interpolate', ['linear'], ['zoom'],
        5, ['match', ['get', 'dtier'], 1, 7, 2, 5, 3.2],
        10, ['match', ['get', 'dtier'], 1, 15, 2, 11, 7]],
    } });
  map.addLayer({ id: 'capital-star', type: 'symbol', source: 'cities',
    filter: ['==', ['get', 'dtier'], 1],
    layout: {
      'icon-image': 'star-ink', 'icon-allow-overlap': true, 'icon-ignore-placement': true,
      'icon-size': ['interpolate', ['linear'], ['zoom'], 5, 0.32, 10, 0.62],
    } });

  /* ---- 特效（脉冲环 / 图标） ---- */
  map.addSource('effects', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } });
  map.addLayer({ id: 'effects-ring', type: 'circle', source: 'effects',
    filter: ['==', ['get', 'kind'], 'ring'],
    paint: {
      'circle-color': ['get', 'color'], 'circle-opacity': 0,
      'circle-stroke-color': ['get', 'color'], 'circle-stroke-opacity': ['get', 'o'],
      'circle-stroke-width': 2.6, 'circle-radius': ['get', 'r'], 'circle-blur': 0.15,
    } });
  map.addLayer({ id: 'effects-icon', type: 'symbol', source: 'effects',
    filter: ['==', ['get', 'kind'], 'icon'],
    layout: {
      'icon-image': ['get', 'icon'], 'icon-size': ['get', 'size'],
      'icon-allow-overlap': true, 'icon-ignore-placement': true, 'icon-rotation-alignment': 'viewport',
    },
    paint: { 'icon-opacity': ['get', 'o'] } });

  /* ---- 军队标记 ---- */
  map.addSource('armies', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } });
  map.addLayer({ id: 'armies-symbol', type: 'symbol', source: 'armies',
    layout: {
      'icon-image': ['get', 'icon'], 'icon-size': 1.32,
      'icon-rotate': ['get', 'bearing'], 'icon-rotation-alignment': 'map',
      'icon-allow-overlap': true, 'icon-ignore-placement': true, 'icon-anchor': 'bottom',
    } });
}

/* ============================== 城市中文标签层（HTML） ============================== */
const LabelLayer = {
  els: new Map(),
  init() {
    const box = $('labels');
    for (const c of DB.cityList) {
      const d = el('div', 'city-label');
      const mark = el('span', 'cap-mark', '◆');
      d.appendChild(mark);
      d.appendChild(document.createTextNode(c.name));
      box.appendChild(d);
      this.els.set(c.id, d);
    }
  },
  update() {
    const map = RT.map;
    if (!map || !RT.state) return;
    const zoom = map.getZoom();
    const W = map.getCanvas().clientWidth, H = map.getCanvas().clientHeight;
    const placed = []; // 已放置标签（按优先级），用于避让
    const order = DB.cityList
      .map((c) => ({ c, dtier: displayTierOf(RT.state, c), p: map.project(c.location) }))
      .sort((a, b) => a.dtier - b.dtier);
    for (const { c, dtier, p } of order) {
      const d = this.els.get(c.id);
      const minZoom = dtier === 1 ? 5.6 : dtier === 2 ? 6.6 : 7.4;
      if (!RT.labelsOn || zoom < minZoom) { d.style.display = 'none'; continue; }
      if (p.x < -40 || p.x > W + 40 || p.y < -20 || p.y > H + 20) { d.style.display = 'none'; continue; }
      // 低优先级标签与高优先级标签过近时隐藏
      if (dtier > 1 && placed.some((q) => Math.abs(q.x - p.x) < 34 && Math.abs(q.y - p.y) < 18)) {
        d.style.display = 'none'; continue;
      }
      placed.push(p);
      d.style.display = 'block';
      const t = Math.min(Math.max((zoom - 5.5) / 4, 0), 1);
      const size = (dtier === 1 ? 14.5 : dtier === 2 ? 12.5 : 11) + t * 3.5;
      d.style.fontSize = size.toFixed(1) + 'px';
      d.style.transform = `translate(${p.x.toFixed(1)}px, ${p.y.toFixed(1)}px) translate(-50%, -150%)`;
      d.classList.toggle('capital', dtier === 1);
      d.style.zIndex = dtier === 1 ? 3 : dtier === 2 ? 2 : 1;
      d.firstChild.style.display = dtier === 1 ? 'inline' : 'none';
    }
  },
};

/* ============================== 城市 / 势力范围 / 盟约线渲染 ============================== */
function rebuildCitiesSource() {
  const feats = [];
  for (const c of DB.cityList) {
    feats.push({
      type: 'Feature',
      properties: {
        id: c.id, dtier: displayTierOf(RT.state, c),
        color: RT.cityColor.get(c.id) || CONFIG.colors.ownerless,
      },
      geometry: { type: 'Point', coordinates: c.location },
    });
  }
  RT.map.getSource('cities').setData({ type: 'FeatureCollection', features: feats });
}

function syncCityColorsFromState() {
  for (const c of DB.cityList) {
    const owner = RT.state.cityOwner.get(c.id);
    RT.cityColor.set(c.id, owner ? displayColorOf(RT.state, owner) : CONFIG.colors.ownerless);
  }
  RT.citiesDirty = true;
}

function rebuildTerritory(animated) {
  const src = RT.map.getSource('territory');
  const apply = () => {
    const feats = [];
    if (RT.territoryOn) {
      for (const f of DB.factionList) {
        const owned = citiesOfFaction(RT.state, f.id);
        if (owned.length < 3) continue;
        try {
          const pts = turf.featureCollection(owned.map((cid) => turf.point(cityLoc(cid))));
          const hull = turf.convex(pts);
          if (!hull) continue;
          const buf = turf.buffer(hull, 60, { units: 'kilometers' });
          let geom = buf.geometry;
          try { geom = turf.polygonSmooth(buf, { iterations: 2 }).features[0].geometry; } catch (e) { /* 用未平滑面 */ }
          feats.push({ type: 'Feature', properties: { color: displayColorOf(RT.state, f.id) }, geometry: geom });
        } catch (e) { console.warn('territory', f.id, e); }
      }
    }
    src.setData({ type: 'FeatureCollection', features: feats });
  };
  if (!animated) { apply(); return; }
  if (!RT.map.getLayer('territory-fill')) { apply(); return; }
  Tweens.add({ dur: 200, onUpdate: (t) => {
    RT.map.setPaintProperty('territory-fill', 'fill-opacity', 0.08 * (1 - t));
    RT.map.setPaintProperty('territory-line', 'line-opacity', 0.4 * (1 - t));
  }, onComplete: () => {
    apply();
    Tweens.add({ dur: 800, onUpdate: (t) => {
      RT.map.setPaintProperty('territory-fill', 'fill-opacity', 0.08 * t);
      RT.map.setPaintProperty('territory-line', 'line-opacity', 0.4 * t);
    } });
  } });
}

function rebuildAllianceLines() {
  const feats = [];
  for (const [leader, members] of RT.state.alliances) {
    const from = cityLoc(RT.state.capitals.get(leader));
    if (!from) continue;
    for (const m of members) {
      const to = cityLoc(RT.state.capitals.get(m));
      if (!to) continue;
      feats.push({
        type: 'Feature',
        properties: { color: mixWithWhite(factionBaseColor(leader), 0.3) },
        geometry: { type: 'LineString', coordinates: [from, to] },
      });
    }
  }
  RT.map.getSource('alliance-lines').setData({ type: 'FeatureCollection', features: feats });
}

/* ============================== 图例 ============================== */
function renderLegend() {
  const box = $('legend-factions');
  box.innerHTML = '';
  const allied = new Set();
  for (const [, members] of RT.state.alliances) members.forEach((m) => allied.add(m));

  const rows = [];
  for (const f of DB.factionList) {
    if (allied.has(f.id)) continue; // 盟友挂到盟主行后
    rows.push({ f, members: RT.state.alliances.get(f.id) || [] });
  }
  const aliveRows = [], deadRows = [];
  for (const r of rows) (factionAlive(RT.state, r.f.id) ? aliveRows : deadRows).push(r);

  const makeRow = (fid, isMember) => {
    const alive = factionAlive(RT.state, fid);
    const row = el('div', 'lg-faction' + (alive ? '' : ' dead') + (isMember ? ' ally-member' : ''));
    const dot = el('span', 'dot');
    dot.style.background = displayColorOf(RT.state, fid);
    row.appendChild(dot);
    row.appendChild(el('span', '', factionName(fid)));
    if (!alive) {
      row.appendChild(el('span', 'dead-mark', RT.state.demise.get(fid) || '亡'));
    } else {
      const cap = RT.state.capitals.get(fid);
      if (cap) row.appendChild(el('span', 'cap-name', '都 ' + cityName(cap)));
    }
    return row;
  };
  for (const r of [...aliveRows, ...deadRows]) {
    box.appendChild(makeRow(r.f.id, false));
    for (const m of r.members) box.appendChild(makeRow(m, true));
  }
}

/* ============================== 状态瞬时落地 ============================== */
function renderStateInstant() {
  syncCityColorsFromState();
  rebuildCitiesSource();
  rebuildTerritory(false);
  rebuildAllianceLines();
  renderLegend();
}
function jumpToState(seq) {
  RT.state = buildState(seq);
  RT.seq = seq;
  renderStateInstant();
  UI.updateTimeline();
}

/* ============================== 补间引擎 ============================== */
const Tweens = {
  set: new Set(),
  add({ dur, ease = easeInOut, onUpdate, onComplete, tag = 'event' }) {
    const t = { start: performance.now(), dur: Math.max(1, dur / RT.speed), ease, onUpdate, onComplete, tag, dead: false };
    this.set.add(t);
    return t;
  },
  cancelTag(tag) { for (const t of this.set) if (t.tag === tag) t.dead = true; },
  update(now) {
    for (const t of [...this.set]) {
      if (t.dead) { this.set.delete(t); continue; }
      let p = (now - t.start) / t.dur;
      if (p >= 1) { this.set.delete(t); t.onUpdate && t.onUpdate(t.ease(1)); t.onComplete && t.onComplete(); continue; }
      if (p < 0) p = 0;
      t.onUpdate && t.onUpdate(t.ease(p));
    }
  },
};
function wait(ms, signal) {
  return new Promise((resolve, reject) => {
    if (signal && signal.aborted) return reject({ cancelled: true });
    let t;
    const onAbort = () => { if (t) t.dead = true; reject({ cancelled: true }); };
    t = Tweens.add({ dur: ms, onUpdate: () => {}, onComplete: () => {
      if (signal) signal.removeEventListener('abort', onAbort);
      resolve();
    } });
    if (signal) signal.addEventListener('abort', onAbort, { once: true });
  });
}
function throwIfAborted(signal) { if (signal && signal.aborted) throw { cancelled: true }; }

/* ============================== 特效管理（脉冲环 / 图标，单一 source） ============================== */
const FX = {
  items: [],
  hadItems: false,
  spawnRing(lngLat, color, { r1 = 90, dur = 900, delay = 0, tag = 'event' } = {}) {
    this.items.push({ kind: 'ring', lngLat, color, r1, dur: dur / RT.speed, start: performance.now() + delay / RT.speed, tag });
  },
  spawnIcon(lngLat, icon, { size = 0.9, dur = 1500, delay = 0, tag = 'event' } = {}) {
    this.items.push({ kind: 'icon', lngLat, icon, size, dur: dur / RT.speed, start: performance.now() + delay / RT.speed, tag });
  },
  clear(tag) { if (tag) this.items = this.items.filter((i) => i.tag !== tag); else this.items = []; this.flush(); },
  flush() {
    const now = performance.now();
    this.items = this.items.filter((i) => now - i.start < i.dur + 60);
    const feats = [];
    for (const i of this.items) {
      const p = (now - i.start) / i.dur;
      if (p < 0) { feats.push(); continue; }
      const pp = Math.min(Math.max(p, 0), 1);
      if (i.kind === 'ring') {
        feats.push({ type: 'Feature', properties: { kind: 'ring', color: i.color, r: 6 + i.r1 * easeOut(pp), o: 0.75 * (1 - pp) }, geometry: { type: 'Point', coordinates: i.lngLat } });
      } else {
        const o = pp < 0.15 ? pp / 0.15 : pp > 0.75 ? (1 - pp) / 0.25 : 1;
        feats.push({ type: 'Feature', properties: { kind: 'icon', icon: i.icon, size: i.size, o: Math.max(0, Math.min(1, o)) }, geometry: { type: 'Point', coordinates: i.lngLat } });
      }
    }
    if (feats.length || this.hadItems) RT.map.getSource('effects').setData({ type: 'FeatureCollection', features: feats });
    this.hadItems = feats.length > 0;
  },
};

/* ============================== 军队标记 ============================== */
const Armies = {
  items: [], // {icon, lngLat, bearing}
  set(items) { this.items = items; RT.armiesDirty = true; },
  clear() { this.items = []; RT.armiesDirty = true; },
  flush() {
    const feats = this.items.map((a) => ({
      type: 'Feature', properties: { icon: a.icon, bearing: a.bearing || 0 },
      geometry: { type: 'Point', coordinates: a.lngLat },
    }));
    RT.map.getSource('armies').setData({ type: 'FeatureCollection', features: feats });
  },
};

/* ============================== 行军路线（line-gradient 生长） ============================== */
let routeSeq = 0;
const Routes = {
  active: [],
  buildPath(from, to, waypoints) {
    let coords;
    if (waypoints && waypoints.length) {
      coords = [from, ...waypoints, to];
      try { return turf.bezierSpline(turf.lineString(coords), { resolution: 8000, sharpness: 0.85 }).geometry.coordinates; } catch (e) { return coords; }
    }
    // 自动弧线：二次贝塞尔，中点沿法向偏移 12% 距离
    const dx = to[0] - from[0], dy = to[1] - from[1];
    const dist = Math.hypot(dx, dy) || 1e-6;
    const mx = (from[0] + to[0]) / 2, my = (from[1] + to[1]) / 2;
    const off = dist * 0.12;
    const ctrl = [mx - (dy / dist) * off, my + (dx / dist) * off];
    coords = [];
    for (let i = 0; i <= 64; i++) {
      const t = i / 64, u = 1 - t;
      coords.push([
        u * u * from[0] + 2 * u * t * ctrl[0] + t * t * to[0],
        u * u * from[1] + 2 * u * t * ctrl[1] + t * t * to[1],
      ]);
    }
    return coords;
  },
  add(coords, colorHex, factionId) {
    const id = ++routeSeq;
    const srcId = `route-src-${id}`, casingId = `route-casing-${id}`, lineId = `route-line-${id}`;
    const color = hexToRgba(colorHex, 1);
    RT.map.addSource(srcId, {
      type: 'geojson', lineMetrics: true,
      data: { type: 'Feature', properties: {}, geometry: { type: 'LineString', coordinates: coords } },
    });
    const before = RT.map.getLayer('effects-ring') ? 'effects-ring' : undefined;
    RT.map.addLayer({ id: casingId, type: 'line', source: srcId,
      paint: { 'line-color': 'rgba(43,36,28,0.75)', 'line-width': 6.5, 'line-opacity': 0 } }, before);
    RT.map.addLayer({ id: lineId, type: 'line', source: srcId,
      paint: {
        'line-width': 4.2, 'line-opacity': 0.95,
        'line-gradient': ['interpolate', ['linear'], ['line-progress'],
          0, color, 0.001, color, 0.002, 'rgba(0,0,0,0)', 1, 'rgba(0,0,0,0)'],
      } }, before);
    const h = { id, srcId, casingId, lineId, color, coords, faction: factionId, len: turf.length(turf.lineString(coords), { units: 'kilometers' }) };
    this.active.push(h);
    return h;
  },
  setProgress(h, p) {
    if (!RT.map.getLayer(h.lineId)) return;
    const q = Math.min(p, 0.997); // 保证插值输入严格递增
    RT.map.setPaintProperty(h.lineId, 'line-gradient', ['interpolate', ['linear'], ['line-progress'],
      0, h.color, q, h.color, q + 0.0025, 'rgba(0,0,0,0)', 1, 'rgba(0,0,0,0)']);
    RT.map.setPaintProperty(h.casingId, 'line-opacity', 0.75 * Math.min(p * 3, 1));
  },
  async fadeOutAll(ms = 500) {
    const hs = [...this.active];
    await new Promise((res) => {
      Tweens.add({ dur: ms, onUpdate: (t) => {
        for (const h of hs) {
          if (RT.map.getLayer(h.lineId)) RT.map.setPaintProperty(h.lineId, 'line-opacity', 0.95 * (1 - t));
          if (RT.map.getLayer(h.casingId)) RT.map.setPaintProperty(h.casingId, 'line-opacity', 0.75 * (1 - t));
        }
      }, onComplete: res, tag: 'route' });
    });
    for (const h of hs) this.remove(h);
  },
  remove(h) {
    for (const lid of [h.lineId, h.casingId]) if (RT.map.getLayer(lid)) RT.map.removeLayer(lid);
    if (RT.map.getSource(h.srcId)) RT.map.removeSource(h.srcId);
    this.active = this.active.filter((x) => x !== h);
  },
  clear() { for (const h of [...this.active]) this.remove(h); },
};

/* 军队沿路线行进：progress 驱动，turf.along 贴线，bearing 转向 */
function armyTween(routeHandles, durMs, signal) {
  return new Promise((resolve, reject) => {
    const lines = routeHandles.map((h) => turf.lineString(h.coords));
    let t;
    const onAbort = () => { if (t) t.dead = true; Armies.clear(); reject({ cancelled: true }); };
    t = Tweens.add({ dur: durMs, ease: (x) => x, onUpdate: (p) => {
      Armies.set(routeHandles.map((h, i) => {
        const line = lines[i];
        const d = Math.max(0.001, h.len * p);
        const pos = turf.along(line, d, { units: 'kilometers' }).geometry.coordinates;
        const ahead = turf.along(line, Math.min(d + 0.4, h.len), { units: 'kilometers' }).geometry.coordinates;
        return { icon: `flag-${h.faction}`, lngLat: pos, bearing: turf.bearing(pos, ahead) };
      }));
    }, onComplete: () => {
      if (signal) signal.removeEventListener('abort', onAbort);
      resolve();
    }, tag: 'event' });
    if (signal) signal.addEventListener('abort', onAbort, { once: true });
  });
}

/* ============================== 城市易主动效（基础共用） ============================== */
function cityLerp(cityId, toColorHex, durMs, signal) {
  return new Promise((resolve, reject) => {
    const from = RT.cityColor.get(cityId) || CONFIG.colors.ownerless;
    let t;
    const onAbort = () => { if (t) t.dead = true; reject({ cancelled: true }); };
    t = Tweens.add({ dur: durMs, onUpdate: (p) => {
      RT.cityColor.set(cityId, lerpColor(from, toColorHex, p));
      RT.citiesDirty = true;
    }, onComplete: () => {
      if (signal) signal.removeEventListener('abort', onAbort);
      resolve();
    }, tag: 'event' });
    if (signal) signal.addEventListener('abort', onAbort, { once: true });
  });
}

/* 占领：900ms 渐变 + 双脉冲环 */
async function animateOccupy(cityId, toFaction, signal, { ringScale = 1, colorOverride } = {}) {
  const loc = cityLoc(cityId);
  const target = colorOverride || displayColorOf(RT.state, toFaction);
  FX.spawnRing(loc, target, { r1: 92 * ringScale, dur: 900 });
  FX.spawnRing(loc, target, { r1: 92 * ringScale, dur: 900, delay: 240 });
  await cityLerp(cityId, target, 900, signal);
}

/* 灭国/归附级联：按距本方都城由近及远，都城最后且有强化效果 */
async function animateCascade(factionId, toColorHex, signal, { stagger = 260, dur = 900, smoky = false } = {}) {
  const owned = citiesOfFaction(RT.state, factionId);
  if (!owned.length) return;
  const cap = RT.state.capitals.get(factionId) || owned[0];
  const capLoc = cityLoc(cap);
  const sorted = [...owned].sort((a, b) =>
    turf.distance(cityLoc(a), capLoc) - turf.distance(cityLoc(b), capLoc));
  const jobs = [];
  sorted.forEach((cid, i) => {
    const isCap = cid === cap;
    jobs.push((async () => {
      await wait(i * stagger, signal);
      const loc = cityLoc(cid);
      if (isCap && smoky) FX.spawnRing(loc, CONFIG.colors.smoke, { r1: 150, dur: 1300 });
      FX.spawnRing(loc, toColorHex, { r1: isCap ? 130 : 88, dur: isCap ? 1200 : 900 });
      if (isCap) FX.spawnRing(loc, toColorHex, { r1: 130, dur: 1200, delay: 240 });
      await cityLerp(cid, toColorHex, isCap ? dur * 1.3 : dur, signal);
    })());
  });
  await Promise.all(jobs);
}

/* 联盟变色：成员城市渐变至盟友浅色 */
async function animateTintTo(cityIds, colorHex, durMs, signal) {
  await Promise.all(cityIds.map((cid) => cityLerp(cid, colorHex, durMs, signal)));
}

/* 反叛闪烁：旧色↔新色 3 次后定格 */
async function animateFlicker(cityId, finalColor, signal) {
  const oldColor = RT.cityColor.get(cityId);
  for (let i = 0; i < 3; i++) {
    await cityLerp(cityId, finalColor, 160, signal);
    await cityLerp(cityId, oldColor, 160, signal);
  }
  FX.spawnRing(cityLoc(cityId), '#b03a2e', { r1: 100, dur: 800 });
  await cityLerp(cityId, finalColor, 240, signal);
}

/* ============================== outcome 落地（动画 + 状态推进） ============================== */
async function applyOutcomeAnimated(oc, ev, signal) {
  switch (oc.type) {
    case 'occupy': {
      applyOutcome(RT.state, oc);
      await animateOccupy(oc.city, oc.to, signal);
      break;
    }
    case 'conquer': {
      const target = displayColorOf({ ...RT.state, alliances: new Map() }, oc.by); // 进攻方正色
      await animateCascade(oc.faction, target, signal, { stagger: 260, dur: 900, smoky: true });
      applyOutcome(RT.state, oc);
      syncCityColorsFromState();
      renderLegend();
      UI.showBanner(`${factionName(oc.faction)}亡于${factionName(oc.by)}`, ev.yearLabel + ' · 灭国', 2600);
      break;
    }
    case 'submit': {
      const target = displayColorOf(RT.state, oc.to);
      await animateCascade(oc.faction, target, signal, { stagger: 200, dur: 1200, smoky: false });
      applyOutcome(RT.state, oc);
      syncCityColorsFromState();
      renderLegend();
      UI.showBanner(`${factionName(oc.faction)}归于${factionName(oc.to)}`, ev.yearLabel + ' · 归附', 2200);
      break;
    }
    case 'rebel': {
      const target = displayColorOf(RT.state, oc.to);
      const ids = oc.cities || citiesOfFaction(RT.state, oc.faction);
      for (const cid of ids) await animateFlicker(cid, target, signal);
      applyOutcome(RT.state, oc);
      syncCityColorsFromState();
      break;
    }
    case 'ally': {
      applyOutcome(RT.state, oc);
      rebuildAllianceLines();
      for (const m of oc.members) {
        const ids = citiesOfFaction(RT.state, m);
        await animateTintTo(ids, displayColorOf(RT.state, m), 800, signal);
      }
      renderLegend();
      break;
    }
    case 'ally_break': {
      applyOutcome(RT.state, oc);
      rebuildAllianceLines();
      syncCityColorsFromState();
      renderLegend();
      break;
    }
    case 'move_capital': {
      await animateMoveCapital(oc, signal);
      applyOutcome(RT.state, oc);
      RT.citiesDirty = true;
      renderLegend();
      break;
    }
    case 'ruler_change':
    case 'proclaim': {
      applyOutcome(RT.state, oc);
      break;
    }
  }
}

/* 迁都：星徽迁移 + 旧都降级 + 新都印章 */
async function animateMoveCapital(oc, signal) {
  const fromLoc = cityLoc(oc.from), toLoc = cityLoc(oc.to);
  const coords = Routes.buildPath(fromLoc, toLoc, []);
  const line = turf.lineString(coords);
  const len = turf.length(line, { units: 'kilometers' });
  await new Promise((resolve, reject) => {
    let t;
    const onAbort = () => { if (t) t.dead = true; Armies.clear(); reject({ cancelled: true }); };
    t = Tweens.add({ dur: 2400, ease: easeInOut, onUpdate: (p) => {
      const d = Math.max(0.001, len * p);
      const pos = turf.along(line, d, { units: 'kilometers' }).geometry.coordinates;
      Armies.set([{ icon: 'star-gold', lngLat: pos, bearing: 0 }]);
    }, onComplete: () => {
      if (signal) signal.removeEventListener('abort', onAbort);
      resolve();
    }, tag: 'event' });
    if (signal) signal.addEventListener('abort', onAbort, { once: true });
  });
  Armies.clear();
  const pt = RT.map.project(toLoc);
  const seal = $('seal');
  seal.style.left = pt.x + 'px';
  seal.style.top = pt.y + 'px';
  seal.classList.add('show');
  FX.spawnRing(toLoc, factionBaseColor(oc.faction), { r1: 120, dur: 1100 });
  setTimeout(() => seal.classList.remove('show'), 1100);
  await wait(700, signal);
}

/* ============================== 相机系统 ============================== */
function collectEventPoints(ev) {
  const st = RT.state; // 事件前状态
  const pts = [];
  for (const r of ev.routes || []) {
    const f = cityLoc(r.from); if (f) pts.push(f);
    if (r.toCity) pts.push(cityLoc(r.toCity));
    if (r.toPoint) pts.push(r.toPoint);
  }
  if (ev.battle) pts.push(ev.battle.location);
  if (ev.city) pts.push(cityLoc(ev.city));
  for (const oc of ev.outcomes || []) {
    if (oc.type === 'occupy') pts.push(cityLoc(oc.city));
    if (oc.type === 'move_capital') { pts.push(cityLoc(oc.from)); pts.push(cityLoc(oc.to)); }
    if (oc.type === 'conquer' || oc.type === 'submit')
      for (const cid of citiesOfFaction(st, oc.faction)) pts.push(cityLoc(cid));
    if (oc.type === 'rebel') (oc.cities || citiesOfFaction(st, oc.faction)).forEach((cid) => pts.push(cityLoc(cid)));
    if (oc.type === 'ally') [oc.leader, ...(oc.members || [])].forEach((f) => {
      const c = st.capitals.get(f); if (c) pts.push(cityLoc(c));
    });
  }
  if (!pts.length && ev.actors && ev.actors.primary) {
    const cap = st.capitals.get(ev.actors.primary);
    if (cap) pts.push(cityLoc(cap));
  }
  return pts.filter(Boolean);
}

function flyToEvent(ev, signal) {
  return new Promise((resolve) => {
    const pts = collectEventPoints(ev);
    if (!pts.length) return resolve();
    let w = 180, s = 90, e = -180, n = -90;
    for (const [x, y] of pts) { w = Math.min(w, x); s = Math.min(s, y); e = Math.max(e, x); n = Math.max(n, y); }
    const pad = Math.round(Math.min(window.innerWidth, window.innerHeight) * 0.18);
    const isDesktop = window.innerWidth > 768;
    const cam = RT.map.cameraForBounds([[w, s], [e, n]], {
      padding: { top: pad, bottom: pad + 110, left: pad, right: pad + (isDesktop ? 330 : 0) },
      maxZoom: 8.2,
    });
    const zoom = Math.min((ev.camera && ev.camera.zoom) || cam.zoom, 8.2);
    const pitch = (ev.camera && ev.camera.pitch) || 58;
    let done = false;
    const finish = () => { if (!done) { done = true; resolve(); } };
    RT.map.flyTo({ center: cam.center, zoom, pitch, duration: 1400 / RT.speed, essential: false });
    RT.map.once('moveend', finish);
    setTimeout(finish, 1700 / RT.speed + 250);
  });
}

/* ============================== 动画编排：十一类事件 ============================== */
function routeHandlesFor(ev) {
  return (ev.routes || []).map((r) => {
    const to = r.toCity ? cityLoc(r.toCity) : r.toPoint;
    const coords = Routes.buildPath(cityLoc(r.from), to, r.waypoints);
    return Routes.add(coords, factionBaseColor(r.faction), r.faction);
  });
}
async function marchPhase(ev, signal, { growMs = 1800, armyMs = 2200 } = {}) {
  const hs = routeHandlesFor(ev);
  if (!hs.length) return;
  Tweens.add({ dur: growMs, onUpdate: (p) => hs.forEach((h) => Routes.setProgress(h, p)), tag: 'event' });
  await armyTween(hs, armyMs, signal);
  Armies.clear();
  for (const h of hs) FX.spawnRing(h.coords[h.coords.length - 1], h.color, { r1: 70, dur: 700 });
  await wait(200, signal);
  await Routes.fadeOutAll(500);
}

const TYPE_ANIMATIONS = {
  /* 行军：路线生长 + 军旗行进 + 到达脉冲 */
  async march(ev, { signal }) {
    await marchPhase(ev, signal, { growMs: 1800, armyMs: 2200 });
    for (const oc of ev.outcomes || []) await applyOutcomeAnimated(oc, ev, signal);
  },

  /* 会战：双军同时抵达 → 接战特效 → 战果落地 */
  async battle(ev, { signal }) {
    const hs = routeHandlesFor(ev);
    Tweens.add({ dur: 2000, onUpdate: (p) => hs.forEach((h) => Routes.setProgress(h, p)), tag: 'event' });
    if (hs.length) await armyTween(hs, 2400, signal); // 归一化同时抵达
    Armies.clear();

    const loc = ev.battle.location;
    const atkColor = factionBaseColor(ev.actors.primary);
    const z0 = RT.map.getZoom();
    RT.map.easeTo({ zoom: z0 + 0.35, duration: 600 / RT.speed });
    const mapEl = $('map');
    mapEl.classList.add('shake');
    setTimeout(() => mapEl.classList.remove('shake'), 480);
    const flash = $('flash');
    flash.classList.remove('on'); void flash.offsetWidth; flash.classList.add('on');
    FX.spawnIcon(loc, 'swords', { size: 1.05, dur: 1900 });
    for (let i = 0; i < 3; i++) FX.spawnRing(loc, atkColor, { r1: 150, dur: 1100, delay: i * 240 });
    await wait(1500, signal);
    RT.map.easeTo({ zoom: z0, duration: 700 / RT.speed });
    await Routes.fadeOutAll(500);

    for (const oc of ev.outcomes || []) await applyOutcomeAnimated(oc, ev, signal);
  },

  /* 占领：如有路线先演行军，再落易主动效 */
  async occupy(ev, { signal }) {
    if ((ev.routes || []).length) await marchPhase(ev, signal, { growMs: 1600, armyMs: 2000 });
    for (const oc of ev.outcomes || []) await applyOutcomeAnimated(oc, ev, signal);
  },

  /* 灭国：行军（如有）→ 级联变色，都城最后 */
  async conquer(ev, { signal }) {
    if ((ev.routes || []).length) await marchPhase(ev, signal, { growMs: 1600, armyMs: 2000 });
    for (const oc of ev.outcomes || []) await applyOutcomeAnimated(oc, ev, signal);
  },

  /* 联盟：成员渐变为盟主浅色 + 盟约线 */
  async ally(ev, { signal }) {
    for (const oc of ev.outcomes || []) await applyOutcomeAnimated(oc, ev, signal);
  },

  /* 反叛：闪烁倒戈 */
  async rebel(ev, { signal }) {
    for (const oc of ev.outcomes || []) await applyOutcomeAnimated(oc, ev, signal);
  },

  /* 归附：无战事级联 */
  async submit(ev, { signal }) {
    for (const oc of ev.outcomes || []) await applyOutcomeAnimated(oc, ev, signal);
  },

  /* 迁都：星徽迁移 + 印章 */
  async move_capital(ev, { signal }) {
    for (const oc of ev.outcomes || []) await applyOutcomeAnimated(oc, ev, signal);
  },

  /* 继位：都城两轮金色脉冲 */
  async succeed(ev, { signal }) {
    const cap = RT.state.capitals.get(ev.actors.primary);
    if (cap) {
      const loc = cityLoc(cap);
      FX.spawnRing(loc, CONFIG.colors.gold, { r1: 110, dur: 1100 });
      FX.spawnRing(loc, CONFIG.colors.gold, { r1: 110, dur: 1100, delay: 500 });
      await wait(1400, signal);
    }
    for (const oc of ev.outcomes || []) await applyOutcomeAnimated(oc, ev, signal);
  },

  /* 称王/建国：王旗升起 + 主色圆环 */
  async proclaim(ev, { signal }) {
    const cap = RT.state.capitals.get(ev.actors.primary);
    if (cap) {
      const loc = cityLoc(cap);
      FX.spawnIcon(loc, `flag-${ev.actors.primary}`, { size: 1.15, dur: 2200 });
      FX.spawnRing(loc, factionBaseColor(ev.actors.primary), { r1: 160, dur: 1300 });
      FX.spawnRing(loc, factionBaseColor(ev.actors.primary), { r1: 160, dur: 1300, delay: 300 });
      await wait(1500, signal);
    }
    for (const oc of ev.outcomes || []) await applyOutcomeAnimated(oc, ev, signal);
  },

  /* 其他大事：相关城市墨色脉冲 */
  async other(ev, { signal }) {
    const loc = ev.city ? cityLoc(ev.city)
      : (RT.state.capitals.get(ev.actors.primary) ? cityLoc(RT.state.capitals.get(ev.actors.primary)) : null);
    if (loc) {
      FX.spawnRing(loc, CONFIG.colors.ink, { r1: 100, dur: 1000 });
      FX.spawnRing(loc, CONFIG.colors.ink, { r1: 100, dur: 1000, delay: 350 });
      await wait(900, signal);
    }
    for (const oc of ev.outcomes || []) await applyOutcomeAnimated(oc, ev, signal);
  },
};

/* ============================== 事件关联实体 ============================== */
function involvedCityIds(ev) {
  const ids = new Set();
  for (const r of ev.routes || []) { if (r.from) ids.add(r.from); if (r.toCity) ids.add(r.toCity); }
  if (ev.city) ids.add(ev.city);
  for (const oc of ev.outcomes || []) {
    if (oc.type === 'occupy') ids.add(oc.city);
    if (oc.type === 'move_capital') { ids.add(oc.from); ids.add(oc.to); }
    if (oc.type === 'rebel') (oc.cities || []).forEach((c) => ids.add(c));
  }
  return [...ids].filter((id) => DB.cities.has(id));
}
function involvedFactionIds(ev) {
  const ids = new Set();
  const a = ev.actors || {};
  if (a.primary) ids.add(a.primary);
  if (a.target) ids.add(a.target);
  (a.supporters || []).forEach((f) => ids.add(f));
  for (const oc of ev.outcomes || []) {
    for (const k of ['faction', 'by', 'leader']) if (oc[k]) ids.add(oc[k]);
    if (oc.type === 'occupy' || oc.type === 'submit' || oc.type === 'rebel') if (oc.to) ids.add(oc.to);
    (oc.members || []).forEach((f) => ids.add(f));
  }
  return [...ids].filter((id) => DB.factions.has(id));
}
function buildHaystack(ev) {
  const parts = [ev.title, ev.yearLabel, TYPE_META[ev.type].label, ev.category];
  for (const cid of involvedCityIds(ev)) parts.push(cityName(cid));
  for (const fid of involvedFactionIds(ev)) parts.push(factionName(fid));
  if (ev.battle) parts.push(ev.battle.name);
  return parts.join(' ').toLowerCase();
}

/* ============================== UI 模块 ============================== */
const FILT = { q: '', type: null, faction: '' };
const SPEEDS = [1, 2, 4, 0.5];

const UI = {
  bannerTimer: 0, cardTimer: 0,

  init() {
    this.buildChips();
    this.buildFactionSelect();
    this.renderList();
    this.buildTicks();

    $('search-input').addEventListener('input', (e) => { FILT.q = e.target.value.trim().toLowerCase(); this.renderList(); });
    $('btn-play').addEventListener('click', () => this.togglePlay());
    $('btn-prev').addEventListener('click', () => this.step(-1));
    $('btn-next').addEventListener('click', () => this.step(1));
    $('btn-speed').addEventListener('click', () => this.cycleSpeed());
    $('btn-auto').addEventListener('click', () => this.toggleAuto());
    $('btn-china').addEventListener('click', () => {
      const wide = window.innerWidth > 768;
      RT.map.fitBounds(CONFIG.chinaView.bounds, {
        pitch: CONFIG.chinaView.pitch, duration: 1600,
        padding: wide ? { top: 60, bottom: 150, left: 60, right: 380 } : 24,
      });
    });
    $('tl-bar').addEventListener('click', (e) => this.barClick(e));
    $('legend-toggle').addEventListener('click', () => $('legend').classList.toggle('collapsed'));
    $('panel-header').addEventListener('click', (e) => {
      if (window.innerWidth > 768) return;
      if (e.target.closest('input, select, .chip')) return;
      $('events-panel').classList.toggle('open');
    });

    const bindToggle = (id, fn) => {
      const e2 = $(id);
      e2.addEventListener('click', () => { e2.classList.toggle('on'); fn(e2.classList.contains('on')); });
    };
    bindToggle('tg-territory', (on) => { RT.territoryOn = on; rebuildTerritory(false); });
    bindToggle('tg-adm3', (on) => { RT.adm3On = on; RT.map.setLayoutProperty('adm3', 'visibility', on ? 'visible' : 'none'); });
    bindToggle('tg-labels', (on) => { RT.labelsOn = on; });

    window.addEventListener('keydown', (e) => {
      if (e.target && (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT')) return;
      if (e.code === 'Space') { e.preventDefault(); this.togglePlay(); }
      if (e.code === 'ArrowLeft') this.step(-1);
      if (e.code === 'ArrowRight') this.step(1);
    });
  },

  /* ---- 播放控制 ---- */
  togglePlay() {
    if (RT.locked) return;
    if (RT.playing) { Player.pause(); return; }
    const next = Math.min(RT.seq + 1, DB.events.length);
    if (RT.seq >= DB.events.length) { Player.play(1); return; }
    Player.play(next);
  },
  step(dir) {
    if (RT.locked) return;
    const cur = RT.busy ? RT.activeSeq : RT.seq;
    const target = cur + dir;
    if (target < 1 || target > DB.events.length) return;
    Player.play(target);
  },
  cycleSpeed() {
    const idx = SPEEDS.indexOf(RT.speed);
    RT.speed = SPEEDS[(idx + 1) % SPEEDS.length];
    $('btn-speed').textContent = RT.speed + '×';
  },
  toggleAuto() {
    if (RT.locked) return;
    RT.autoplay = !RT.autoplay;
    this.setAuto(RT.autoplay);
    if (RT.autoplay && !RT.busy && RT.seq < DB.events.length) Player.play(RT.seq + 1);
  },
  setAuto(on) { $('btn-auto').classList.toggle('on', on); },
  setPlayIcon(playing) { $('btn-play').textContent = playing ? '❚❚' : '▶'; },
  barClick(e) {
    if (RT.locked) return;
    const rect = $('tl-bar').getBoundingClientRect();
    const ratio = Math.min(Math.max((e.clientX - rect.left) / rect.width, 0), 1);
    const seq = Math.round(ratio * DB.events.length);
    if (seq === RT.seq) return;
    if (seq <= 0) { Player.pause(); jumpToState(0); return; }
    Player.play(seq);
  },

  /* ---- 类型 chips 与势力筛选 ---- */
  buildChips() {
    const box = $('type-chips');
    const all = el('button', 'chip on', '全部');
    all.addEventListener('click', () => { FILT.type = null; this.markChips(all); this.renderList(); });
    box.appendChild(all);
    for (const [type, meta] of Object.entries(TYPE_META)) {
      const c = el('button', 'chip', meta.label);
      c.addEventListener('click', () => { FILT.type = type; this.markChips(c); this.renderList(); });
      box.appendChild(c);
    }
  },
  markChips(active) { for (const c of $('type-chips').children) c.classList.toggle('on', c === active); },
  buildFactionSelect() {
    const sel = $('faction-select');
    for (const f of DB.factionList) {
      const o = el('option', '', f.name);
      o.value = f.id;
      sel.appendChild(o);
    }
    sel.addEventListener('change', () => { FILT.faction = sel.value; this.renderList(); });
  },

  /* ---- 事件列表 ---- */
  match(ev) {
    if (FILT.type && ev.type !== FILT.type) return false;
    if (FILT.faction && !involvedFactionIds(ev).includes(FILT.faction)) return false;
    if (FILT.q && !ev._hay.includes(FILT.q)) return false;
    return true;
  },
  renderList() {
    const list = $('events-list');
    list.innerHTML = '';
    let lastYear = null, shown = 0;
    for (const ev of DB.events) {
      if (!this.match(ev)) continue;
      shown++;
      if (ev.yearLabel !== lastYear) { lastYear = ev.yearLabel; list.appendChild(el('div', 'year-head', ev.yearLabel)); }
      const item = el('div', 'event-item');
      item.dataset.seq = ev.seq;
      const meta = TYPE_META[ev.type];
      const badge = el('span', 'ev-badge', meta.char);
      badge.style.background = meta.color;
      item.appendChild(el('span', 'ev-seq', String(ev.seq)));
      item.appendChild(badge);
      const main = el('div', 'ev-main');
      main.appendChild(el('div', 'ev-title', ev.title));
      main.appendChild(el('div', 'ev-meta', `${ev.yearLabel} · ${meta.label} · ${ev.category}`));
      item.appendChild(main);
      item.addEventListener('click', () => { if (!RT.locked) Player.play(ev.seq); });
      list.appendChild(item);
    }
    $('panel-sub').textContent = `${DB.events.length} 事 · 显示 ${shown}`;
    this.refreshListClasses();
  },
  refreshListClasses() {
    for (const item of $('events-list').querySelectorAll('.event-item')) {
      const seq = Number(item.dataset.seq);
      item.classList.toggle('done', seq <= RT.seq);
      item.classList.toggle('active', seq === RT.activeSeq && RT.busy);
    }
  },
  setActiveEvent(seq) {
    RT.activeSeq = seq;
    this.refreshListClasses();
    const item = $('events-list').querySelector(`.event-item[data-seq="${seq}"]`);
    if (item) item.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  },

  /* ---- 时间轴 ---- */
  buildTicks() {
    const box = $('tl-ticks');
    const N = DB.events.length;
    for (const ev of DB.events) {
      const t = el('div', 'tl-tick ' + (ev.category === '国际' ? 'intl' : 'dom'));
      if ((ev.outcomes || []).some((o) => o.type === 'conquer')) t.classList.add('big');
      t.style.left = ((ev.seq - 0.5) / N) * 100 + '%';
      t.title = `${ev.title} · ${ev.yearLabel}`;
      t.addEventListener('click', (e) => { e.stopPropagation(); if (!RT.locked) Player.play(ev.seq); });
      box.appendChild(t);
    }
  },
  updateTimeline() {
    const N = DB.events.length;
    $('tl-year').textContent = RT.seq > 0 ? DB.events[RT.seq - 1].yearLabel : '初始之局';
    $('tl-count').textContent = `第 ${RT.seq} / ${N} 事`;
    $('tl-progress').style.width = (RT.seq / N) * 100 + '%';
    const ticks = $('tl-ticks').children;
    for (let i = 0; i < ticks.length; i++) ticks[i].classList.toggle('cur', i + 1 === RT.activeSeq && RT.busy);
    this.refreshListClasses();
  },

  /* ---- 详情卡 ---- */
  showCard(ev) {
    const meta = TYPE_META[ev.type];
    const badges = $('dc-badges');
    badges.innerHTML = '';
    const b = el('span', 'actor-chip', meta.label);
    b.style.background = meta.color;
    badges.appendChild(b);
    const b2 = el('span', 'actor-chip', ev.category);
    b2.style.background = ev.category === '国际' ? '#8c6a3f' : '#4a5560';
    badges.appendChild(b2);

    $('dc-title').textContent = ev.title;
    $('dc-meta').textContent = `${ev.yearLabel} · ${meta.label}`;

    const actors = $('dc-actors');
    actors.innerHTML = '';
    const a = ev.actors || {};
    const mk = (fid, role) => {
      if (!fid || !DB.factions.has(fid)) return;
      const c = el('span', 'actor-chip', `${factionName(fid)} · ${role}`);
      c.style.background = factionBaseColor(fid);
      actors.appendChild(c);
    };
    mk(a.primary, '主动方');
    mk(a.target, '对方');
    (a.supporters || []).forEach((f) => mk(f, '协同'));

    $('dc-summary').textContent = ev.summary || '';
    const q = $('dc-quote');
    if (ev.quote && ev.quote.text) {
      q.style.display = 'block';
      q.innerHTML = '';
      q.appendChild(document.createTextNode(ev.quote.text));
      q.appendChild(el('span', 'qsrc', '—— ' + (ev.quote.source || '')));
    } else q.style.display = 'none';

    const cities = $('dc-cities');
    cities.innerHTML = '';
    for (const cid of involvedCityIds(ev)) {
      const c = el('button', 'city-link', cityName(cid));
      c.addEventListener('click', () => {
        const loc = cityLoc(cid);
        if (loc) RT.map.flyTo({ center: loc, zoom: 8, pitch: 52, duration: 1200 });
      });
      cities.appendChild(c);
    }
    $('detail-card').classList.add('show');
    clearTimeout(this.cardTimer);
  },
  hideCardSoon(ms) {
    clearTimeout(this.cardTimer);
    this.cardTimer = setTimeout(() => $('detail-card').classList.remove('show'), ms);
  },

  /* ---- 横幅 ---- */
  showBanner(title, sub, holdMs = 0) {
    $('banner-title').textContent = title;
    $('banner-sub').textContent = sub || '';
    $('banner').classList.add('show');
    clearTimeout(this.bannerTimer);
    if (holdMs > 0) this.hideBannerSoon(holdMs);
  },
  hideBannerSoon(ms) {
    clearTimeout(this.bannerTimer);
    this.bannerTimer = setTimeout(() => $('banner').classList.remove('show'), ms);
  },
};

/* ============================== 播放器 ============================== */
function cleanupVisuals() {
  Tweens.cancelTag('event');
  Tweens.cancelTag('route');
  Routes.clear();
  Armies.clear();
  FX.clear('event');
  $('seal').classList.remove('show');
}
function finalizeAfterEvent(ev) {
  RT.state = buildState(ev.seq);
  RT.seq = ev.seq;
  syncCityColorsFromState();
  rebuildCitiesSource();
  rebuildTerritory(true);
  rebuildAllianceLines();
  renderLegend();
  UI.updateTimeline();
}

const Player = {
  async play(seq) {
    if (RT.locked) return;
    this.cancel();
    seq = Math.max(1, Math.min(seq, DB.events.length));
    const myId = ++RT.playId;
    RT.busy = true; RT.playing = true; RT.activeSeq = seq;
    const ctrl = new AbortController();
    RT.abort = ctrl;
    const ev = DB.events[seq - 1];
    UI.setPlayIcon(true);
    UI.setActiveEvent(seq);
    try {
      jumpToState(seq - 1);                    // 瞬时回到事件之前
      await flyToEvent(ev, ctrl.signal);       // 镜头先到位
      throwIfAborted(ctrl.signal);
      UI.showCard(ev);
      UI.showBanner(ev.title, `${ev.yearLabel} · ${TYPE_META[ev.type].label}`, 0);
      await TYPE_ANIMATIONS[ev.type](ev, { signal: ctrl.signal });
      throwIfAborted(ctrl.signal);
      finalizeAfterEvent(ev);                  // 状态推进到 seq
      UI.hideBannerSoon(2800);
      UI.hideCardSoon(3600);
      if (myId !== RT.playId) return;
      RT.busy = false; RT.playing = false; UI.setPlayIcon(false);
      UI.refreshListClasses();
      if (RT.autoplay && seq < DB.events.length) {
        await wait(600, ctrl.signal);
        if (myId === RT.playId) this.play(seq + 1);
      }
    } catch (e) {
      if (!e || !e.cancelled) console.error('play error', e);
      if (myId !== RT.playId) return;
      cleanupVisuals();
      jumpToState(RT.seq);                     // 回到最后确认状态
      RT.busy = false; RT.playing = false; UI.setPlayIcon(false);
      UI.hideBannerSoon(0); UI.hideCardSoon(0);
      UI.refreshListClasses();
    }
  },
  cancel() {
    RT.playId++;
    if (RT.abort) RT.abort.abort();
    cleanupVisuals();
  },
  pause() {
    RT.autoplay = false; UI.setAuto(false);
    this.cancel();
    jumpToState(RT.seq);
    RT.busy = false; RT.playing = false; UI.setPlayIcon(false);
    UI.hideBannerSoon(0); UI.hideCardSoon(0);
    UI.refreshListClasses();
  },
};

/* ============================== 主循环 ============================== */
function frame() {
  Tweens.update(performance.now());
  if (RT.map && RT.state) {
    FX.flush();
    if (RT.citiesDirty) { rebuildCitiesSource(); RT.citiesDirty = false; }
    if (RT.armiesDirty) { Armies.flush(); RT.armiesDirty = false; }
    LabelLayer.update();
  }
  requestAnimationFrame(frame);
}

/* ============================== 启动 ============================== */
function setLoad(t) { $('load-status').textContent = t; }
function showErrors(list, note) {
  const box = $('error');
  box.classList.add('show');
  if (note) $('error-note').textContent = note;
  const ul = $('error-list');
  ul.innerHTML = '';
  for (const m of list) ul.appendChild(el('li', '', m));
}

async function boot() {
  const glOK = window.maplibregl && (
    typeof maplibregl.isSupported === 'function' ? maplibregl.isSupported()
      : (typeof maplibregl.supported === 'function' ? maplibregl.supported() : true));
  if (!glOK) {
    $('loading').classList.add('hide');
    showErrors(['当前浏览器不支持 WebGL，请使用最新版 Chrome / Edge / Safari。'], 'WebGL 不可用');
    return;
  }
  setLoad('载入势力、城市与事件…');
  let factions, cities, eventsJ;
  try {
    [factions, cities, eventsJ] = await Promise.all([
      fetchJSON(`${CONFIG.dataDir}/factions.json`),
      fetchJSON(`${CONFIG.dataDir}/cities.json`),
      fetchJSON(`${CONFIG.dataDir}/events.json`),
    ]);
  } catch (e) {
    $('loading').classList.add('hide');
    showErrors([String((e && e.message) || e)], '数据文件加载失败');
    return;
  }

  DB.factionList = factions;
  DB.factions = new Map(factions.map((f) => [f.id, f]));
  DB.cityList = cities;
  DB.cities = new Map(cities.map((c) => [c.id, c]));
  DB.events = [...eventsJ.events].sort((a, b) => a.seq - b.seq);
  for (const ev of DB.events) ev._hay = buildHaystack(ev);
  $('panel-sub').textContent = `${eventsJ.meta ? eventsJ.meta.title : '事件库'} · ${DB.events.length} 事`;

  setLoad('校验数据…');
  const errors = validateData(factions, cities, DB.events);
  if (errors.length) { showErrors(errors); RT.locked = true; }

  setLoad('铺陈山河…');
  RT.map = createMap();
  RT.map.on('error', (e) => {
    const msg = e && e.error && e.error.message;
    if (msg) console.warn('[map]', msg);
  });
  RT.map.on('load', () => {
    try {
      setupMapLayers(RT.map);
      LabelLayer.init();
      UI.init();
      jumpToState(0);
      requestAnimationFrame(frame);
    } catch (err) {
      console.error(err);
      showErrors([String((err && err.message) || err)], '地图初始化失败');
      RT.locked = true;
    }
    let hidden = false;
    const hideLoading = () => { if (!hidden) { hidden = true; $('loading').classList.add('hide'); } };
    RT.map.on('idle', hideLoading);
    setTimeout(hideLoading, 7000); // 兜底：瓦片慢也不卡死
  });
}

boot();
