// service-worker.js — ABpE Softphone PWA Service Worker
const CACHE_NAME = 'abpe-softphone-v6';

// Nur statische Assets cachen — KEINE API-Calls, KEINE Kontakte
const PRECACHE = [
    '/static/abpe_crm/softphone/css/softphone.css',
    '/static/abpe_crm/softphone/js/vendor/jssip.min.js',
    '/static/abpe_crm/softphone/js/2_sp-config.js',
    '/static/abpe_crm/softphone/js/3_sp-i18n.js',
    '/static/abpe_crm/softphone/js/4_sp-theme.js',
    '/static/abpe_crm/softphone/js/5_sp-lang.js',
    '/static/abpe_crm/softphone/js/5_sp-contacts.js',
    '/static/abpe_crm/softphone/js/6_sp-core.js',
    '/static/abpe_crm/softphone/js/7_sp-ui.js',
    '/static/abpe_crm/softphone/js/8_sp-status.js',
    '/static/abpe_crm/softphone/js/9_sp-transfer.js',
    '/static/abpe_crm/softphone/js/10_sp-fop.js',
    '/static/abpe_crm/softphone/js/11_sp-init.js',
    '/static/abpe_crm/softphone/i18n/de_phone.json',
    '/static/abpe_crm/softphone/i18n/en_phone.json',
    '/static/abpe_crm/softphone/i18n/fr_phone.json',
    '/static/abpe_crm/softphone/i18n/es_phone.json',
    '/static/abpe_crm/softphone/i18n/it_phone.json',
    '/static/abpe_crm/softphone/i18n/pl_phone.json',
    '/static/abpe_crm/softphone/i18n/ru_phone.json',
    '/static/abpe_crm/softphone/i18n/ar_phone.json',
    '/static/abpe_crm/softphone/i18n/zh_phone.json',
    '/static/abpe_crm/softphone/manifest.json',
    // HTML-Seite zuletzt — nach den Assets
    '/crm/softphone/',
];

self.addEventListener('install', function(e) {
    e.waitUntil(
        caches.open(CACHE_NAME).then(function(cache) {
            // allSettled: ein fehlgeschlagener Asset stoppt nicht alles
            return Promise.allSettled(
                PRECACHE.map(function(url) { return cache.add(url); })
            );
        })
    );
    self.skipWaiting();
});

self.addEventListener('activate', function(e) {
    e.waitUntil(
        caches.keys().then(function(keys) {
            return Promise.all(
                keys.filter(function(k) { return k !== CACHE_NAME; })
                    .map(function(k) { return caches.delete(k); })
            );
        })
    );
    self.clients.claim();
});

self.addEventListener('fetch', function(e) {
    var url = e.request.url;

    // API-Calls, WS, Kontakte NIEMALS cachen
    if (url.includes('/crm/api/')
     || url.includes('/api/')
     || url.startsWith('wss://')
     || url.startsWith('ws://')
     || url.includes('contacts')) {
        return; // netzwerk direkt, kein cache
    }

    e.respondWith(
        caches.match(e.request).then(function(cached) {
            if (cached) return cached;
            return fetch(e.request).catch(function() {
                if (e.request.mode === 'navigate') {
                    return caches.match('/crm/softphone/');
                }
            });
        })
    );
});
