// ============================================================================
// 山河裂变 · 3D 中国历史疆域战争地图
// ============================================================================
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { CSS2DRenderer, CSS2DObject } from 'three/addons/renderers/CSS2DRenderer.js';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { Line2 } from 'three/addons/lines/Line2.js';
import { LineGeometry } from 'three/addons/lines/LineGeometry.js';
import { LineMaterial } from 'three/addons/lines/LineMaterial.js';
import { LineSegments2 } from 'three/addons/lines/LineSegments2.js';
import { LineSegmentsGeometry } from 'three/addons/lines/LineSegmentsGeometry.js';

// ============================== 配置 ==============================
const CFG = {
  bbox: [73.0, 17.9, 135.1, 53.6],
  lon0: 104, lat0: 36,
  kx: 111.32 * Math.cos(36 * Math.PI / 180),
  kz: 110.94,
  maxH: 8316,
  exagg: 1.8,
  liftCounty: 0.9, liftLine: 1.0, liftBorder: 1.6, liftRoute: 2.2, liftRiver: 0.5,
  stateTexSize: 64,
  neutralColor: [26, 31, 38], neutralAlpha: 46,
  ownedAlpha: 217,
};

// ============================== 投影 ==============================
const projX = lon => (lon - CFG.lon0) * CFG.kx;
const projZ = lat => -(lat - CFG.lat0) * CFG.kz;
const proj = (lon, lat) => [projX(lon), projZ(lat)];

function geodesic(lon1, lat1, lon2, lat2, n = 48) {
  const toV = (lo, la) => {
    const φ = la * Math.PI / 180, λ = lo * Math.PI / 180;
    return [Math.cos(φ) * Math.cos(λ), Math.cos(φ) * Math.sin(λ), Math.sin(φ)];
  };
  const [ax, ay, az] = toV(lon1, lat1), [bx, by, bz] = toV(lon2, lat2);
  const dot = Math.min(1, Math.max(-1, ax * bx + ay * by + az * bz));
  const Ω = Math.acos(dot), pts = [];
  if (Ω < 1e-6) return [[lon1, lat1], [lon2, lat2]];
  for (let i = 0; i <= n; i++) {
    const t = i / n, s1 = Math.sin((1 - t) * Ω) / Math.sin(Ω), s2 = Math.sin(t * Ω) / Math.sin(Ω);
    const x = s1 * ax + s2 * bx, y = s1 * ay + s2 * by, z = s1 * az + s2 * bz;
    pts.push([Math.atan2(y, x) * 180 / Math.PI, Math.atan2(z, Math.hypot(x, y)) * 180 / Math.PI]);
  }
  return pts;
}

function hexToRgb(hex) {
  const h = hex.replace('#', '');
  return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)];
}

// ============================== GLSL 共享 ==============================
const GLSL_NOISE = /* glsl */`
vec2 hash2(vec2 p){
  p = vec2(dot(p, vec2(127.1,311.7)), dot(p, vec2(269.5,183.3)));
  return fract(sin(p)*43758.5453)*2.0-1.0;
}
float gradNoise(vec2 p){
  vec2 i = floor(p), f = fract(p);
  vec2 u = f*f*f*(f*(f*6.0-15.0)+10.0);
  return mix(mix(dot(hash2(i),f), dot(hash2(i+vec2(1,0)),f-vec2(1,0)), u.x),
             mix(dot(hash2(i+vec2(0,1)),f-vec2(0,1)), dot(hash2(i+vec2(1,1)),f-vec2(1,1)), u.x), u.y);
}
float fbm(vec2 p){
  return gradNoise(p) + 0.5*gradNoise(p*2.04+vec2(17.3,9.1)) + 0.25*gradNoise(p*4.11+vec2(42.7,28.6));
}`;
const GLSL_HEIGHT = /* glsl */`
uniform sampler2D uHeightmap;
uniform vec4 uBBox;
uniform float uMaxH, uExagg;
float heightMeters(vec2 lonlat){
  vec2 uv = (lonlat - uBBox.xy) / (uBBox.zw - uBBox.xy);
  vec4 t = texture2D(uHeightmap, uv);
  float enc = floor(t.r*255.0+0.5)*256.0 + floor(t.g*255.0+0.5);
  return enc / 65535.0 * uMaxH;
}
vec3 lonlatToWorld(vec2 lonlat, float lift){
  float x = (lonlat.x - ${CFG.lon0.toFixed(1)}) * ${CFG.kx.toFixed(4)};
  float z = -(lonlat.y - ${CFG.lat0.toFixed(1)}) * ${CFG.kz.toFixed(4)};
  return vec3(x, heightMeters(lonlat)*0.001*uExagg + lift, z);
}`;

// ============================== 全局状态 ==============================
let renderer, scene, camera, controls, composer, bloomPass, css2d;
let terrainMesh, countyMesh, countyLines, boundaryGroup, prevBoundaryGroup;
let citiesGroup, flagsGroup, routesGroup, arcsGroup, fxGroup, riversGroup, lakesGroup, coastGroup;
let oceanMat;
let uTime = 0, playing = true, autoplay = true, speed = 1, soloIdx = -1;
let exaggUniforms = [], lineMaterials = [];
let heightData = null;
let DATA = {};
let factions = [], factionIdx = {}, cities = [], cityById = {};
let timeline = null, events = [];
let snap = { owner: [], vassal: [], capitals: [], fallen: [], vassalMap: [] };
let stateTexPrev, stateTexNext;
let delayAttr;
let engine = { tweens: [], current: 0, busy: false, dwellUntil: 0, busyUntil: 0, flight: null, shakeT: 0, userHold: 0 };
let flags = {}, cityMeshes = {}, allyArcs = {};
let firstFrameShown = false;

// ============================== 加载 ==============================
const lStatus = t => { document.getElementById('l-status').textContent = t; };
function fatal(title, detail) {
  const l = document.getElementById('loader');
  l.classList.add('error');
  l.querySelector('.l-title').textContent = title;
  document.getElementById('l-detail').innerHTML = detail;
  l.classList.remove('fade');
}
async function fetchJSON(path) {
  const r = await fetch(path);
  if (!r.ok) throw new Error(`${path} · HTTP ${r.status}`);
  return r.json();
}
function loadImage(path) {
  return new Promise((res, rej) => {
    const img = new Image();
    img.onload = () => res(img);
    img.onerror = () => rej(new Error(`${path} 加载失败`));
    img.src = path;
  });
}
async function loadAll() {
  try {
    lStatus('加载地形…');
    DATA.terrain = await fetchJSON('data/terrain.json');
    CFG.maxH = DATA.terrain.max;
    const [hmImg, reliefImg] = await Promise.all([loadImage('data/heightmap.png'), loadImage('data/relief.jpg')]);
    DATA.heightmapImg = hmImg; DATA.reliefImg = reliefImg;
    decodeHeightCPU(hmImg);

    lStatus('烘焙疆域…');
    const binRes = await fetch('data/counties.bin');
    if (!binRes.ok) throw new Error('data/counties.bin · HTTP ' + binRes.status);
    DATA.countiesBin = await binRes.arrayBuffer();
    [DATA.countyLines, DATA.countyMeta, DATA.timeline, DATA.cities, DATA.factions] = await Promise.all([
      fetchJSON('data/county_lines.json'), fetchJSON('data/counties_meta.json'),
      fetchJSON('data/timeline.json'), fetchJSON('data/cities.json'), fetchJSON('data/factions.json'),
    ]);

    lStatus('竖立战旗…');
    [DATA.coastline, DATA.rivers, DATA.lakes] = await Promise.all([
      fetchJSON('data/geo/coastline.json'), fetchJSON('data/geo/rivers.json'), fetchJSON('data/geo/lakes.json'),
    ]);
    try { await Promise.race([document.fonts.load('700 200px "Noto Serif SC"', '夏商周'), new Promise(r => setTimeout(r, 3500))]); } catch (e) { /* 字体回退 */ }
  } catch (e) {
    console.error(e);
    fatal('数据加载失败', `缺失或损坏：<b>${e.message}</b><br/>请先运行 <code>tools/preprocess.py</code> 生成 data/ 目录。`);
    throw e;
  }
}
function decodeHeightCPU(img) {
  const c = document.createElement('canvas');
  c.width = img.width; c.height = img.height;
  const ctx = c.getContext('2d', { willReadFrequently: true });
  ctx.drawImage(img, 0, 0);
  const d = ctx.getImageData(0, 0, c.width, c.height).data;
  const n = c.width * c.height;
  heightData = new Float32Array(n);
  for (let i = 0; i < n; i++) heightData[i] = (d[i * 4] * 256 + d[i * 4 + 1]) / 65535 * CFG.maxH;
  heightData._w = c.width; heightData._h = c.height;
}
function heightAt(lon, lat) {
  const [x0, y0, x1, y1] = CFG.bbox, w = heightData._w, h = heightData._h;
  let u = (lon - x0) / (x1 - x0) * w - 0.5, v = (y1 - lat) / (y1 - y0) * h - 0.5;
  u = Math.min(Math.max(u, 0), w - 1.001); v = Math.min(Math.max(v, 0), h - 1.001);
  const iu = Math.floor(u), iv = Math.floor(v), fu = u - iu, fv = v - iv;
  const s = (x, y) => heightData[Math.min(y, h - 1) * w + Math.min(x, w - 1)];
  return s(iu, iv) * (1 - fu) * (1 - fv) + s(iu + 1, iv) * fu * (1 - fv)
       + s(iu, iv + 1) * (1 - fu) * fv + s(iu + 1, iv + 1) * fu * fv;
}
const worldY = (lon, lat, lift = 0) => heightAt(lon, lat) * 0.001 * CFG.exagg + lift;

