/* Aviation Briefing — service worker
 * 仅缓存"应用外壳"(HTML/manifest/图标)，接口请求一律走网络。
 * 注意: iOS 通过 http://内网IP 访问时 SW 无法注册(需 https/localhost)，
 * 此时离线缓存不可用，但"添加到主屏幕"仍可正常安装。 */
const CACHE = 'avbrief-v1';
const SHELL = ['/', '/manifest.webmanifest', '/icon-192.png', '/icon-512.png', '/apple-touch-icon.png'];

self.addEventListener('install', function (e) {
  e.waitUntil(caches.open(CACHE).then(function (c) { return c.addAll(SHELL); }).then(function () {
    return self.skipWaiting();
  }).catch(function () {}));
});

self.addEventListener('activate', function (e) {
  e.waitUntil(caches.keys().then(function (keys) {
    return Promise.all(keys.map(function (k) { if (k !== CACHE) return caches.delete(k); }));
  }).then(function () { return self.clients.claim(); }));
});

self.addEventListener('fetch', function (e) {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== location.origin) return;          // 外部 API 不拦截
  if (url.pathname.indexOf('/api/') === 0) return;        // 接口不缓存
  e.respondWith(
    caches.match(req).then(function (hit) {
      const net = fetch(req).then(function (res) {
        if (res && res.ok && (url.pathname === '/' || SHELL.indexOf(url.pathname) >= 0)) {
          const clone = res.clone();
          caches.open(CACHE).then(function (c) { c.put(req, clone); });
        }
        return res;
      }).catch(function () { return hit; });
      return hit || net;
    })
  );
});
