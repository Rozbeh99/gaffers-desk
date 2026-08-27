# -*- coding: utf-8 -*-
"""Assembles docs/ - the installable, publicly hosted version of the dashboard.

The artifact on claude.ai needs a login and cannot be opened offline. This build
produces the same page as a self-contained static site: a web manifest so it
installs to a home screen, real icon files, a service worker so it opens without
a signal, and the four JSON files served at fixed paths as a read-only API.

SANITISING IS THE POINT OF THIS FILE. season.json carries a `setup` block with
the ntfy topic in it, and that topic is a write endpoint - anyone who learns it
can push notifications to his phone. It is stripped here, and the build refuses
to write anything if it survives.
"""
import datetime
import io
import json
import os
import re
import sys

import make_icon

sys.stdout.reconfigure(encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'docs')

SITE_NAME = "The Gaffer's Desk"
SHORT_NAME = "Gaffer"
THEME_DARK = '#0A120F'
THEME_LIGHT = '#EDF1EC'

# anything matching these must never appear in the published bundle
FORBIDDEN = [
    (re.compile(r'gaffer-babadook-[0-9a-f]+'), 'the ntfy topic'),
    (re.compile(r'ntfy\.sh/[A-Za-z0-9_-]+'), 'an ntfy endpoint'),
    (re.compile(r'trig_[A-Za-z0-9]+'), 'the routine id'),
]


def public_season(season):
    """Drop everything from `setup` except the corrections log, which is the one
    part worth publishing - it is the record of calls that were wrong."""
    s = json.loads(json.dumps(season))
    setup = s.pop('setup', {})
    if setup.get('corrections'):
        s['corrections'] = setup['corrections']
    return s


def scan(text, where):
    for pat, what in FORBIDDEN:
        m = pat.search(text)
        if m:
            raise SystemExit(f"REFUSING TO BUILD: {what} ({m.group(0)}) found in {where}")


# ---------------------------------------------------------------- data
squad = json.load(io.open(os.path.join(HERE, 'squad.json'), encoding='utf-8'))
season = json.load(io.open(os.path.join(HERE, 'season.json'), encoding='utf-8'))
points = json.load(io.open(os.path.join(HERE, 'points.json'), encoding='utf-8'))
advice = json.load(io.open(os.path.join(HERE, 'advice.json'), encoding='utf-8'))
season_pub = public_season(season)

# squad.json carries generated=None; build_page.py stamps its own copy at render
# time. Stamp ours the same way so the footer and the cache key are real.
squad['generated'] = datetime.datetime.now(datetime.timezone.utc).strftime(
    '%d %b %Y, %H:%M UTC')

os.makedirs(OUT, exist_ok=True)

# ---------------------------------------------------------------- the page
template = io.open(os.path.join(HERE, 'template.html'), encoding='utf-8').read()
html = template
html = html.replace('/*__SQUAD__*/null', json.dumps(squad, ensure_ascii=False))
html = html.replace('/*__SEASON__*/null', json.dumps(season_pub, ensure_ascii=False))
html = html.replace('/*__POINTS__*/null', json.dumps(points, ensure_ascii=False))

