══════════════════════════════════════════════
  Aviation Briefing 使用说明
  WX / TAF / NOTAM 判读智能体
══════════════════════════════════════════════

【方式一】双击 app.html —— 最简单
  · 直接双击用浏览器打开即可使用
  · WX 天气: 实时在线获取 (Open-Meteo)
  · TAF: 实时在线获取 (AviationWeather)
  · NOTAM: 自动在线获取 (FAA NOTAM Search)
    若网络受限、在线获取失败，自动回退内置缓存
    + 手动粘贴 JEP Pro 通告
  · 无需安装任何东西，发给别人也能用

【方式二】双击 start.command (Mac) / start.bat (Win)
  · 启动本地服务器，全自动在线获取
  · WX / TAF / NOTAM 全部实时更新
  · 需要 Python 3 (Mac自带)

【方式三】iPhone/iPad 添加主屏幕 (像App一样 · PWA)
  已内置 PWA 支持：独立图标、全屏运行、离线外壳缓存
  1. 电脑上双击 start.command / start.bat 启动服务器
  2. 手机/iPad 连同一WiFi
  3. Safari 访问 http://电脑IP:8080
     (服务器启动时会打印本机IP)
  4. Safari 底部"分享" → "添加到主屏幕"
  5. 之后从主屏幕图标打开，全屏运行，像一个App
  · Android Chrome: 菜单 → "添加到主屏幕/安装应用"
  · 注意: 经 http://内网IP 访问时，iOS 不注册 Service Worker，
    故离线缓存不可用；需要离线壳请让设备访问 https 或 localhost

【方式四】公网部署 —— 任何网络都能用 (多设备推荐)
  把 server.py 部署到免费平台，得到一个固定 https 网址，
  任何网络都能访问，且电脑不用一直开着。
  · 已附带部署文件: Dockerfile / Procfile / requirements.txt
    / render.yaml / fly.toml / .dockerignore
  · 最快路径 (Render 免费层):
      1. 把本文件夹上传到 GitHub 仓库（可不要 android/ 与 *.zip）
      2. render.com → New → Web Service → 选中该仓库
      3. Render 自动识别 render.yaml；或手动填:
         Build Command: pip install -r requirements.txt
         Start Command: python3 server.py
      4. 部署完成 → 得到 https://xxx.onrender.com
      5. 设备打开该网址 → "添加到主屏幕"
  · 免费层闲置会休眠，首次访问需等约 30 秒唤醒
  · 因为是 https，iOS 的离线外壳缓存(SW)此时也能生效
  · 备选: Railway(读 Procfile) / Fly.io(读 fly.toml + Dockerfile)
  · 部署平台在国外机房，访问 FAA 通常比国内直连更稳

【手动粘贴通告】(针对 JEP Pro 用户)
  1. 展开页面中"手动粘贴 TAF / NOTAM"
  2. 从 JEP Pro 复制通告原文粘贴
  3. 点 GET BRIEF，粘贴内容自动解析分类
  · 支持标准 ICAO 格式:
    A2923/26 NOTAMN
    Q) WMKK/QMXLC/IV/NBO/A/000/999/
    A) WMKK
    B) 2609250000
    C) 2610312359
    E) TWY E BTN INT E2 AND INT E4 CLSD

【数据来源设置】(页面右上角 ⚙ 按钮)
  NOTAM 来源:
    · 合并(默认) — 在线/缓存 + 手动粘贴，
      同号通告以粘贴内容为准
    · 仅自动 — 忽略粘贴内容
    · 仅手动粘贴 — 只用粘贴的通告
  TAF 来源:
    · 自动(默认) — 在线优先，失败时用粘贴内容
    · 仅手动粘贴
  设置保存在浏览器中，下次打开自动生效

【刷新NOTAM缓存】(服务器模式 · GET BRIEF 旁的按钮)
  强制绕开5分钟缓存，重新在线抓取并写回 notam_cache.json
  弹窗会显示每个机场是"在线成功N条"还是"在线失败(用缓存)"
  建议: 起飞前先点一次，确保用的是最新通告

【文件说明】
  app.html            单文件应用（双击即用，可单独发送）
  start.command       Mac 一键启动服务器
  start.bat           Windows 一键启动服务器
  server.py           Python服务器（方式二/三需要）
  notam_cache.json    服务器模式的NOTAM缓存（自动更新）
  manifest.webmanifest PWA 清单（主屏幕安装用）
  sw.js               PWA Service Worker（离线外壳）
  icon-192.png / icon-512.png / icon-512-maskable.png  App图标
  apple-touch-icon.png  iOS 主屏幕图标
  Dockerfile / Procfile / requirements.txt  公网部署用
  render.yaml / fly.toml / .dockerignore     平台部署配置

【数据来源】
  WX:  Open-Meteo (开放API)
  TAF: AviationWeather.gov
  NOTAM: FAA NOTAM Search (国际机场覆盖较全；
        本地双击模式经浏览器直连/公共CORS代理在线获取，
        国内网络可能受限，此时请用 start.command 服务器
        模式；并建议配合 JEP Pro 手动粘贴核对)