// ============================== 快照预计算 ==============================
function buildSnapshots() {
  timeline = DATA.timeline;
  events = timeline.events;
  factions = DATA.factions;
  factions.forEach((f, i) => factionIdx[f.id] = i);
  cities = DATA.cities;
  cities.forEach(c => cityById[c.id] = c);
  const NC = DATA.countyMeta.length;
  const n = events.length + 1;
  const curO = new Int16Array(NC).fill(-1), curV = new Int16Array(NC).fill(-1);
  for (const s of timeline.initial.states) {
    curO[s.county_idx] = factionIdx[s.owner] ?? -1;
    curV[s.county_idx] = s.vassal_of ? (factionIdx[s.vassal_of] ?? -1) : -1;
  }
  snap.owner = [curO.slice()]; snap.vassal = [curV.slice()];
  snap.capitals = [timeline.initial.capitals];
  snap.fallen = [[]]; snap.vassalMap = [{}];
  const vmap = {};
  for (let k = 1; k < n; k++) {
    const ev = events[k - 1];
    for (const ch of ev.changes) {
      curO[ch.county_idx] = factionIdx[ch.owner] ?? -1;
      curV[ch.county_idx] = ch.vassal_of ? (factionIdx[ch.vassal_of] ?? -1) : -1;
    }
    for (const vs of ev.vassals_set) vmap[vs.faction] = vs.suzerain;
    for (const vc of ev.vassals_clear) delete vmap[vc];
    for (const oc of ev.outcomes) if (oc.type === 'conquer') delete vmap[oc.faction];
    snap.owner[k] = curO.slice(); snap.vassal[k] = curV.slice();
    snap.capitals[k] = ev.capitals;
    snap.fallen[k] = ev.fallen;
    snap.vassalMap[k] = { ...vmap };
  }
  const meta = new Array(NC);
  for (const m of DATA.countyMeta) meta[m.county_idx] = m;
  DATA.countyMetaArr = meta;
}

// ============================== 渲染器 ==============================
function initRenderer() {
  if (!window.WebGL2RenderingContext) {
    fatal('WebGL 不可用', '你的浏览器不支持 WebGL2。<br/>推荐使用最新版 Chrome / Edge / Firefox。');
    return false;
  }
  renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'high-performance' });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.setSize(innerWidth, innerHeight);
  renderer.toneMapping = THREE.NeutralToneMapping;
  renderer.toneMappingExposure = 1.15;
  renderer.domElement.id = 'scene-canvas';
  document.body.appendChild(renderer.domElement);

  scene = new THREE.Scene();
  scene.background = new THREE.Color('#0b0d10');
  camera = new THREE.PerspectiveCamera(45, innerWidth / innerHeight, 1, 20000);
  camera.position.set(0, 2650, 2350);

  controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true; controls.dampingFactor = 0.08;
  controls.minDistance = 120; controls.maxDistance = 4200;
  controls.maxPolarAngle = Math.PI * 0.49;
  controls.target.set(0, 0, 0);
  controls.autoRotate = true; controls.autoRotateSpeed = 0.15;
  controls.mouseButtons = { LEFT: THREE.MOUSE.PAN, MIDDLE: THREE.MOUSE.DOLLY, RIGHT: THREE.MOUSE.ROTATE };
  controls.addEventListener('start', () => { engine.flight = null; engine.userHold = uTime; });

  css2d = new CSS2DRenderer();
  css2d.setSize(innerWidth, innerHeight);
  css2d.domElement.style.cssText = 'position:fixed;inset:0;pointer-events:none;z-index:4;';
  document.body.appendChild(css2d.domElement);

  composer = new EffectComposer(renderer);
  composer.addPass(new RenderPass(scene, camera));
  bloomPass = new UnrealBloomPass(new THREE.Vector2(innerWidth, innerHeight), 0.22, 0.4, 1.0);
  composer.addPass(bloomPass);
  composer.addPass(new OutputPass());
  return true;
}

let sunLight, hemiLight;
function initLights() {
  sunLight = new THREE.DirectionalLight(0xffffff, 1.6);
  scene.add(sunLight); scene.add(sunLight.target);
  hemiLight = new THREE.HemisphereLight(0x8fa3c0, 0x2a241c, 0.55);
  scene.add(hemiLight);
}

// ============================== 地形 ==============================
const terrainUniforms = {
  uHeightmap: { value: null }, uRelief: { value: null },
  uBBox: { value: new THREE.Vector4(...CFG.bbox) },
  uMaxH: { value: CFG.maxH }, uExagg: { value: CFG.exagg },
  uSunDir: { value: new THREE.Vector3(0.3, 0.6, -0.7) },
  uSunColor: { value: new THREE.Color(1, 0.95, 0.85) },
  uAmbient: { value: 0.62 },
  uTexel: { value: new THREE.Vector2(1 / 2048, 1 / 1152) },
};
let heightTex;
function makeHeightTexture() {
  heightTex = new THREE.Texture(DATA.heightmapImg);
  heightTex.needsUpdate = true;
  heightTex.minFilter = THREE.LinearFilter; heightTex.magFilter = THREE.LinearFilter;
  heightTex.wrapS = heightTex.wrapT = THREE.ClampToEdgeWrapping;
  heightTex.generateMipmaps = false;
  return heightTex;
}
function buildTerrain() {
  const w = (CFG.bbox[2] - CFG.bbox[0]) * CFG.kx;
  const h = (CFG.bbox[3] - CFG.bbox[1]) * CFG.kz;
  const geo = new THREE.PlaneGeometry(w, h, 512, 288);
  geo.rotateX(-Math.PI / 2);
  // PlaneGeometry: uv(0,1) 在左上（minLon,maxLat），uv(1,0) 在右下
  const reliefTex = new THREE.Texture(DATA.reliefImg);
  reliefTex.needsUpdate = true; reliefTex.colorSpace = THREE.SRGBColorSpace;
  reliefTex.wrapS = reliefTex.wrapT = THREE.ClampToEdgeWrapping;
  reliefTex.flipY = true;
  terrainUniforms.uHeightmap.value = makeHeightTexture();
  terrainUniforms.uRelief.value = reliefTex;
  terrainUniforms.uMaxH.value = CFG.maxH;
  exaggUniforms.push(terrainUniforms);

  const mat = new THREE.ShaderMaterial({
    uniforms: terrainUniforms,
    vertexShader: /* glsl */`
      varying vec2 vUv;
      ${GLSL_HEIGHT}
      void main(){
        vUv = uv;
        vec2 lonlat = vec2(uBBox.x + vUv.x*(uBBox.z-uBBox.x), uBBox.y + vUv.y*(uBBox.w-uBBox.y));
        gl_Position = projectionMatrix * modelViewMatrix * vec4(lonlatToWorld(lonlat, 0.0), 1.0);
      }`,
    fragmentShader: /* glsl */`
      varying vec2 vUv;
      uniform sampler2D uRelief;
      uniform vec3 uSunDir, uSunColor;
      uniform float uAmbient;
      uniform vec2 uTexel;
      ${GLSL_HEIGHT}
      void main(){
        vec2 lonlat = vec2(uBBox.x + vUv.x*(uBBox.z-uBBox.x), uBBox.y + vUv.y*(uBBox.w-uBBox.y));
        float dx = (uBBox.z-uBBox.x) * uTexel.x;
        float dy = (uBBox.w-uBBox.y) * uTexel.y;
        float hC = heightMeters(lonlat);
        float hX = heightMeters(lonlat+vec2(dx,0.0));
        float hZ = heightMeters(lonlat+vec2(0.0,dy));
        float sx = ${CFG.kx.toFixed(2)}*1000.0*dx;
        float sz = ${CFG.kz.toFixed(2)}*1000.0*dy;
        vec3 N = normalize(vec3(-(hX-hC)*uExagg/sx, 1.0, -(hZ-hC)*uExagg/sz));
        // 低海拔（海洋/平原水面）：平坦法线，消除摩尔纹
        if (hC < 2.0) N = vec3(0.0, 1.0, 0.0);
        vec3 relief = pow(texture2D(uRelief, vUv).rgb, vec3(0.85));
        float lit = max(dot(N, normalize(uSunDir)), 0.0);
        vec3 col = relief * (uAmbient + 1.25*lit) * uSunColor;
        // 近海水面与陆地水体统一为深色水域（完全覆盖，消除 relief 噪点）
        float water = 1.0 - smoothstep(0.0, 2.0, hC);
        col = mix(col, vec3(0.030, 0.052, 0.068), water);
        float ridge = smoothstep(0.55, 0.95, hC/uMaxH);
        col += ridge * lit * vec3(0.10,0.10,0.11);
        gl_FragColor = vec4(col, 1.0);
      }`,
  });
  terrainMesh = new THREE.Mesh(geo, mat);
  terrainMesh.frustumCulled = false;
  scene.add(terrainMesh);

  // 裙边
  const verts = [], idx = [];
  const N = 128, [x0, y0, x1, y1] = CFG.bbox;
  const segs = [];
  for (let i = 0; i < N; i++) {
    const t0 = i / N, t1 = (i + 1) / N;
    segs.push([[x0+t0*(x1-x0), y0],[x0+t1*(x1-x0), y0]]);
    segs.push([[x0+t0*(x1-x0), y1],[x0+t1*(x1-x0), y1]]);
    segs.push([[x0, y0+t0*(y1-y0)],[x0, y0+t1*(y1-y0)]]);
    segs.push([[x1, y0+t0*(y1-y0)],[x1, y0+t1*(y1-y0)]]);
  }
  let vi = 0;
  const drop = 150;
  for (const [a, b] of segs) {
    const ya = heightAt(a[0],a[1])*0.001*CFG.exagg, yb = heightAt(b[0],b[1])*0.001*CFG.exagg;
    verts.push(projX(a[0]),ya,projZ(a[1]), projX(b[0]),yb,projZ(b[1]),
               projX(a[0]),ya-drop,projZ(a[1]), projX(b[0]),yb-drop,projZ(b[1]));
    idx.push(vi,vi+2,vi+1, vi+1,vi+2,vi+3);
    vi += 4;
  }
  const sg = new THREE.BufferGeometry();
  sg.setAttribute('position', new THREE.Float32BufferAttribute(verts, 3));
  sg.setIndex(idx);
  const skirt = new THREE.Mesh(sg, new THREE.MeshBasicMaterial({ color: 0x0b0d10, side: THREE.DoubleSide }));
  skirt.frustumCulled = false;
  scene.add(skirt);
}

