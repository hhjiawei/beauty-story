#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
一键启动：自动检测瓦片层级 + 生成正确 HTML + 启动 HTTP 服务器 + 自动打开浏览器
"""

import os
import webbrowser
import http.server
import socketserver
import threading
import time
from pathlib import Path

PORT = 8000

def get_available_zoom_levels(tiles_dir):
    """扫描 tiles/relief/ 目录，返回所有可用的 z 层级列表"""
    levels = []
    if not os.path.exists(tiles_dir):
        return levels
    for name in os.listdir(tiles_dir):
        path = os.path.join(tiles_dir, name)
        if os.path.isdir(path) and name.isdigit():
            # 检查该层级下是否有 webp 文件
            has_tiles = False
            for root, dirs, files in os.walk(path):
                if any(f.endswith('.webp') for f in files):
                    has_tiles = True
                    break
            if has_tiles:
                levels.append(int(name))
    return sorted(levels)

def generate_html(tile_url, min_zoom, max_zoom, initial_zoom):
    """根据可用层级动态生成 HTML"""
    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>中国地形图 - Relief Tiles</title>
  <script src="https://unpkg.com/maplibre-gl@3.6.2/dist/maplibre-gl.js"></script>
  <link href="https://unpkg.com/maplibre-gl@3.6.2/dist/maplibre-gl.css" rel="stylesheet" />
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ font-family: "Noto Serif SC", "SimSun", serif; background: #f5f0e8; }}
    #map {{ position: absolute; top: 0; left: 0; right: 0; bottom: 0; }}
    .map-title {{
      position: absolute; top: 20px; left: 20px; z-index: 10;
      background: rgba(250, 246, 240, 0.92);
      padding: 16px 24px; border-radius: 12px; border: 1px solid #d4c9b8;
      box-shadow: 0 4px 20px rgba(0,0,0,0.08); backdrop-filter: blur(8px);
      max-width: 340px;
    }}
    .map-title h2 {{ font-size: 22px; color: #3d3229; letter-spacing: 4px; margin-bottom: 6px; }}
    .map-title p {{ font-size: 12px; color: #8c7e6e; line-height: 1.5; }}
    .map-title .meta {{ margin-top: 8px; padding-top: 8px; border-top: 1px solid #d4c9b8; font-size: 11px; color: #a09080; }}
    .loading {{
      position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); z-index: 20;
      background: rgba(250, 246, 240, 0.95); padding: 20px 32px; border-radius: 12px;
      border: 1px solid #d4c9b8; font-size: 14px; color: #5a5046;
      display: flex; align-items: center; gap: 10px;
    }}
    .loading.hidden {{ display: none; }}
    .spinner {{ width: 16px; height: 16px; border: 2px solid #d4c9b8; border-top-color: #c45c3e; border-radius: 50%; animation: spin 1s linear infinite; }}
    @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
  </style>
</head>
<body>
  <div class="loading" id="loading"><div class="spinner"></div><span>正在加载地形瓦片...</span></div>
  <div id="map"></div>
  <div class="map-title">
    <h2>中国地形图</h2>
    <p>Terrarium DEM → 山体阴影 → 高程着色</p>
    <div class="meta">层级: z={min_zoom}~{max_zoom} | 瓦片金字塔 | 渲染: 自烘焙 WebP</div>
  </div>
<script>
const TILE_URL = '{tile_url}';
const CHINA_BOUNDS = [73.0, 18.0, 136.0, 54.0];
const MIN_ZOOM = {min_zoom};
const MAX_ZOOM = {max_zoom};

const MAP_STYLE = {{
  version: 8,
  sources: {{
    relief: {{
      type: 'raster',
      tiles: [TILE_URL],
      tileSize: 256,
      bounds: CHINA_BOUNDS,
      attribution: 'Terrain Tiles © Mapzen | 渲染 © 自制',
      minzoom: MIN_ZOOM,
      maxzoom: MAX_ZOOM
    }}
  }},
  layers: [{{
    id: 'relief-layer',
    type: 'raster',
    source: 'relief',
    paint: {{ 'raster-opacity': 1.0 }}
  }}]
}};

const map = new maplibregl.Map({{
  container: 'map',
  style: MAP_STYLE,
  center: [104.5, 36.0],
  zoom: {initial_zoom},
  minZoom: MIN_ZOOM,
  maxZoom: MAX_ZOOM + 0.5,  // 允许稍微超出，但会显示最大层级瓦片放大
  maxBounds: [[70, 15], [140, 55]],
  attributionControl: false
}});

map.addControl(new maplibregl.AttributionControl({{
  customAttribution: '地形渲染 © 自制 | DEM © Mapzen/AWS Open Data'
}}), 'bottom-right');

map.addControl(new maplibregl.NavigationControl(), 'top-right');
map.addControl(new maplibregl.ScaleControl({{ maxWidth: 120, unit: 'metric' }}), 'bottom-left');

map.on('load', () => {{
  document.getElementById('loading').classList.add('hidden');
  console.log('✅ 地图加载完成，可用层级: z=' + MIN_ZOOM + '~' + MAX_ZOOM);
}});

map.on('error', (e) => {{
  console.error('❌ 地图错误:', e);
  document.querySelector('#loading span').textContent = '瓦片加载失败，请检查瓦片是否存在';
}});
</script>
</body>
</html>'''
def main():
    root = Path(__file__).parent.resolve()
    os.chdir(root)
    print(f"📂 工作目录: {root}")

    tiles_dir = os.path.join(root, "tiles", "china_relief")
    available_z = get_available_zoom_levels(tiles_dir)

    if not available_z:
        print(f"⚠️  警告: 未找到任何瓦片")
        print("   请先运行 pipline_pyramid.py 生成瓦片！")
        return

    min_z = min(available_z)
    max_z = max(available_z)
    initial_z = 4 if 4 in available_z else min(available_z)

    print(f"📦 检测到瓦片层级: z={min_z}~{max_z}")
    for z in available_z:
        z_dir = os.path.join(tiles_dir, str(z))
        count = sum(1 for _, _, files in os.walk(z_dir) for f in files if f.endswith('.webp'))
        print(f"   z={z}: {count} 张")

    tile_url = f'http://localhost:{PORT}/tiles/china_relief/{{z}}/{{x}}/{{y}}.webp'
    html = generate_html(tile_url, min_z, max_z, initial_z)

    index_path = os.path.join(root, "index.html")
    with open(index_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"📝 已生成: {index_path} (minZoom={min_z}, maxZoom={max_z}, initialZoom={initial_z})")

    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", PORT), handler) as httpd:
        print(f"\n🚀 服务器启动: http://localhost:{PORT}")
        print(f"🌍 自动打开浏览器...")

        server_thread = threading.Thread(target=httpd.serve_forever)
        server_thread.daemon = True
        server_thread.start()

        time.sleep(1)
        # webbrowser.open(f"http://localhost:{PORT}/index.html")

        print(f"\n按 Ctrl+C 停止服务器")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n⏹️  服务器已停止")
            httpd.shutdown()

if __name__ == "__main__":
    main()