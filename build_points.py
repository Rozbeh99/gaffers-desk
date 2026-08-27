# -*- coding: utf-8 -*-
"""Builds points.json - what every player actually scored, week by week.

The FPL API keeps scoring in three places and none of them is complete on its own:

  entry/{id}/history/        team totals, rank and bench points per gameweek
  entry/{id}/event/{gw}/picks/   who was in the XI, who was captain, autosubs
  event/{gw}/live/           every player's stats for that gameweek, bonus included

This pulls all three for every finished gameweek and joins them, so the dashboard
can show a player's own score AND what he actually contributed to the team (a
benched player contributes nothing; a captain contributes double).

Only finished gameweeks are read. Bonus is provisional until an event's
data_checked flag is true - that is carried through as `provisional`.
"""
import json
import os
import sys
import urllib.request

sys.stdout.reconfigure(encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
TEAM = json.load(open(os.path.join(HERE, 'team.json'), encoding='utf-8'))['teamId']
API = 'https://fantasy.premierleague.com/api/'


def fetch(path, cache, force=False):
    """GET an endpoint, caching to disk. Finished gameweeks never change, so a
    cached picks/live file is reused; anything still in progress is re-fetched."""
    dest = os.path.join(HERE, cache)
    if os.path.exists(dest) and not force:
        with open(dest, encoding='utf-8') as f:
            return json.load(f)
    req = urllib.request.Request(API + path, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=40) as r:
        raw = r.read()
    with open(dest, 'wb') as f:
        f.write(raw)
    print(f"  fetched {cache}")
    return json.loads(raw.decode('utf-8'))


boot = json.load(open(os.path.join(HERE, 'bootstrap.json'), encoding='utf-8'))
teams = {t['id']: t['short_name'] for t in boot['teams']}
POS = {1: 'GK', 2: 'DEF', 3: 'MID', 4: 'FWD'}
el = {p['id']: p for p in boot['elements']}

# a gameweek counts once it has kicked off; still-live ones are re-fetched each run
played = [e for e in boot['events'] if e['finished'] or e['is_current']]
played = [e for e in played if e['id'] <= (max((x['id'] for x in boot['events']
                                                if x['is_current']), default=0) or 0)
          or e['finished']]
gws = sorted(e['id'] for e in played)
checked = {e['id']: e['data_checked'] for e in boot['events']}
avg_score = {e['id']: e['average_entry_score'] for e in boot['events']}
high_score = {e['id']: e['highest_score'] for e in boot['events']}

history = fetch(f'entry/{TEAM}/history/', 'history.json', force=True)

players = {}          # element id -> record
team_gws = []

for gw in gws:
    settled = checked.get(gw, False)
    picks = fetch(f'entry/{TEAM}/event/{gw}/picks/', f'picks_gw{gw}.json', force=not settled)
    live = fetch(f'event/{gw}/live/', f'live_gw{gw}.json', force=not settled)
    stats = {e['id']: e['stats'] for e in live['elements']}
    subs_in = {s['element_in'] for s in picks.get('automatic_subs', [])}
    subs_out = {s['element_out'] for s in picks.get('automatic_subs', [])}

    eh = picks['entry_history']
    cap_id = next((p['element'] for p in picks['picks'] if p['is_captain']), None)
    vice_id = next((p['element'] for p in picks['picks'] if p['is_vice_captain']), None)

    for pick in picks['picks']:
        pid = pick['element']
        s = stats.get(pid, {})
        base = s.get('total_points', 0)
        mult = pick['multiplier']          # 0 bench, 1 starter, 2 captain, 3 triple
        rec = players.setdefault(pid, {
            'id': pid,
            'name': el[pid]['web_name'] if pid in el else str(pid),
            'full': (el[pid]['first_name'] + ' ' + el[pid]['second_name']).strip() if pid in el else '',
            'club': teams.get(el[pid]['team']) if pid in el else '',
            'pos': POS.get(el[pid]['element_type']) if pid in el else '',
            'gws': {}, 'own': 0, 'counted': 0, 'bonus': 0, 'mins': 0,
            'goals': 0, 'assists': 0, 'cs': 0, 'starts': 0,
        })
        rec['gws'][str(gw)] = {
            'p': base,                                  # what the player scored
            'c': base * mult,                           # what the team banked
            'b': s.get('bonus', 0),
            'm': s.get('minutes', 0),
            'g': s.get('goals_scored', 0),
            'a': s.get('assists', 0),
            'cs': s.get('clean_sheets', 0),
            'mult': mult,
            'role': 'bench' if mult == 0 else 'xi',
            'cap': pid == cap_id,
            'vice': pid == vice_id,
            'subOn': pid in subs_in,
            'subOff': pid in subs_out,
            'prov': not settled,
        }
        rec['own'] += base
        rec['counted'] += base * mult
        rec['bonus'] += s.get('bonus', 0)
        rec['mins'] += s.get('minutes', 0)
        rec['goals'] += s.get('goals_scored', 0)
        rec['assists'] += s.get('assists', 0)
        rec['cs'] += s.get('clean_sheets', 0)
        rec['starts'] += s.get('starts', 0)

    cap_pts = stats.get(cap_id, {}).get('total_points', 0) if cap_id else 0
    team_gws.append({
        'gw': gw,
        'points': eh['points'],                          # already net of hits
        'gross': eh['points'] + eh['event_transfers_cost'],
        'hit': eh['event_transfers_cost'],
        'transfers': eh['event_transfers'],
        'bench': eh['points_on_bench'],
        'rank': eh['overall_rank'],
        'gwRank': eh['rank'],
        'value': round(eh['value'] / 10.0, 1),
        'bank': round(eh['bank'] / 10.0, 1),
        'chip': picks.get('active_chip'),
        'captain': el[cap_id]['web_name'] if cap_id in el else None,
        'captainPts': cap_pts,
        'avg': avg_score.get(gw),
        'best': high_score.get(gw),
        'prov': not checked.get(gw, False),
    })

# rank movement between gameweeks
for i, g in enumerate(team_gws):
    g['rankDelta'] = (team_gws[i - 1]['rank'] - g['rank']) if i else None

cur = history['current']
total = cur[-1]['total_points'] if cur else 0
out = {
    'gws': gws,
    'team': {
        'total': total,
        'rank': cur[-1]['overall_rank'] if cur else None,
        'percentile': cur[-1].get('percentile_rank') if cur else None,
        'managers': boot.get('total_players'),
        'bench': sum(g['bench'] for g in team_gws),
        'hits': sum(g['hit'] for g in team_gws),
        'best': max((g['points'] for g in team_gws), default=0),
        'avgTotal': sum(g['avg'] or 0 for g in team_gws),
        'byGw': team_gws,
    },
    'players': sorted(players.values(), key=lambda r: (-r['counted'], -r['own'])),
    'past': [{'season': p['season_name'], 'points': p['total_points'], 'rank': p['rank']}
             for p in history.get('past', [])],
}

json.dump(out, open(os.path.join(HERE, 'points.json'), 'w', encoding='utf-8'),
          indent=1, ensure_ascii=False)

print(f"points.json written - GW{gws[0] if gws else '-'}"
      f"{'-' + str(gws[-1]) if len(gws) > 1 else ''}, {len(out['players'])} players tracked")
print(f"  team total {total} pts   overall rank {out['team']['rank']:,}"
      f"   {out['team']['bench']} left on the bench   {out['team']['hits']} pts of hits")
scorers = [p for p in out['players'] if p['own']]
for p in sorted(scorers, key=lambda r: -r['own'])[:6]:
    tag = f" (incl {p['bonus']} bonus)" if p['bonus'] else ""
    print(f"  {p['name']:16s} {p['own']:3d} pts{tag}")
blanks = [p['name'] for p in out['players'] if p['own'] <= 1 and p['mins'] > 0]
if blanks:
    print("  played but returned nothing: " + ", ".join(blanks))