// ============================== 海洋 ==============================
function buildOcean() {
  const geo = new THREE.PlaneGeometry(20000, 20000);
  geo.rotateX(-Math.PI / 2);
  oceanMat = new THREE.ShaderMaterial({
    uniforms: { uTime: { value: 0 } },
    vertexShader: `void main(){ gl_Position = projectionMatrix*modelViewMatrix*vec4(position,1.0); }`,
    fragmentShader: /* glsl */`
      uniform float uTime;
      ${GLSL_NOISE}
      void main(){
        vec3 base = vec3(0.012, 0.028, 0.040);
        float n = fbm(gl_FragCoord.xy*0.008 + vec2(uTime*0.03, uTime*0.02));
        base += vec3(0.004, 0.008, 0.010) * (n*0.5+0.5);
        gl_FragColor = vec4(base, 1.0);
      }`,
  });
  const m = new THREE.Mesh(geo, oceanMat);
  m.position.y = 0.02;
  m.renderOrder = -2;
  scene.add(m);
}

// ============================== 疆域：状态纹理 + 县面 ==============================
const TEXN = CFG.stateTexSize;
function makeStateTex() {
  const t = new THREE.DataTexture(new Uint8Array(TEXN * TEXN * 4), TEXN, TEXN, THREE.RGBAFormat);
  t.minFilter = t.magFilter = THREE.NearestFilter;
  t.needsUpdate = true;
  return t;
}
function countyColor(oIdx, vIdx) {
  if (oIdx < 0) return [...CFG.neutralColor, CFG.neutralAlpha];
  if (vIdx >= 0 && vIdx !== oIdx) return [...hexToRgb(factions[vIdx].vassal_color), CFG.ownedAlpha];
  return [...hexToRgb(factions[oIdx].color), CFG.ownedAlpha];
}
function writeStateTex(tex, ownerTex, si) {
  const o = snap.owner[si], v = snap.vassal[si];
  const d = tex.image.data, od = ownerTex.image.data;
  for (let i = 0; i < o.length; i++) {
    const c = countyColor(o[i], v[i]);
    d[i*4]=c[0]; d[i*4+1]=c[1]; d[i*4+2]=c[2]; d[i*4+3]=c[3];
    od[i*4] = o[i] < 0 ? 0 : o[i] + 1; od[i*4+3] = 255;
  }
  tex.needsUpdate = true; ownerTex.needsUpdate = true;
}

const countyUniforms = {
  uHeightmap: { value: null }, uBBox: { value: new THREE.Vector4(...CFG.bbox) },
  uMaxH: { value: CFG.maxH }, uExagg: { value: CFG.exagg },
  uStatePrev: { value: null }, uStateNext: { value: null },
  uOwnerPrev: { value: null }, uOwnerNext: { value: null },
  uProgress: { value: 1 }, uSolo: { value: -1 },
};
function buildCounties() {
  const buf = DATA.countiesBin;
  const dv = new DataView(buf);
  const hlen = dv.getUint32(0, true);
  const header = JSON.parse(new TextDecoder().decode(new Uint8Array(buf, 4, hlen)));
  let off = 4 + hlen;
  const nV = header.count;
  const pos = new Float32Array(buf.slice(off, off + nV * 8)); off += nV * 8;
  const cidx = new Uint16Array(buf.slice(off, off + nV * 2)); off += nV * 2;
  const indices = new Uint32Array(buf.slice(off));

  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(pos, 2));
  geo.setAttribute('aCountyIdx', new THREE.BufferAttribute(Float32Array.from(cidx), 1));
  geo.setAttribute('aDelay', new THREE.BufferAttribute(new Float32Array(nV), 1));
  geo.setIndex(new THREE.BufferAttribute(indices, 1));
  geo.boundingSphere = new THREE.Sphere(new THREE.Vector3(), 8000); // position 为 2 分量经纬度，跳过 NaN 包围球计算
  delayAttr = geo.getAttribute('aDelay');

  stateTexPrev = makeStateTex(); stateTexNext = makeStateTex();
  const ownerP = makeStateTex(), ownerN = makeStateTex();
  countyUniforms.uHeightmap.value = heightTex;
  countyUniforms.uMaxH.value = CFG.maxH;
  countyUniforms.uStatePrev.value = stateTexPrev;
  countyUniforms.uStateNext.value = stateTexNext;
  countyUniforms.uOwnerPrev.value = ownerP;
  countyUniforms.uOwnerNext.value = ownerN;
  exaggUniforms.push(countyUniforms);

  const mat = new THREE.ShaderMaterial({
    uniforms: countyUniforms,
    transparent: true, depthWrite: false,
    polygonOffset: true, polygonOffsetFactor: -1, polygonOffsetUnits: -1,
    vertexShader: /* glsl */`
      attribute float aCountyIdx, aDelay;
      uniform sampler2D uStatePrev, uStateNext, uOwnerPrev, uOwnerNext;
      uniform float uProgress;
      varying vec4 vColor; varying float vOwner;
      ${GLSL_HEIGHT}
      vec4 readTex(sampler2D t, float idx){
        return texture2D(t, vec2((mod(idx,${TEXN}.0)+0.5)/${TEXN}.0, (floor(idx/${TEXN}.0)+0.5)/${TEXN}.0));
      }
      void main(){
        vec3 p = lonlatToWorld(position.xy, ${CFG.liftCounty.toFixed(2)});
        vec4 cP = readTex(uStatePrev, aCountyIdx);
        vec4 cN = readTex(uStateNext, aCountyIdx);
        float lt = smoothstep(aDelay, aDelay+0.35, uProgress);
        vColor = mix(cP, cN, lt);
        vOwner = mix(readTex(uOwnerPrev, aCountyIdx).r, readTex(uOwnerNext, aCountyIdx).r, step(0.5, lt));
        gl_Position = projectionMatrix * modelViewMatrix * vec4(p, 1.0);
      }`,
    fragmentShader: /* glsl */`
      varying vec4 vColor; varying float vOwner;
      uniform float uSolo;
      void main(){
        float alpha = vColor.a;
        if (uSolo >= 0.0 && vColor.a > 0.4 && abs(vOwner*255.0-1.0-uSolo) > 0.5) alpha *= 0.15;
        // 颜色按 sRGB 写入纹理，此处转线性让 ACES 输出后还原原色
        gl_FragColor = vec4(pow(vColor.rgb, vec3(2.2)), alpha);
      }`,
  });
  countyMesh = new THREE.Mesh(geo, mat);
  countyMesh.frustumCulled = false;
  countyMesh.renderOrder = 1;
  scene.add(countyMesh);
}

// ============================== 县界线 ==============================
const countyLineUniforms = {
  uHeightmap: { value: null }, uBBox: { value: new THREE.Vector4(...CFG.bbox) },
  uMaxH: { value: CFG.maxH }, uExagg: { value: CFG.exagg }, uCamDist: { value: 3000 },
};
function buildCountyLines() {
  const rings = DATA.countyLines;
  let total = 0;
  for (const r of rings) total += (r.length - 1) * 2;
  const pos = new Float32Array(total * 2);
  let o = 0;
  for (const ring of rings) {
    for (let i = 0; i < ring.length - 1; i++) {
      pos[o++] = ring[i][0]; pos[o++] = ring[i][1];
      pos[o++] = ring[i+1][0]; pos[o++] = ring[i+1][1];
    }
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(pos, 2));
  geo.boundingSphere = new THREE.Sphere(new THREE.Vector3(), 8000); // position 为 2 分量经纬度，跳过 NaN 包围球计算
  countyLineUniforms.uHeightmap.value = heightTex;
  countyLineUniforms.uMaxH.value = CFG.maxH;
  exaggUniforms.push(countyLineUniforms);
  const mat = new THREE.ShaderMaterial({
    uniforms: countyLineUniforms,
    transparent: true, depthWrite: false,
    vertexShader: /* glsl */`
      ${GLSL_HEIGHT}
      void main(){
        gl_Position = projectionMatrix * modelViewMatrix * vec4(lonlatToWorld(position.xy, ${CFG.liftLine.toFixed(2)}), 1.0);
      }`,
    fragmentShader: /* glsl */`
      uniform float uCamDist;
      void main(){
        gl_FragColor = vec4(0.055, 0.067, 0.086, mix(0.35, 0.10, smoothstep(1200.0, 2500.0, uCamDist)));
      }`,
  });
  countyLines = new THREE.LineSegments(geo, mat);
  countyLines.frustumCulled = false;
  countyLines.renderOrder = 2;
  scene.add(countyLines);
}