# the hosted build is a real document, not an artifact fragment
head = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<link rel="manifest" href="manifest.webmanifest">
<link rel="apple-touch-icon" href="icon-180.png">
"""
# template.html is an artifact fragment: head content and body content run
# together with no <head>/<body> of their own. Split it at the masthead so the
# hosted build is a well-formed document rather than relying on tag inference.
assert '<header class="top">' in html
html = html.replace('<header class="top">',
                    '</head>\n<body>\n<header class="top">', 1)

html = head + html + """
<script>
if('serviceWorker' in navigator){
  addEventListener('load', function(){
    navigator.serviceWorker.register('sw.js').catch(function(){});
  });
}
</script>
</body>
</html>
"""

scan(html, 'docs/index.html')
io.open(os.path.join(OUT, 'index.html'), 'w', encoding='utf-8').write(html)

# ---------------------------------------------------------------- the API
api = {
    'squad.json': squad,
    'points.json': points,
    'advice.json': advice,
    'season.json': season_pub,
}
for name, payload in api.items():
    text = json.dumps(payload, ensure_ascii=False, indent=1)
    scan(text, 'docs/' + name)
    io.open(os.path.join(OUT, name), 'w', encoding='utf-8').write(text)

io.open(os.path.join(OUT, 'api.json'), 'w', encoding='utf-8').write(json.dumps({
    'name': SITE_NAME,
    'team': {'id': season['teamId'], 'name': season['teamName']},
    'generated': squad.get('generated'),
    'gameweek': squad.get('gw'),
    'endpoints': {
        'squad.json': 'the 15, with prices, selling prices, status and the next five fixtures',
        'points.json': 'every score and bonus per gameweek, team totals, rank, past seasons',
        'advice.json': 'this gameweek\'s verdict, evidence and watchlist',
        'season.json': 'the running log of every gameweek and every transfer',
    },
    'note': 'Read-only. Rebuilt from the official FPL API on a schedule; '
            'the verdict in advice.json is updated when the weekly analysis runs.',
}, ensure_ascii=False, indent=1))

# ---------------------------------------------------------------- manifest
manifest = {
    'name': SITE_NAME,
    'short_name': SHORT_NAME,
    'description': 'Fantasy Premier League squad console: the XI, what everyone '
                   'scored, and the moves to make before the deadline.',
    'start_url': './',
    'scope': './',
    'display': 'standalone',
    'orientation': 'portrait-primary',
    'background_color': THEME_DARK,
    'theme_color': THEME_DARK,
    'icons': [
        {'src': 'icon-192.png', 'sizes': '192x192', 'type': 'image/png', 'purpose': 'any'},
        {'src': 'icon-512.png', 'sizes': '512x512', 'type': 'image/png', 'purpose': 'any'},
        {'src': 'icon-512.png', 'sizes': '512x512', 'type': 'image/png', 'purpose': 'maskable'},
    ],
}
io.open(os.path.join(OUT, 'manifest.webmanifest'), 'w', encoding='utf-8').write(
    json.dumps(manifest, indent=1))

# ---------------------------------------------------------------- icons
icons = make_icon.write_files(OUT)

# ---------------------------------------------------------------- service worker
# Network-first for the page and the API so an online open is always current;
# the cache is the fallback that makes it open at all with no signal.
sw = """/* The Gaffer's Desk - offline shell. Bumping CACHE evicts the old one. */
var CACHE = 'gaffer-%s';
var SHELL = ['./', './index.html', './manifest.webmanifest',
             './icon-180.png', './icon-192.png', './icon-512.png'];

self.addEventListener('install', function(e){
  self.skipWaiting();
  e.waitUntil(caches.open(CACHE).then(function(c){ return c.addAll(SHELL); }));
});

self.addEventListener('activate', function(e){
  e.waitUntil(caches.keys().then(function(keys){
    return Promise.all(keys.filter(function(k){ return k !== CACHE; })
                           .map(function(k){ return caches.delete(k); }));
  }).then(function(){ return self.clients.claim(); }));
});

self.addEventListener('fetch', function(e){
  var req = e.request;
  if(req.method !== 'GET') return;
  var url = new URL(req.url);
  var sameOrigin = url.origin === location.origin;

  // fonts: serve from cache, refresh in the background
  if(!sameOrigin){
    e.respondWith(caches.match(req).then(function(hit){
      var net = fetch(req).then(function(res){
        if(res && (res.ok || res.type === 'opaque')){
          caches.open(CACHE).then(function(c){ c.put(req, res.clone()); });
        }
        return res;
      }).catch(function(){ return hit; });
      return hit || net;
    }));
    return;
  }

  // page and data: fresh when online, last known copy when not
  e.respondWith(fetch(req).then(function(res){
    if(res && res.ok){
      var copy = res.clone();
      caches.open(CACHE).then(function(c){ c.put(req, copy); });
    }
    return res;
  }).catch(function(){
    return caches.match(req).then(function(hit){
      return hit || caches.match('./index.html');
    });
  }));
});
""" % re.sub(r'[^0-9A-Za-z]', '', squad['generated'])
io.open(os.path.join(OUT, 'sw.js'), 'w', encoding='utf-8').write(sw)

# GitHub Pages would otherwise run the output through Jekyll
io.open(os.path.join(OUT, '.nojekyll'), 'w', encoding='utf-8').write('')

print(f"docs/ built - GW{squad.get('gw')}, generated {squad.get('generated')}")
print(f"  index.html   {os.path.getsize(os.path.join(OUT, 'index.html')):,} bytes")
for name in list(api) + ['api.json', 'manifest.webmanifest', 'sw.js']:
    print(f"  {name:22s} {os.path.getsize(os.path.join(OUT, name)):,} bytes")
for n, size in icons:
    print(f"  icon-{n}.png{'':11s} {size:,} bytes".replace('  icon', '  icon'))
print("  secrets scan: clean")
