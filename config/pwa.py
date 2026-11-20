import json

from django.http import HttpResponse, JsonResponse
from django.templatetags.static import static


def manifest(request):
    return JsonResponse({
        'name': 'COMANDA', 'short_name': 'COMANDA', 'lang': 'es', 'start_url': '/', 'scope': '/',
        'display': 'standalone', 'background_color': '#f9fafb', 'theme_color': '#FF441F',
        'description': 'Pide en las cafeterías y papelerías del campus y recíbelo en tu aula.',
        'icons': [{'src': static('img/icon-192.png'), 'sizes': '192x192', 'type': 'image/png'},
                  {'src': static('img/icon-512.png'), 'sizes': '512x512', 'type': 'image/png'}]})


def service_worker(request):
    """Solo guarda en caché los archivos estáticos; las páginas con datos personales nunca se cachean."""
    js = """const CACHE = 'comanda-estaticos-v1';
self.addEventListener('install', e => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim())));
self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET' || !url.pathname.startsWith('/static/')) return;
  e.respondWith(caches.open(CACHE).then(c => c.match(e.request).then(hit => hit || fetch(e.request).then(r => { c.put(e.request, r.clone()); return r; }))));
});"""
    resp = HttpResponse(js, content_type='application/javascript')
    resp['Service-Worker-Allowed'] = '/'
    resp['Cache-Control'] = 'no-cache'
    return resp