// ============================== 水系 ==============================
function buildHydro() {
  coastGroup = new THREE.Group();
  const coastMat = new THREE.LineBasicMaterial({ color: 0x2a3f48, transparent: true, opacity: 0.45 });
  for (const f of DATA.coastline.features) {
    const cs = f.geometry.type === 'LineString' ? [f.geometry.coordinates] : f.geometry.coordinates;
    for (const line of cs) {
      if (!line || line.length < 2) continue;
      const v = [];
      for (const [lo, la] of line) v.push(projX(lo), 0.35, projZ(la));
      const g = new THREE.BufferGeometry();
      g.setAttribute('position', new THREE.Float32BufferAttribute(v, 3));
      coastGroup.add(new THREE.Line(g, coastMat));
    }
  }
  scene.add(coastGroup);
  riversGroup = new THREE.Group(); scene.add(riversGroup);
  rebuildRivers();
  lakesGroup = new THREE.Group();
  const lakeMat = new THREE.MeshBasicMaterial({ color: 0x16303e, transparent: true, opacity: 0.8, depthWrite: false });
  for (const f of DATA.lakes.features) {
    const polys = f.geometry.type === 'Polygon' ? [f.geometry.coordinates] : f.geometry.coordinates;
    for (const poly of polys) {
      if (!poly[0] || poly[0].length < 3) continue;
      let cx = 0, cy = 0;
      for (const [lo, la] of poly[0]) { cx += lo; cy += la; }
      cx /= poly[0].length; cy /= poly[0].length;
      const shape = new THREE.Shape(poly[0].map(([lo, la]) => new THREE.Vector2(projX(lo), projZ(la))));
      const g = new THREE.ShapeGeometry(shape);
      g.rotateX(Math.PI / 2);
      const mesh = new THREE.Mesh(g, lakeMat);
      mesh.position.y = Math.max(worldY(cx, cy, 0), 0.2);
      mesh.renderOrder = 1;
      lakesGroup.add(mesh);
    }
  }
  scene.add(lakesGroup);
}
function rebuildRivers() {
  riversGroup.clear();
  const major = /yellow|yangtze|黄河|长江/i;
  const matN = new THREE.LineBasicMaterial({ color: 0x6a90b0, transparent: true, opacity: 0.28 });
  const matM = new THREE.LineBasicMaterial({ color: 0x8fb8d9, transparent: true, opacity: 0.55 });
  for (const f of DATA.rivers.features) {
    const nm = (f.properties && (f.properties.name_zh || f.properties.name)) || '';
    const cs = f.geometry.type === 'LineString' ? [f.geometry.coordinates] : f.geometry.coordinates;
    for (const line of cs) {
      if (!line || line.length < 2) continue;
      const v = [];
      for (const [lo, la] of line) {
        v.push(projX(lo), Math.max(heightAt(lo, la) * 0.001 * CFG.exagg, 0.02) + CFG.liftRiver, projZ(la));
      }
      const g = new THREE.BufferGeometry();
      g.setAttribute('position', new THREE.Float32BufferAttribute(v, 3));
      riversGroup.add(new THREE.Line(g, major.test(nm) ? matM : matN));
    }
  }
}

// ============================== 势力外轮廓 ==============================
const boundaryCache = {};
async function loadBoundaries(id) {
  if (!boundaryCache[id]) boundaryCache[id] = await fetchJSON(`data/boundaries/${id}.json`);
  return boundaryCache[id];
}
function ringsToSegs(rings, color, lift, linewidth, dashed) {
  const positions = [];
  for (const ring of rings) {
    for (let i = 0; i < ring.length - 1; i++) {
      const [lo1, la1] = ring[i], [lo2, la2] = ring[i + 1];
      positions.push(projX(lo1), worldY(lo1, la1, lift), projZ(la1));
      positions.push(projX(lo2), worldY(lo2, la2, lift), projZ(la2));
    }
  }
  if (!positions.length) return null;
  const g = new LineSegmentsGeometry();
  g.setPositions(positions);
  const m = new LineMaterial({
    color: new THREE.Color(color).multiplyScalar(1.6), linewidth, transparent: true, opacity: 1.0,
    depthWrite: false,
    dashed: !!dashed, dashSize: dashed ? 4 : 1, gapSize: dashed ? 3 : 0,
  });
  m.resolution.set(innerWidth, innerHeight);
  lineMaterials.push(m);
  const seg = new LineSegments2(g, m);
  if (dashed) seg.computeLineDistances();
  seg.frustumCulled = false;
  seg.renderOrder = 3;
  return seg;
}
function buildBoundaryGroup(data, vmap) {
  const grp = new THREE.Group();
  for (const [fid, rings] of Object.entries(data.bloc || {})) {
    const f = factions[factionIdx[fid]];
    if (!f) continue;
    const seg = ringsToSegs(rings, f.color, CFG.liftBorder, 2.5, false);
    if (seg) grp.add(seg);
  }
  for (const [fid, suz] of Object.entries(vmap || {})) {
    const rings = (data.owner || {})[fid];
    const sf = factions[factionIdx[suz]];
    if (!rings || !sf) continue;
    const seg = ringsToSegs(rings, sf.color, CFG.liftBorder + 0.3, 1.5, true);
    if (seg) grp.add(seg);
  }
  return grp;
}
async function showBoundaries(id, si, instant = false) {
  const data = await loadBoundaries(id);
  const grp = buildBoundaryGroup(data, snap.vassalMap[si]);
  if (prevBoundaryGroup) { scene.remove(prevBoundaryGroup); disposeGroup(prevBoundaryGroup); }
  prevBoundaryGroup = boundaryGroup;
  boundaryGroup = grp;
  scene.add(grp);
  if (!instant && prevBoundaryGroup) {
    const oldG = prevBoundaryGroup;
    setGroupOpacity(oldG, 1); setGroupOpacity(grp, 0);
    addTween(0.6, k => setGroupOpacity(oldG, 1 - k), () => {
      scene.remove(oldG); disposeGroup(oldG);
      if (prevBoundaryGroup === oldG) prevBoundaryGroup = null;
    });
    addTween(0.6, k => setGroupOpacity(grp, k), null);
  }
}
function setGroupOpacity(grp, op) { grp.traverse(o => { if (o.material) o.material.opacity = op * 0.95; }); }
function disposeGroup(grp) {
  grp.traverse(o => {
    if (o.geometry) o.geometry.dispose();
    if (o.material) {
      const i = lineMaterials.indexOf(o.material); if (i >= 0) lineMaterials.splice(i, 1);
      o.material.dispose();
    }
  });
}

// ============================== 城市 ==============================
function cityColor(c) {
  const oIdx = c._ownerIdx ?? factionIdx[c.owner];
  const vIdx = c._vassalIdx ?? -1;
  if (vIdx >= 0 && vIdx !== oIdx) return factions[vIdx].vassal_color;
  return factions[oIdx] ? factions[oIdx].color : '#888888';
}
function buildCities() {
  citiesGroup = new THREE.Group();
  for (const c of cities) {
    const [x, z] = proj(c.location[0], c.location[1]);
    const holder = new THREE.Group();
    holder.position.set(x, worldY(c.location[0], c.location[1], 1.1), z);
    let ring = null;
    if (c.tier === 1) {
      ring = new THREE.Mesh(new THREE.RingGeometry(3.4, 4.6, 40),
        new THREE.MeshBasicMaterial({ color: 0xf2ead8, transparent: true, opacity: 0.9, side: THREE.DoubleSide, depthWrite: false }));
      ring.rotation.x = -Math.PI / 2;
      holder.add(ring);
    }
    const r = c.tier === 1 ? 2.6 : c.tier === 2 ? 2.5 : 1.5;
    const disc = new THREE.Mesh(new THREE.CircleGeometry(r, 24),
      new THREE.MeshBasicMaterial({ color: cityColor(c), depthWrite: false }));
    disc.rotation.x = -Math.PI / 2;
    disc.renderOrder = 4;
    holder.add(disc);
    const div = document.createElement('div');
    div.className = `city-label t${c.tier}`;
    div.textContent = c.name;
    const label = new CSS2DObject(div);
    label.position.set(0, c.tier === 1 ? 3 : 2, 0);
    holder.add(label);
    citiesGroup.add(holder);
    cityMeshes[c.id] = { holder, disc, ring, labelDiv: div, city: c };
  }
  scene.add(citiesGroup);
}
function updateCityColors() {
  for (const c of cities) cityMeshes[c.id].disc.material.color.set(cityColor(c));
}
function updateCityLabelVisibility() {
  const d = camera.position.distanceTo(controls.target);
  for (const id in cityMeshes) {
    const { labelDiv, city } = cityMeshes[id];
    labelDiv.style.display = city.tier === 1 ? '' : city.tier === 2 ? (d < 1800 ? '' : 'none') : (d < 700 ? '' : 'none');
  }
}

