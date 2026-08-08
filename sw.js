// BASystem 서비스워커 — 설치(홈 화면 추가)와 오프라인 실행을 위한 최소 구성.
//
// ⚠️ VERSION 을 올리면 캐시가 통째로 새로 받아진다. 화면이나 실측 반사표를 고치면
//    반드시 같이 올린다 (index.html 의 VERSION 과 같은 값으로).
const VERSION = 'basystem-v1.0.0';
const ASSETS = [
  './', './index.html', './manifest.json',
  './data/table_medium.json', './data/five_half_numbers.json',
  './data/measured_bounce.json', './data/english.json',
  './icons/icon-192.png', './icons/icon-512.png',
];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(VERSION).then(c => c.addAll(ASSETS)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', e => {
  e.waitUntil(caches.keys()
    .then(ks => Promise.all(ks.filter(k => k !== VERSION).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});

// 먼저 네트워크, 안 되면 캐시. 당구장 와이파이가 약해도 열리게 한다.
self.addEventListener('fetch', e => {
  if (e.request.method !== 'GET') return;
  e.respondWith(
    fetch(e.request)
      .then(r => {
        const copy = r.clone();
        caches.open(VERSION).then(c => c.put(e.request, copy));
        return r;
      })
      .catch(() => caches.match(e.request).then(r => r || caches.match('./index.html')))
  );
});
