#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全国 3D 古风地形服务器
纯启动脚本，不生成 HTML，避免格式化错误
"""

import os
import http.server
import socketserver
import threading
import time

PORT = 8000


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    print(f"📂 工作目录: {os.getcwd()}")

    # 检查瓦片
    tiles_dir = os.path.join("../tiles", "china_relief")
    if not os.path.exists(tiles_dir):
        print("\n❌ 错误: 未找到瓦片目录 tiles/china_relief/")
        print("   请先运行: python pipline_china.py")
        return

    # 检查 Natural Earth 预处理数据
    if not os.path.exists("../geojson"):
        print("\n⚠️ 警告: 未找到 geojson/ 目录，河流/海洋/湖泊将不显示")
        print("   建议运行: python prepare_ne_data.py")

    print(f"\n🚀 服务器启动: http://localhost:{PORT}")
    print(f"🌍 访问地址: http://localhost:{PORT}/china_3d.html")
    print(f"\n💡 提示: 确保 china_3d.html 与本脚本在同一目录")
    print(f"\n按 Ctrl+C 停止服务器")

    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", PORT), handler) as httpd:
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