// ============================== 3D 战旗 ==============================
function makeFlagTexture(faction) {
  const c = document.createElement('canvas');
  c.width = 512; c.height = 336;
  const x = c.getContext('2d');
  const [r, g, b] = hexToRgb(faction.color);
  x.fillStyle = `rgb(${r},${g},${b})`;
  x.fillRect(0, 0, 512, 336);
  for (let i = 0; i < 900; i++) {
    x.fillStyle = `rgba(0,0,0,${(Math.random() * 0.08).toFixed(3)})`;
    x.fillRect(Math.random() * 512, Math.random() * 336, 2, 2);
  }
  x.strokeStyle = `rgb(${r * 0.55 | 0},${g * 0.55 | 0},${b * 0.55 | 0})`;
  x.lineWidth = 18; x.strokeRect(12, 12, 488, 312);
  x.strokeStyle = 'rgba(242,234,216,0.35)';
  x.lineWidth = 3; x.strokeRect(30, 30, 452, 276);
  x.fillStyle = '#f2ead8';
  x.font = '700 220px "Noto Serif SC", "Songti SC", "SimSun", serif';
  x.textAlign = 'center'; x.textBaseline = 'middle';
  x.shadowColor = 'rgba(0,0,0,0.45)'; x.shadowBlur = 10; x.shadowOffsetY = 5;
  x.fillText(faction.name.slice(0, 1), 256, 178);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = renderer.capabilities.getMaxAnisotropy();
  return t;
}
function createFlag(faction) {
  const grp = new THREE.Group();
  const pole = new THREE.Mesh(new THREE.CylinderGeometry(0.4, 0.6, 26, 8),
    new THREE.MeshBasicMaterial({ color: 0x2b2620 }));
  pole.position.y = 13; grp.add(pole);
  const finial = new THREE.Mesh(new THREE.SphereGeometry(0.9, 12, 8),
    new THREE.MeshBasicMaterial({ color: 0xc9a45c }));
  finial.position.y = 26.6; grp.add(finial);
  const uniforms = {
    uTime: { value: 0 }, uMap: { value: makeFlagTexture(faction) },
    uUnfurl: { value: 0 }, uOpacity: { value: 1 }, uTilt: { value: 0 },
  };
  const clothGeo = new THREE.PlaneGeometry(13, 8.5, 24, 16);
  clothGeo.translate(6.5, 0, 0);
  const cloth = new THREE.Mesh(clothGeo, new THREE.ShaderMaterial({
    uniforms, side: THREE.DoubleSide, transparent: true,
    vertexShader: /* glsl */`
      uniform float uTime, uUnfurl, uTilt;
      varying vec2 vUv;
      void main(){
        vUv = uv;
        vec3 p = position;
        float k = p.x / 13.0;
        p.z += (sin(p.x*0.55 - uTime*2.6)*(0.5+0.5*k)*0.9 + sin(p.x*1.7 - uTime*4.1)*0.25) * k;
        p.x *= uUnfurl;
        p.y *= (0.3 + 0.7*uUnfurl);
        float cy = cos(uTilt), sy = sin(uTilt);
        p = vec3(p.x*cy - p.y*sy, p.x*sy + p.y*cy, p.z);
        gl_Position = projectionMatrix * modelViewMatrix * vec4(p, 1.0);
      }`,
    fragmentShader: /* glsl */`
      uniform sampler2D uMap;
      uniform float uOpacity;
      varying vec2 vUv;
      void main(){
        vec4 c = texture2D(uMap, vUv);
        gl_FragColor = vec4(c.rgb, c.a * uOpacity);
      }`,
  }));
  cloth.position.y = 25;
  grp.add(cloth);
  grp.visible = false;
  flagsGroup.add(grp);
  return { group: grp, cloth, uniforms, faction, cityId: null };
}
function placeFlag(f, cityId, instant = false) {
  const c = cityById[cityId];
  if (!c) return;
  const [x, z] = proj(c.location[0], c.location[1]);
  f.group.position.set(x, worldY(c.location[0], c.location[1], 0), z);
  f.cityId = cityId;
  if (instant) {
    f.group.visible = true;
    f.uniforms.uUnfurl.value = 1; f.uniforms.uOpacity.value = 1; f.uniforms.uTilt.value = 0;
  }
}
function flagRise(f) {
  f.group.visible = true;
  addTween(1.2, k => {
    f.uniforms.uUnfurl.value = easeOutCubic(k);
    f.uniforms.uOpacity.value = k;
    f.uniforms.uTilt.value = 0;
  }, null);
  goldRing(f.group.position.clone());
}
function flagFall(f, done) {
  addTween(1.0, k => {
    f.uniforms.uTilt.value = k * 0.45;
    f.uniforms.uOpacity.value = 1 - k;
  }, () => {
    f.group.visible = false;
    f.uniforms.uUnfurl.value = 0; f.uniforms.uTilt.value = 0;
    if (done) done();
  });
}
function buildFlags() {
  flagsGroup = new THREE.Group(); scene.add(flagsGroup);
  for (const f of factions) flags[f.id] = createFlag(f);
}
const fxRings = [];
function goldRing(pos, color = 0xc9a45c, maxR = 90) {
  const g = new THREE.RingGeometry(0.8, 1, 64);
  const m = new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.9, side: THREE.DoubleSide, blending: THREE.AdditiveBlending, depthWrite: false });
  const mesh = new THREE.Mesh(g, m);
  mesh.rotation.x = -Math.PI / 2;
  mesh.position.copy(pos); mesh.position.y += 1.5;
  fxGroup.add(mesh);
  fxRings.push({ mesh, t: 0, dur: 1.1, maxR });
}
function updateFxRings(dt) {
  for (let i = fxRings.length - 1; i >= 0; i--) {
    const r = fxRings[i];
    r.t += dt * speed;
    const k = Math.min(r.t / r.dur, 1);
    r.mesh.scale.setScalar(1 + (1 - Math.pow(1 - k, 3)) * r.maxR);
    r.mesh.material.opacity = 0.9 * (1 - k);
    if (k >= 1) {
      fxGroup.remove(r.mesh); r.mesh.geometry.dispose(); r.mesh.material.dispose();
      fxRings.splice(i, 1);
    }
  }
}

// ============================== 行军路线 ==============================
const activeRoutes = [];
function spawnRoute(route) {
  const from = cityById[route.from];
  if (!from) return;
  const to = route.toCity ? cityById[route.toCity]?.location : route.toPoint;
  if (!to) return;
  const pts = [];
  let cur = from.location;
  for (const h of [...(route.waypoints || []), to]) {
    const seg = geodesic(cur[0], cur[1], h[0], h[1], 48);
    pts.push(...seg.slice(pts.length ? 1 : 0));
    cur = h;
  }
  const positions = [];
  for (const [lo, la] of pts) positions.push(projX(lo), worldY(lo, la, CFG.liftRoute), projZ(la));
  const g = new LineGeometry();
  g.setPositions(positions);
  const f = factions[factionIdx[route.faction]];
  const m = new LineMaterial({
    color: new THREE.Color(f ? f.color : '#ffffff'), linewidth: 2.5,
    transparent: true, opacity: 0.95, blending: THREE.AdditiveBlending, depthWrite: false,
    dashed: true, dashSize: 6, gapSize: 4,
  });
  m.resolution.set(innerWidth, innerHeight);
  lineMaterials.push(m);
  const line = new Line2(g, m);
  line.computeLineDistances();
  line.frustumCulled = false;
  line.renderOrder = 5;
  const cone = new THREE.Mesh(new THREE.ConeGeometry(1.6, 5, 10),
    new THREE.MeshBasicMaterial({ color: f ? f.color : '#fff' }));
  cone.visible = false;
  routesGroup.add(line); routesGroup.add(cone);
  const cum = [0];
  for (let i = 1; i < pts.length; i++) {
    const [x1, z1] = proj(pts[i-1][0], pts[i-1][1]);
    const [x2, z2] = proj(pts[i][0], pts[i][1]);
    cum.push(cum[i-1] + Math.hypot(x2-x1, z2-z1));
  }
  const state = { line, cone, m, pts, cum, total: cum[cum.length-1], progress: 0, dying: false, dash: 0 };
  activeRoutes.push(state);
  addTween(0.9, k => { state.progress = k; }, null);
}
function updateRoutes(dt) {
  for (let i = activeRoutes.length - 1; i >= 0; i--) {
    const r = activeRoutes[i];
    r.dash -= dt * 30 * speed;
    r.m.dashOffset = r.dash;
    const visPts = Math.max(2, Math.floor(r.pts.length * easeOutCubic(r.progress)));
    r.line.geometry.setDrawRange(0, visPts);
    if (r.progress > 0.02 && r.progress < 1) {
      r.cone.visible = true;
      const dist = easeOutCubic(r.progress) * r.total;
      let j = 1;
      while (j < r.cum.length - 1 && r.cum[j] < dist) j++;
      const [lo1, la1] = r.pts[j-1], [lo2, la2] = r.pts[j];
      const t = (dist - r.cum[j-1]) / Math.max(r.cum[j] - r.cum[j-1], 1e-6);
      const lo = lo1 + (lo2-lo1)*t, la = la1 + (la2-la1)*t;
      r.cone.position.set(projX(lo), worldY(lo, la, CFG.liftRoute), projZ(la));
      r.cone.rotation.set(Math.PI/2, 0, -Math.atan2(projX(lo2)-projX(lo1), projZ(lo2)-projZ(lo1)), 'ZXY');
    } else if (r.progress >= 1 && !r.dying) {
      r.cone.visible = false;
      r.dying = true;
      addTween(0.8, k => { r.m.opacity = 0.95 * (1 - k); }, () => {
        routesGroup.remove(r.line); routesGroup.remove(r.cone);
        r.line.geometry.dispose();
        const mi = lineMaterials.indexOf(r.m); if (mi >= 0) lineMaterials.splice(mi, 1);
        r.m.dispose(); r.cone.geometry.dispose(); r.cone.material.dispose();
        activeRoutes.splice(activeRoutes.indexOf(r), 1);
      });
    }
  }
}

