// PrecioValida Service Worker — cache básico del shell de la app
const CACHE = 'precio-valida-v1';
const ASSETS = [
  '/static/css/app.css',
  '/static/js/ocr.js',
  'https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,400;12..96,600;12..96,700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;600;700&display=swap',
  'https://unpkg.com/tesseract.js@5.1.1/dist/tesseract.min.js'
];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(ASSETS).catch(()=>{})));
  self.skipWaiting();
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
  );
  self.clients.claim();
});

self.addEventListener('fetch', e => {
  const { request } = e;
  // Solo cachear GET de assets estáticos
  if (request.method !== 'GET') return;
  const url = new URL(request.url);
  const isStatic = url.pathname.startsWith('/static/') ||
                   url.hostname === 'fonts.googleapis.com' ||
                   url.hostname === 'fonts.gstatic.com' ||
                   url.hostname === 'unpkg.com';
  if (!isStatic) return;
  e.respondWith(
    caches.match(request).then(cached => cached || fetch(request).then(res => {
      if (res.ok) {
        const clone = res.clone();
        caches.open(CACHE).then(c => c.put(request, clone));
      }
      return res;
    }).catch(() => cached))
  );
});
