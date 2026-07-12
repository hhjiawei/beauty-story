#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
河南 3D 地形服务器（修复版）
自动修复工作目录、文件生成、404 问题
"""

import os
import sys
import http.server
import socketserver
import threading
import time

PORT = 8000


def get_available_zoom_levels(tiles_dir):
    levels = []
    if not os.path.exists(tiles_dir):
        return levels
    for name in os.listdir(tiles_dir):
        path = os.path.join(tiles_dir, name)
        if os.path.isdir(path) and name.isdigit():
            has_tiles = False
            for root, dirs, files in os.walk(path):
                if any(f.endswith('.webp') for f in files):
                    has_tiles = True
                    break
            if has_tiles:
                levels.append(int(name))
    return sorted(levels)


def generate_html(tile_url, dem_url, min_zoom, max_zoom, initial_zoom):
    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>河南古风地形 · 3D Demo</title>
  <script src="https://unpkg.com/maplibre-gl@3.6.2/dist/maplibre-gl.js"></script>
  <link href="https://unpkg.com/maplibre-gl@3.6.2/dist/maplibre-gl.css" rel="stylesheet" />
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ font-family: "Noto Serif SC", "SimSun", "STSong", serif; background: #f5f0e8; overflow: hidden; }}
    #map {{ position: absolute; top: 0; left: 0; right: 0; bottom: 0; }}

    .map-title {{
      position: absolute; top: 20px; left: 20px; z-index: 10;
      background: rgba(250, 246, 240, 0.95);
      padding: 16px 24px; border-radius: 12px; border: 1px solid #d4c9b8;
      box-shadow: 0 4px 20px rgba(0,0,0,0.08); backdrop-filter: blur(8px);
      max-width: 320px;
    }}
    .map-title h2 {{ font-size: 20px; color: #3d3229; letter-spacing: 4px; margin-bottom: 6px; }}
    .map-title p {{ font-size: 11px; color: #8c7e6e; line-height: 1.5; }}
    .map-title .meta {{ margin-top: 8px; padding-top: 8px; border-top: 1px solid #d4c9b8; font-size: 10px; color: #a09080; }}

    .loading {{
      position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); z-index: 20;
      background: rgba(250, 246, 240, 0.95); padding: 20px 36px; border-radius: 12px;
      border: 1px solid #d4c9b8; font-size: 14px; color: #5a5046;
      display: flex; align-items: center; gap: 10px;
    }}
    .loading.hidden {{ display: none; }}
    .spinner {{ width: 18px; height: 18px; border: 2px solid #d4c9b8; border-top-color: #c45c3e; border-radius: 50%; animation: spin 1s linear infinite; }}
    @keyframes spin {{ to {{ transform: rotate(360deg); }} }}

    .warn-box {{
      position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%);
      background: #fff3cd; border: 1px solid #ffc107; border-radius: 10px;
      padding: 16px 24px; font-size: 13px; color: #856404; z-index: 25;
      display: none; max-width: 400px; text-align: center; line-height: 1.6;
    }}
    .warn-box.show {{ display: block; }}

    .exaggeration-control {{
      position: absolute; bottom: 24px; right: 24px; z-index: 10;
      background: rgba(250, 246, 240, 0.96); padding: 14px 18px;
      border-radius: 10px; border: 1px solid #d4c9b8;
      box-shadow: 0 4px 16px rgba(0,0,0,0.08);
      min-width: 180px;
    }}
    .exaggeration-control label {{
      font-size: 12px; color: #5a5046; display: block; margin-bottom: 8px;
      font-weight: bold;
    }}
    .exaggeration-control input {{
      width: 100%; accent-color: #c45c3e;
    }}
    .exaggeration-control .value {{
      font-size: 11px; color: #c45c3e; text-align: right; margin-top: 4px;
    }}

    .landmark-popup {{
      position: absolute; top: 20px; right: 20px; z-index: 10;
      background: rgba(250, 246, 240, 0.96); padding: 14px 18px;
      border-radius: 10px; border: 1px solid #d4c9b8;
      box-shadow: 0 4px 16px rgba(0,0,0,0.08);
      max-width: 220px;
    }}
    .landmark-popup h3 {{
      font-size: 14px; color: #3d3229; margin-bottom: 10px;
      border-bottom: 1px solid #d4c9b8; padding-bottom: 6px;
    }}
    .landmark-item {{
      display: flex; justify-content: space-between; align-items: center;
      padding: 5px 0; font-size: 12px; color: #5a5046;
      border-bottom: 1px dashed #e0d8cc;
    }}
    .landmark-item:last-child {{ border-bottom: none; }}
    .landmark-elev {{ color: #c45c3e; font-weight: bold; }}
  </style>
</head>
<body>
  <div class="loading" id="loading"><div class="spinner"></div><span>正在加载3D古风地形...</span></div>
  <div class="warn-box" id="warnBox">
    <b>3D 地形加载失败</b><br>
    DEM 高程瓦片缺失，已降级为 2D 地图。<br>
    请先运行 <code>python pipline_henan.py</code> 生成瓦片。
  </div>

  <div id="map"></div>

  <div class="map-title">
    <h2>河南古风地形</h2>
    <p>太行山 · 伏牛山 · 南阳盆地 · 豫东平原</p>
    <div class="meta">层级: z={min_zoom}~{max_zoom} | 3D exaggeration: 12x | 渲染: 古风配色</div>
  </div>

  <div class="landmark-popup">
    <h3>地标海拔</h3>
    <div class="landmark-item"><span>嵩山</span><span class="landmark-elev">1491m</span></div>
    <div class="landmark-item"><span>太行山</span><span class="landmark-elev">1500m+</span></div>
    <div class="landmark-item"><span>桐柏山</span><span class="landmark-elev">800m+</span></div>
    <div class="landmark-item"><span>南阳盆地</span><span class="landmark-elev">~80m</span></div>
    <div class="landmark-item"><span>豫东平原</span><span class="landmark-elev">~50m</span></div>
  </div>

  <div class="exaggeration-control">
    <label>地形夸张倍数（实时调节）</label>
    <input type="range" id="exSlider" min="0" max="20" value="12" step="0.5">
    <div class="value" id="exValue">12.0 x</div>
    <div style="font-size:10px;color:#a09080;margin-top:6px;">
      拉到 15x 看太行山拔地而起，<br>降到 0x 看原始平面
    </div>
  </div>

<script>
const TILE_URL = '{tile_url}';
const DEM_URL = '{dem_url}';
const HENAN_BOUNDS = [110.0, 31.0, 117.0, 37.0];

const landmarks = [
  {{ name: '嵩山', coords: [113.02, 34.49], elev: 1491, type: 'peak' }},
  {{ name: '太行山', coords: [113.65, 36.05], elev: 1580, type: 'peak' }},
  {{ name: '桐柏山', coords: [113.40, 32.35], elev: 800, type: 'peak' }},
  {{ name: '南阳盆地', coords: [112.55, 33.00], elev: 80, type: 'basin' }},
  {{ name: '豫东平原', coords: [114.70, 33.80], elev: 50, type: 'plain' }},
  {{ name: '洛阳盆地', coords: [112.45, 34.62], elev: 150, type: 'basin' }}
];

const map = new maplibregl.Map({{
  container: 'map',
  style: {{
    version: 8,
    sources: {{
      dem: {{
        type: 'raster-dem',
        tiles: [DEM_URL],
        tileSize: 256,
        bounds: HENAN_BOUNDS,
        attribution: 'DEM © Mapzen/AWS Open Data',
        minzoom: {min_zoom},
        maxzoom: {max_zoom},
        encoding: 'terrarium'
      }},
      relief: {{
        type: 'raster',
        tiles: [TILE_URL],
        tileSize: 256,
        bounds: HENAN_BOUNDS,
        attribution: 'Terrain © 古风自制',
        minzoom: {min_zoom},
        maxzoom: {max_zoom}
      }}
    }},
    layers: [
      {{
        id: 'relief-layer',
        type: 'raster',
        source: 'relief',
        paint: {{ 'raster-opacity': 1.0 }}
      }}
    ],
    terrain: {{
      source: 'dem',
      exaggeration: 12
    }},
    sky: {{
      'sky-type': 'atmosphere',
      'sky-atmosphere-sun': [0.0, 90.0],
      'sky-atmosphere-sun-intensity': 15
    }},
    fog: {{
      'range': [0.5, 6],
      'color': '#f0e8d8',
      'horizon-blend': 0.15
    }},
    light: {{
      'anchor': 'viewport',
      'color': '#fff8f0',
      'intensity': 0.85,
      'position': [1.15, 210, 25]
    }}
  }},
  center: [113.0, 34.0],
  zoom: 8,
  pitch: 82,
  bearing: -20,
  minZoom: {min_zoom},
  maxZoom: {max_zoom} + 0.5,
  maxPitch: 85,
  maxBounds: [[109, 30], [118, 38]]
}});

map.addControl(new maplibregl.AttributionControl({{
  customAttribution: '3D Terrain © Mapzen | 古风渲染 © 自制'
}}), 'bottom-right');

map.addControl(new maplibregl.NavigationControl(), 'top-right');

function checkDEMAndFallback() {{
  const testUrl = DEM_URL.replace('{{z}}', '{initial_zoom}').replace('{{x}}', '825').replace('{{y}}', '400');
  fetch(testUrl)
    .then(r => {{
      if (!r.ok) throw new Error('DEM 404');
      console.log('✅ DEM 瓦片检测通过');
    }})
    .catch(e => {{
      console.warn('❌ DEM 瓦片缺失，降级到 2D:', e);
      map.setTerrain(null);
      map.setFog(null);
      map.setPitch(0);
      document.getElementById('warnBox').classList.add('show');
    }});
}}

function initLandmarks() {{
  const features = landmarks.map(l => ({{
    type: 'Feature',
    properties: {{ name: l.name, elev: l.elev, type: l.type }},
    geometry: {{ type: 'Point', coordinates: l.coords }}
  }}));

  map.addSource('landmarks', {{
    type: 'geojson',
    data: {{ type: 'FeatureCollection', features: features }}
  }});

  const colorExpr = [
    'case',
    ['==', ['get', 'type'], 'peak'], '#c45c3e',
    ['==', ['get', 'type'], 'basin'], '#2a7d8f',
    '#8c9e5e'
  ];

  map.addLayer({{
    id: 'landmark-circle',
    type: 'circle',
    source: 'landmarks',
    paint: {{
      'circle-radius': 8,
      'circle-color': colorExpr,
      'circle-stroke-width': 2,
      'circle-stroke-color': '#fff',
      'circle-opacity': 0.9
    }}
  }});

  map.addLayer({{
    id: 'landmark-label',
    type: 'symbol',
    source: 'landmarks',
    layout: {{
      'text-field': ['concat', ['get', 'name'], '\\n', ['get', 'elev'], 'm'],
      'text-size': 11,
      'text-offset': [0, 1.2],
      'text-anchor': 'top',
      'text-font': ['Noto Sans Regular']
    }},
    paint: {{
      'text-color': '#3d3229',
      'text-halo-color': 'rgba(250,246,240,0.9)',
      'text-halo-width': 2
    }}
  }});
}}

document.getElementById('exSlider').addEventListener('input', function(e) {{
  const val = parseFloat(e.target.value);
  document.getElementById('exValue').textContent = val.toFixed(1) + ' x';
  map.setTerrain({{ source: 'dem', exaggeration: val }});
}});

map.on('load', () => {{
  document.getElementById('loading').classList.add('hidden');
  checkDEMAndFallback();
  initLandmarks();
  console.log('✅ 河南 3D 古风地图加载完成');

  setTimeout(() => {{
    map.easeTo({{ center: [113.02, 34.49], zoom: 9.5, pitch: 82, duration: 2000 }});
  }}, 1500);
}});

map.on('error', (e) => {{
  console.error('❌ 地图错误:', e);
  document.querySelector('#loading span').textContent = '瓦片加载失败，请检查服务器';
}});
</script>
</body>
</html>'''


def main():
    # 关键修复：确保工作目录就是脚本所在目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    print(f"📂 脚本目录: {script_dir}")
    print(f"📂 当前工作目录: {os.getcwd()}")

    tiles_dir = os.path.join(script_dir, "tiles", "henan_relief")
    available_z = get_available_zoom_levels(tiles_dir)

    if not available_z:
        print(f"\n❌ 错误: 未找到任何瓦片!")
        print(f"   瓦片目录: {tiles_dir}")
        print(f"   请先运行: python pipline_henan.py")
        print(f"   或者检查 tiles/henan_relief/ 是否存在")
        sys.exit(1)

    min_z = min(available_z)
    max_z = max(available_z)
    initial_z = 8 if 8 in available_z else min(available_z)

    print(f"\n📦 检测到瓦片层级: z={min_z}~{max_z}")
    for z in available_z:
        z_dir = os.path.join(tiles_dir, str(z))
        count = sum(1 for _, _, files in os.walk(z_dir) for f in files if f.endswith('.webp'))
        print(f"   z={z}: {count} 张")

    tile_url = f'http://localhost:{PORT}/tiles/henan_relief/{{z}}/{{x}}/{{y}}.webp'
    dem_url = f'http://localhost:{PORT}/tiles/henan_dem/{{z}}/{{x}}/{{y}}.png'
    html = generate_html(tile_url, dem_url, min_z, max_z, initial_z)

    index_path = os.path.join(script_dir, "henan_3d.html")
    with open(index_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"\n📝 HTML 已生成: {os.path.abspath(index_path)}")

    # 验证文件确实存在
    if not os.path.exists(index_path):
        print(f"❌ 文件生成失败！")
        sys.exit(1)

    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", PORT), handler) as httpd:
        print(f"\n🚀 服务器启动: http://localhost:{PORT}")
        print(f"🌍 访问地址: http://localhost:{PORT}/henan_3d.html")
        print(f"\n💡 如果浏览器 404，请确认：")
        print(f"   1. 你在浏览器输入的是: http://localhost:{PORT}/henan_3d.html")
        print(f"   2. 当前目录下有 henan_3d.html 文件")
        print(f"   3. 没有别的程序占用 8000 端口")
        print(f"\n按 Ctrl+C 停止服务器")

        server_thread = threading.Thread(target=httpd.serve_forever)
        server_thread.daemon = True
        server_thread.start()

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n⏹️  服务器已停止")
            httpd.shutdown()


if __name__ == "__main__":
    main()