// ============================== 联盟光链 ==============================
function spawnAllyArc(suzId, memId, caps) {
  const c1 = cityById[caps[suzId]], c2 = cityById[caps[memId]];
  if (!c1 || !c2) return;
  const [x1, z1] = proj(c1.location[0], c1.location[1]);
  const [x2, z2] = proj(c2.location[0], c2.location[1]);
  const y1 = worldY(c1.location[0], c1.location[1], 2), y2 = worldY(c2.location[0], c2.location[1], 2);
  const mid = new THREE.Vector3((x1+x2)/2, Math.max(y1,y2) + Math.hypot(x2-x1,z2-z1)*0.22 + 20, (z1+z2)/2);
  const pts = new THREE.QuadraticBezierCurve3(new THREE.Vector3(x1,y1,z1), mid, new THREE.Vector3(x2,y2,z2)).getPoints(64);
  const g = new LineGeometry();
  g.setPositions(pts.flatMap(p => [p.x, p.y, p.z]));
  const sf = factions[factionIdx[suzId]];
  const m = new LineMaterial({
    color: new THREE.Color(sf ? sf.color : '#c9a45c'), linewidth: 2,
    transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false,
    dashed: true, dashSize: 5, gapSize: 3,
  });
  m.resolution.set(innerWidth, innerHeight);
  lineMaterials.push(m);
  const line = new Line2(g, m);
  line.computeLineDistances();
  line.frustumCulled = false;
  line.renderOrder = 5;
  arcsGroup.add(line);
  (allyArcs[suzId] = allyArcs[suzId] || []).push({ line, m, memberId: memId });
  addTween(0.8, k => { m.opacity = k * 0.85; }, null);
}
function removeAllyArcs(suzId, memId) {
  const list = allyArcs[suzId] || [];
  for (let i = list.length - 1; i >= 0; i--) {
    if (list[i].memberId !== memId) continue;
    const arc = list[i];
    addTween(0.5, k => { arc.m.opacity = 0.85 * (1 - k); }, () => {
      arcsGroup.remove(arc.line);
      arc.line.geometry.dispose();
      const mi = lineMaterials.indexOf(arc.m); if (mi >= 0) lineMaterials.splice(mi, 1);
      arc.m.dispose();
    });
    list.splice(i, 1);
  }
}

