# -*- coding: utf-8 -*-
"""Injects squad.json + season.json + points.json into template.html -> index.html."""
import json, datetime, os, re, sys

sys.stdout.reconfigure(encoding='utf-8')

squad = json.load(open('squad.json', encoding='utf-8'))
season = json.load(open('season.json', encoding='utf-8'))
points = json.load(open('points.json', encoding='utf-8')) if os.path.exists('points.json') else None
squad['generated'] = datetime.datetime.now(datetime.timezone.utc).strftime('%d %b %Y, %H:%M UTC')

html = open('template.html', encoding='utf-8').read()
html = html.replace('/*__SQUAD__*/null', json.dumps(squad, ensure_ascii=False))
html = html.replace('/*__SEASON__*/null', json.dumps(season, ensure_ascii=False))
html = html.replace('/*__POINTS__*/null', json.dumps(points, ensure_ascii=False))
open('index.html', 'w', encoding='utf-8').write(html)

# --- integrity checks ---
errs = []
for m in re.findall(r'<script(?:(?!src=)[^>])*>(.*?)</script>', html, re.S):
    for o, c in [('{', '}'), ('[', ']'), ('(', ')')]:
        if m.count(o) != m.count(c):
            errs.append(f'script unbalanced {o}{c}: {m.count(o)} vs {m.count(c)}')

# JavaScript inside <style> silently kills every rule after it and never runs.
# This has happened once - a whole render block was pasted into the stylesheet -
# and the page shipped looking half-styled with no verdict panel. Never again.
for m in re.findall(r'<style[^>]*>(.*?)</style>', html, re.S):
    for token in ('function ', 'var ', 'addEventListener', 'innerHTML', 'localStorage'):
        if token in m:
            errs.append(f'JavaScript found inside <style>: "{token.strip()}"')

# the verdict panel renders only when DATA.advice exists. It silently rendered
# nothing for a day because advice.json was written but never loaded.
if not squad.get('advice'):
    errs.append('squad.json has no advice - the verdict panel will not render')
else:
    missing = [k for k in ('verdict', 'headline', 'body', 'evidence', 'watch')
               if k not in squad['advice']]
    if missing:
        errs.append(f'advice is missing {missing}')

if '/*__SQUAD__*/' in html or '/*__SEASON__*/' in html or '/*__POINTS__*/' in html:
    errs.append('a data placeholder was not replaced')

# every id the script writes to must exist in the markup
for ident in re.findall(r"\$\('([A-Za-z0-9_-]+)'\)", html):
    if f'id="{ident}"' not in html:
        errs.append(f'script targets #{ident}, which is not in the page')

print('index.html written', f'({len(html):,} bytes)')
if points:
    print(f"  points: {points['team']['total']} pts, {len(points['gws'])} gameweek(s), "
          f"{len(points['players'])} players")
print('CHECKS:', 'all passed' if not errs else sorted(set(errs)))
if errs:
    sys.exit(1)