// ============================== 战场特效 ==============================
function spawnBattleFX(lon, lat) {
  const [x, z] = proj(lon, lat);
  const y = worldY(lon, lat, 2);
  goldRing(new THREE.Vector3(x, y, z), 0xd97a4a, 90);
  goldRing(new THREE.Vector3(x, y, z), 0xa63a2b, 55);
  const N = 200;
  const pos = new Float32Array(N*3), vel = new Float32Array(N*3), seed = new Float32Array(N);
  for (let i = 0; i < N; i++) {
    pos[i*3]=x; pos[i*3+1]=y; pos[i*3+2]=z;
    const a = Math.random()*Math.PI*2, r = 8+Math.random()*22;
    vel[i*3]=Math.cos(a)*r; vel[i*3+1]=10+Math.random()*28; vel[i*3+2]=Math.sin(a)*r;
    seed[i]=Math.random();
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  g.setAttribute('aVel', new THREE.BufferAttribute(vel, 3));
  g.setAttribute('aSeed', new THREE.BufferAttribute(seed, 1));
  const m = new THREE.ShaderMaterial({
    uniforms: { uT: { value: 0 } }, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
    vertexShader: /* glsl */`
      attribute vec3 aVel; attribute float aSeed;
      uniform float uT;
      varying float vA;
      void main(){
        float t = uT * (0.7 + aSeed*0.6);
        vec3 p = position + aVel*t + vec3(0.0, -78.0*t*t, 0.0);
        vA = max(1.0 - uT/1.6, 0.0);
        gl_Position = projectionMatrix * modelViewMatrix * vec4(p, 1.0);
        gl_PointSize = (2.0 + aSeed*3.0) * vA * 3.0 + 0.5;
      }`,
    fragmentShader: /* glsl */`
      varying float vA;
      void main(){
        if (length(gl_PointCoord-0.5) > 0.5 || vA <= 0.0) discard;
        gl_FragColor = vec4(0.85, 0.55, 0.35, vA*0.7);
      }`,
  });
  const pts = new THREE.Points(g, m);
  fxGroup.add(pts);
  addTween(1.6, k => { m.uniforms.uT.value = k * 1.6; }, () => { fxGroup.remove(pts); g.dispose(); m.dispose(); });
  engine.shakeT = 0.15;
}

// ============================== 缓动 & 补间 ==============================
function easeInOutCubic(k) { return k < 0.5 ? 4*k*k*k : 1 - Math.pow(-2*k+2, 3)/2; }
function easeOutCubic(k) { return 1 - Math.pow(1-k, 3); }
function smoothstepJS(a, b, x) { const t = Math.min(Math.max((x-a)/(b-a), 0), 1); return t*t*(3-2*t); }
function addTween(dur, update, done) {
  engine.tweens.push({ t: 0, dur: Math.max(dur / (speed || 1), 0.01), update, done });
}
function updateTweens(dt) {
  for (let i = engine.tweens.length - 1; i >= 0; i--) {
    const tw = engine.tweens[i];
    tw.t += dt;
    const k = Math.min(tw.t / tw.dur, 1);
    if (tw.update) tw.update(k);
    if (k >= 1) { engine.tweens.splice(i, 1); if (tw.done) tw.done(); }
  }
}

// ============================== 相机飞行 ==============================
function flyTo(target, dist, pitchDeg, dur = 0.9) {
  const startPos = camera.position.clone(), startTgt = controls.target.clone();
  const pitch = pitchDeg * Math.PI / 180;
  const dir = camera.position.clone().sub(controls.target);
  const azim = Math.atan2(dir.x, dir.z);
  const endPos = new THREE.Vector3(
    target.x + dist*Math.cos(pitch)*Math.sin(azim),
    target.y + dist*Math.sin(pitch),
    target.z + dist*Math.cos(pitch)*Math.cos(azim));
  const flight = {};
  engine.flight = flight;
  addTween(dur, k => {
    if (engine.flight !== flight) return;
    const e = easeInOutCubic(k);
    camera.position.lerpVectors(startPos, endPos, e);
    controls.target.lerpVectors(startTgt, target, e);
  }, () => { if (engine.flight === flight) engine.flight = null; });
}
function eventFocus(ev) {
  let minX=1e9, maxX=-1e9, minZ=1e9, maxZ=-1e9, n=0;
  const meta = DATA.countyMetaArr;
  for (const ch of ev.changes) {
    const m = meta[ch.county_idx];
    if (!m) continue;
    const [x, z] = proj(m.cx, m.cy);
    minX=Math.min(minX,x); maxX=Math.max(maxX,x);
    minZ=Math.min(minZ,z); maxZ=Math.max(maxZ,z);
    n++;
  }
  if (!n && ev.battle) {
    const [x, z] = proj(ev.battle.location[0], ev.battle.location[1]);
    minX=maxX=x; minZ=maxZ=z; n=1;
  }
  if (!n) {
    const capId = ev.capitals && ev.capitals[ev.actors.primary];
    const cc = capId && cityById[capId];
    if (cc) { const [x, z] = proj(cc.location[0], cc.location[1]); minX=maxX=x; minZ=maxZ=z; n=1; }
  }
  if (!n) return { target: new THREE.Vector3(0,0,0), dist: 2600, pitch: 50 };
  const diag = Math.hypot(maxX-minX, maxZ-minZ);
  const zoomK = ev.camera ? ev.camera.zoom / 7.4 : 1;
  return {
    target: new THREE.Vector3((minX+maxX)/2, 0, (minZ+maxZ)/2),
    dist: Math.min(Math.max(diag * zoomK * 1.6, 420), 2400),
    pitch: ev.camera ? Math.min(Math.max(ev.camera.pitch, 30), 65) : 52,
  };
}

// ============================== 事件卡 ==============================
const TYPE_BADGE = {
  occupy: ['占领', '#a63a2b'], conquer: ['灭国', '#2b2f38'], ally: ['联盟', '#c9a45c'],
  rebel: ['反叛', '#8e3b46'], submit: ['归附', '#8fb8b2'], battle: ['决战', '#a63a2b'],
  proclaim: ['称制', '#c9a45c'], move_capital: ['迁都', '#8fb8b2'], succeed: ['继位', '#7a8194'],
  march: ['出征', '#a63a2b'], ally_break: ['决裂', '#7a8194'], other: ['纪事', '#7a8194'],
};
let cardTimer = null;
function showEventCard(ev, sticky = false) {
  const card = document.getElementById('event-card');
  const [label, color] = TYPE_BADGE[ev.type] || TYPE_BADGE.other;
  document.getElementById('ec-badge').textContent = label;
  document.getElementById('ec-badge').style.background = color;
  document.getElementById('ec-year').textContent = ev.yearLabel;
  document.getElementById('ec-title').textContent = ev.title;
  document.getElementById('ec-summary').textContent = ev.summary || '';
  const q = document.getElementById('ec-quote');
  if (ev.quote && ev.quote.text) {
    q.style.display = '';
    document.getElementById('ec-quote-text').textContent = `「${ev.quote.text}」`;
    document.getElementById('ec-source').textContent = `—— ${ev.quote.source}`;
  } else q.style.display = 'none';
  card.classList.add('show');
  if (cardTimer) clearTimeout(cardTimer);
  if (!sticky) cardTimer = setTimeout(() => card.classList.remove('show'), 4200);
}

// ============================== 图鉴 ==============================
function rebuildLegend(si) {
  const box = document.getElementById('legend-items');
  const counts = {};
  const o = snap.owner[si];
  for (let i = 0; i < o.length; i++) if (o[i] >= 0) counts[o[i]] = (counts[o[i]] || 0) + 1;
  const fallenSet = new Set(snap.fallen[si]);
  const items = factions.map((f, i) => ({ f, i, n: counts[i] || 0, dead: fallenSet.has(f.id) }))
    .sort((a, b) => (b.n - a.n) || (a.dead - b.dead));
  box.innerHTML = '';
  for (const { f, i, n, dead } of items) {
    const div = document.createElement('div');
    div.className = 'legend-item' + (dead ? ' fallen' : '') + (soloIdx === i ? ' solo' : '');
    div.innerHTML = `<span class="legend-dot" style="background:${f.color}"></span>
      <span class="legend-name">${f.name}</span>
      ${dead ? '<span class="legend-fallen-tag">亡</span>' : `<span class="legend-count">${n}县</span>`}`;
    div.onclick = () => {
      soloIdx = soloIdx === i ? -1 : i;
      countyUniforms.uSolo.value = soloIdx;
      rebuildLegend(engine.current);
    };
    box.appendChild(div);
  }
}

// ============================== 年份显示 ==============================
function updateYearDisplay() {
  const i = engine.current;
  const yd = document.getElementById('year-display');
  const ec = document.getElementById('event-counter');
  if (i === 0) {
    yd.textContent = events[0] ? events[0].yearLabel : '—';
    ec.textContent = `初始格局 · 0 / ${events.length}`;
  } else {
    yd.textContent = events[i-1].yearLabel;
    ec.textContent = `${events[i-1].title} · ${i} / ${events.length}`;
  }
  const sl = document.getElementById('timeline');
  if (document.activeElement !== sl) sl.value = i;
}

// ============================== 快照应用 ==============================
function applySnapshot(idx, instant = true) {
  replayCityOwners(idx);
  writeStateTex(stateTexPrev, countyUniforms.uOwnerPrev.value, idx);
  writeStateTex(stateTexNext, countyUniforms.uOwnerNext.value, idx);
  countyUniforms.uProgress.value = 1;
  updateCityColors();
  rebuildLegend(idx);
  updateYearDisplay();
  applyFlags(idx, true);
  showBoundaries(idx === 0 ? 'initial' : events[idx-1].id, idx, instant);
}
function replayCityOwners(idx) {
  for (const c of cities) { c._ownerIdx = factionIdx[c.owner]; c._vassalIdx = -1; }
  for (let k = 0; k < idx; k++) {
    for (const oc of events[k].outcomes) {
      if (oc.type === 'occupy') setCityOwner(oc.city, oc.to);
      else if (oc.type === 'conquer') { for (const c of cities) if (c._ownerIdx === factionIdx[oc.faction]) c._ownerIdx = factionIdx[oc.by]; }
      else if (oc.type === 'submit') { for (const c of cities) if (c._ownerIdx === factionIdx[oc.faction]) c._ownerIdx = factionIdx[oc.to]; }
      else if (oc.type === 'rebel') { for (const cid of oc.cities || []) setCityOwner(cid, oc.to); }
      else if (oc.type === 'ally') { for (const m of oc.members || []) for (const c of cities) if (c._ownerIdx === factionIdx[m]) c._vassalIdx = factionIdx[oc.leader]; }
      else if (oc.type === 'ally_break') { for (const m of oc.members || []) for (const c of cities) if (c._ownerIdx === factionIdx[m]) c._vassalIdx = -1; }
    }
  }
}
function setCityOwner(cid, fid) {
  const c = cityById[cid];
  if (c) { c._ownerIdx = factionIdx[fid]; c._vassalIdx = -1; }
}
function applyFlags(idx, instant = false) {
  const caps = snap.capitals[idx] || {};
  const fallenSet = new Set(snap.fallen[idx]);
  for (const f of factions) {
    const fl = flags[f.id];
    if (!fl) continue;
    if (fallenSet.has(f.id)) { fl.group.visible = false; continue; }
    const cap = caps[f.id];
    if (cap && cityById[cap]) placeFlag(fl, cap, instant);
    else if (!cap) fl.group.visible = false;
  }
}

// ============================== 事件引擎 ==============================
const ANIM_DUR = { occupy: 2.6, conquer: 4.2, ally: 2.2, rebel: 2.4, submit: 3.0, battle: 3.5, proclaim: 1.8, move_capital: 2.6, march: 1.8, succeed: 1.8, other: 1.8, ally_break: 2.0 };

function playEvent(idx) {
  if (idx < 1 || idx > events.length) { engine.busy = false; return; }
  const ev = events[idx - 1];
  engine.busy = true;
  engine.current = idx;
  showEventCard(ev);
  updateYearDisplay();

  writeStateTex(stateTexPrev, countyUniforms.uOwnerPrev.value, idx - 1);
  writeStateTex(stateTexNext, countyUniforms.uOwnerNext.value, idx);
  countyUniforms.uProgress.value = 0;

  // 级联 delay
  const primaryCap = (snap.capitals[idx-1] || {})[ev.actors.primary];
  const pc = primaryCap ? cityById[primaryCap] : null;
  const meta = DATA.countyMetaArr;
  const delayByCounty = new Map();
  if (ev.changes.length) {
    let dmax = 1;
    for (const ch of ev.changes) {
      const m = meta[ch.county_idx];
      const d = pc ? Math.hypot(m.cx - pc.location[0], m.cy - pc.location[1]) : 0;
      delayByCounty.set(ch.county_idx, d);
      dmax = Math.max(dmax, d);
    }
    for (const [k, v] of delayByCounty) delayByCounty.set(k, v / dmax * 0.6);
  }
  const cidxAttr = countyMesh.geometry.getAttribute('aCountyIdx');
  for (let i = 0; i < cidxAttr.count; i++) {
    delayAttr.array[i] = delayByCounty.get(cidxAttr.array[i]) || 0;
  }
  delayAttr.needsUpdate = true;

  // 相机
  const userRecent = engine.userHold && (uTime - engine.userHold < 3.5);
  if (!userRecent) {
    const focus = eventFocus(ev);
    flyTo(focus.target, focus.dist, focus.pitch);
  }

  // 疆域过渡
  const colorDur = ANIM_DUR[ev.type] || 2.2;
  if (ev.changes.length) addTween(colorDur * 0.75, k => { countyUniforms.uProgress.value = k; }, null);
  else countyUniforms.uProgress.value = 1;

  runChoreography(ev, idx, colorDur);
  showBoundaries(ev.id, idx, false);
  replayCityOwners(idx);
  addTween(colorDur * 0.5, k => { if (k >= 1) updateCityColors(); }, null);
  applyFlagsAnimated(ev, idx);
  rebuildLegend(idx);

  engine.busyUntil = uTime + colorDur / speed;
  engine.dwellUntil = uTime + (colorDur + 2.2) / speed;
}

function runChoreography(ev, idx, dur) {
  for (const r of ev.routes || []) spawnRoute(r);
  if (ev.battle && ev.battle.location) {
    addTween(0.8, k => { if (k >= 1) spawnBattleFX(ev.battle.location[0], ev.battle.location[1]); }, null);
  }
  for (const oc of ev.outcomes) {
    if (oc.type === 'ally') {
      for (const m of oc.members) {
        addTween(0.4, k => { if (k >= 1) spawnAllyArc(oc.leader, m, snap.capitals[idx]); }, null);
      }
    }
    if (oc.type === 'ally_break') {
      for (const m of oc.members) removeAllyArcs(oc.leader, m);
    }
    if (oc.type === 'conquer' && flags[oc.faction] && flags[oc.faction].group.visible) {
      addTween(dur * 0.5, k => { if (k >= 1) flagFall(flags[oc.faction]); }, null);
    }
    if (oc.type === 'submit') {
      if (flags[oc.faction] && flags[oc.faction].group.visible) {
        addTween(dur * 0.6, k => { if (k >= 1) flagFall(flags[oc.faction]); }, null);
      }
      const caps = snap.capitals[idx] || {};
      if (caps[oc.to] && cityById[caps[oc.to]]) {
        const c = cityById[caps[oc.to]];
        const [x, z] = proj(c.location[0], c.location[1]);
        goldRing(new THREE.Vector3(x, worldY(c.location[0], c.location[1], 1.5), z), 0xc9a45c, 50);
      }
    }
  }
  if (ev.type === 'ally_break' && ev.city && cityById[ev.city]) {
    const c = cityById[ev.city];
    const [x, z] = proj(c.location[0], c.location[1]);
    goldRing(new THREE.Vector3(x, worldY(c.location[0], c.location[1], 1.5), z), 0x7a8194, 40);
  }
  if (ev.type === 'proclaim' || ev.type === 'succeed' || ev.type === 'other') {
    const caps = snap.capitals[idx] || {};
    const capId = (ev.city && cityById[ev.city]) ? ev.city : caps[ev.actors.primary];
    if (capId && cityById[capId]) {
      const c = cityById[capId];
      const [x, z] = proj(c.location[0], c.location[1]);
      goldRing(new THREE.Vector3(x, worldY(c.location[0], c.location[1], 1.5), z), 0xc9a45c, ev.type === 'proclaim' ? 70 : 40);
    }
  }
}
function applyFlagsAnimated(ev, idx) {
  const fallenSet = new Set(snap.fallen[idx]);
  for (const mv of ev.capital_moves || []) {
    const fl = flags[mv.faction];
    if (fl && fl.group.visible) {
      flagFall(fl, () => { placeFlag(fl, mv.to, false); flagRise(fl); });
    }
  }
  if (ev.type === 'proclaim') {
    const fl = flags[ev.actors.primary];
    const caps = snap.capitals[idx] || {};
    if (fl && !fl.group.visible && caps[ev.actors.primary]) {
      placeFlag(fl, caps[ev.actors.primary], false);
      flagRise(fl);
    }
  }
  for (const f of factions) {
    if (fallenSet.has(f.id) && flags[f.id]) flags[f.id].group.visible = false;
  }
}

// ============================== 播放控制 ==============================
function seekTo(idx, instant = true) {
  idx = Math.max(0, Math.min(events.length, idx));
  engine.tweens.length = 0;
  engine.current = idx;
  applySnapshot(idx, instant);
  engine.dwellUntil = uTime + 1.5;
  engine.busy = false;
}
function nextEvent() {
  if (engine.current >= events.length) {
    if (autoplay) { seekTo(0, true); return; }
    setPlaying(false);
    return;
  }
  playEvent(engine.current + 1);
}
function setPlaying(p) {
  playing = p;
  document.getElementById('btn-play').textContent = p ? '⏸' : '▶';
  document.getElementById('btn-play').classList.toggle('active', p);
  if (p && engine.current >= events.length) seekTo(0, true);
}

// ============================== 时辰 ==============================
function applyTimeOfDay(t01) {
  const elev = 0.10 + 0.52 * t01;
  const azim = -1.0 + 2.0 * t01;
  const dir = new THREE.Vector3(Math.cos(elev)*Math.sin(azim), Math.sin(elev), -Math.cos(elev)*Math.cos(azim));
  const w = smoothstepJS(0.0, 0.42, elev);
  const col = new THREE.Color(1.0, 0.55, 0.30).lerp(new THREE.Color(1.0, 0.95, 0.85), w);
  const inten = 2.0 - 0.8 * w;
  sunLight.position.copy(dir).multiplyScalar(5000);
  sunLight.color.copy(col); sunLight.intensity = inten;
  terrainUniforms.uSunDir.value.copy(dir);
  terrainUniforms.uSunColor.value.copy(col).multiplyScalar(inten * 0.62);
  document.getElementById('tod-val').textContent = t01 < 0.2 ? '清晨' : t01 < 0.45 ? '上午' : t01 < 0.75 ? '午后' : '黄昏';
}

// ============================== UI ==============================
function bindUI() {
  const $ = id => document.getElementById(id);
  $('timeline').max = events.length;
  $('timeline').addEventListener('input', e => { seekTo(+e.target.value, true); });
  $('btn-prev').onclick = () => seekTo(engine.current - 1, true);
  $('btn-next').onclick = () => { engine.busy = false; engine.tweens.length = 0; nextEvent(); };
  $('btn-play').onclick = () => setPlaying(!playing);
  $('btn-auto').onclick = e => { autoplay = !autoplay; e.target.classList.toggle('active', autoplay); };
  document.querySelectorAll('.speed-pill').forEach(b => {
    b.onclick = () => {
      speed = +b.dataset.speed;
      document.querySelectorAll('.speed-pill').forEach(x => x.classList.toggle('active', x === b));
    };
  });
  $('exagg').addEventListener('input', e => {
    CFG.exagg = 1.0 + (e.target.value / 100) * 2.0;
    $('exagg-val').textContent = CFG.exagg.toFixed(1) + '×';
    for (const u of exaggUniforms) u.uExagg.value = CFG.exagg;
    refreshExaggDependent();
  });
  $('tod').addEventListener('input', e => applyTimeOfDay(e.target.value / 100));
  $('btn-drift').onclick = e => {
    controls.autoRotate = !controls.autoRotate;
    e.target.classList.toggle('active', controls.autoRotate);
  };
  addEventListener('keydown', e => {
    if (e.key === 'h' || e.key === 'H') document.getElementById('ui').classList.toggle('hidden-mode');
    if (e.key === ' ') { e.preventDefault(); setPlaying(!playing); }
  });
}
let exaggTimer = null;
function refreshExaggDependent() {
  if (exaggTimer) clearTimeout(exaggTimer);
  exaggTimer = setTimeout(() => {
    rebuildRivers();
    for (const id in cityMeshes) {
      const { holder, city } = cityMeshes[id];
      holder.position.y = worldY(city.location[0], city.location[1], 1.1);
    }
    for (const f of factions) {
      const fl = flags[f.id];
      if (fl && fl.cityId && cityById[fl.cityId]) {
        const c = cityById[fl.cityId];
        fl.group.position.y = worldY(c.location[0], c.location[1], 0);
      }
    }
    showBoundaries(engine.current === 0 ? 'initial' : events[engine.current-1].id, engine.current, true);
  }, 120);
}

// ============================== 主循环 ==============================
let lastT = 0, fpsAcc = 0, fpsFrames = 0, fpsLast = 0;
function frame(t) {
  const now = t * 0.001;
  const dt = Math.min(now - lastT, 0.1);
  lastT = now;
  uTime += dt;

  controls.update();
  updateTweens(dt);
  updateRoutes(dt);
  updateFxRings(dt);

  if (playing && !engine.busy && uTime >= engine.dwellUntil) nextEvent();
  else if (engine.busy && uTime >= engine.busyUntil) engine.busy = false;

  for (const f of factions) {
    const fl = flags[f.id];
    if (fl && fl.group.visible) fl.uniforms.uTime.value = uTime;
  }
  for (const sid in allyArcs) for (const a of allyArcs[sid]) a.m.dashOffset = -uTime * 8;

  if (engine.shakeT > 0) {
    engine.shakeT -= dt;
    camera.position.x += (Math.random()-0.5) * 1.2;
    camera.position.y += (Math.random()-0.5) * 1.2;
  }

  countyLineUniforms.uCamDist.value = camera.position.distanceTo(controls.target);
  updateCityLabelVisibility();
  oceanMat.uniforms.uTime.value = uTime;

  composer.render();
  css2d.render(scene, camera);

  fpsAcc += dt; fpsFrames++;
  if (now - fpsLast > 0.5) {
    document.getElementById('fps').textContent = `${Math.round(fpsFrames / fpsAcc)} FPS`;
    fpsAcc = 0; fpsFrames = 0; fpsLast = now;
  }
  if (!firstFrameShown) {
    firstFrameShown = true;
    document.getElementById('loader').classList.add('fade');
    document.getElementById('ui').classList.add('revealed');
  }
}

function onResize() {
  camera.aspect = innerWidth / innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight);
  composer.setSize(innerWidth, innerHeight);
  css2d.setSize(innerWidth, innerHeight);
  for (const m of lineMaterials) m.resolution.set(innerWidth, innerHeight);
}
document.addEventListener('visibilitychange', () => {
  if (document.hidden) renderer.setAnimationLoop(null);
  else { lastT = performance.now() * 0.001; renderer.setAnimationLoop(frame); }
});

// ============================== 启动 ==============================
(async function main() {
  try { await loadAll(); } catch (e) { return; }
  if (!initRenderer()) return;
  initLights();
  routesGroup = new THREE.Group(); scene.add(routesGroup);
  arcsGroup = new THREE.Group(); scene.add(arcsGroup);
  fxGroup = new THREE.Group(); scene.add(fxGroup);
  buildSnapshots();
  buildTerrain();
  buildOcean();
  buildCounties();
  buildCountyLines();
  buildHydro();
  buildCities();
  buildFlags();
  bindUI();
  applyTimeOfDay(0.62);
  applySnapshot(0, true);
  addEventListener('resize', onResize);
  renderer.setAnimationLoop(frame);
  window.__dbg = { scene, camera, controls, engine, DATA, countyUniforms, terrainUniforms, seekTo };
  console.log('[山河裂变] 初始化完成', { 县数: DATA.countyMeta.length, 事件数: events.length });
})();
