# -*- coding: utf-8 -*-
"""Builds squad.json — the data the dashboard page reads.
Re-run after each bootstrap pull to refresh prices, status and fixtures."""
import json, csv, sys

d = json.load(open('bootstrap.json', encoding='utf-8'))
teams = {t['id']: t['name'] for t in d['teams']}
short = {t['id']: t['short_name'] for t in d['teams']}
name_to_tid = {t['name']: t['id'] for t in d['teams']}
rows = {r['id']: r for r in csv.DictReader(open('players.csv', encoding='utf-8'))}
by_key = {r['web_name'] + '|' + r['team_name']: r for r in rows.values()}

events = d['events']
next_gw = next((e['id'] for e in events if e['is_next']), None)
cur_gw = next((e['id'] for e in events if e['is_current']), None)
# the gameweek he can still act on: the first one not finished. is_current lags,
# it keeps pointing at the completed gameweek until the next one kicks off.
open_gw = next((e['id'] for e in events if not e['finished']), None)
anchor = open_gw or next_gw or cur_gw or 1
deadline = next((e['deadline_time'] for e in events if e['id'] == anchor), None)

fx = json.load(open('fixtures.json', encoding='utf-8'))
FN = 5  # fixtures to show per player
team_fix = {tid: [] for tid in teams}
for m in sorted([m for m in fx if m['event'] and anchor <= m['event'] < anchor + FN],
                key=lambda x: (x['event'], x['kickoff_time'] or '')):
    team_fix[m['team_h']].append({'gw': m['event'], 'opp': short[m['team_a']], 'ha': 'H',
                                  'fdr': m['team_h_difficulty']})
    team_fix[m['team_a']].append({'gw': m['event'], 'opp': short[m['team_h']], 'ha': 'A',
                                  'fdr': m['team_a_difficulty']})


LEDGER = json.load(open('prices.json', encoding='utf-8'))['bought']

def selling_price(name, now):
    """FPL rule: you keep what you paid plus HALF the rise, rounded down to 0.1.
    A price fall is absorbed in full - you sell at the lower current price."""
    paid = LEDGER.get(name, {}).get('price')
    if paid is None:
        return now, 0.0, None            # unknown purchase price: assume market
    rise = round(now - paid, 1)
    if rise <= 0:
        return now, rise, paid           # fallen (or level): sell at current price
    keep = int(round(rise * 10)) // 2    # half the rise, in 0.1m units, rounded down
    return round(paid + keep / 10.0, 1), rise, paid

def pack(key, role):
    r = by_key[key]
    tid = name_to_tid[r['team_name']]
    sell, rise, paid = selling_price(r['web_name'], float(r['now_cost']))
    return {
        'id': int(r['id']), 'name': r['web_name'],
        'sell': sell, 'rise': rise, 'paid': paid, 'full': (r['first_name'] + ' ' + r['second_name']).strip(),
        'club': short[tid], 'clubName': r['team_name'], 'pos': r['position'],
        'price': float(r['now_cost']), 'sel': float(r['selected_by_percent'] or 0),
        'pts': int(r['total_points'] or 0), 'ppg': float(r['points_per_game'] or 0),
        'starts': int(r['starts'] or 0), 'mins': int(r['minutes'] or 0),
        'status': r['status'], 'chance': r['chance_of_playing_next_round'], 'news': r['news'],
        'role': role, 'fixtures': team_fix[tid][:FN],
    }

SQUAD = [
    ('Raya|Arsenal', 'xi'), ('Dubravka|Spurs', 'bench'),
    ('Calafiori|Arsenal', 'xi'), ('Virgil|Liverpool', 'xi'), ('Guéhi|Man City', 'xi'),
    ('Shaw|Man Utd', 'xi'), ('van Ewijk|Coventry City', 'bench'),
    ('B.Fernandes|Man Utd', 'xi'), ('Szoboszlai|Liverpool', 'xi'), ('Anderson|Man City', 'xi'),
    ('Hughes|Crystal Palace', 'bench'), ('Slater|Hull City', 'bench'),
    ('Haaland|Man City', 'xi'), ('João Pedro|Chelsea', 'xi'), ('Calvert-Lewin|Leeds', 'xi'),
]
squad = [pack(k, r) for k, r in SQUAD]

ADVICE = json.load(open('advice.json', encoding='utf-8'))
MOVES = json.load(open('moves.json', encoding='utf-8'))
moves = []
for m in MOVES:
    o, i = by_key[m['out']], by_key[m['in']]
    moves.append({'out': pack(m['out'], 'out'), 'in': pack(m['in'], 'in'),
                  'delta': round(float(i['now_cost']) - float(o['now_cost']), 1),
                  'priority': m['priority'], 'reason': m['reason'], 'gain': m['gain']})

out = {
    'generated': None,           # stamped by the shell after the script runs
    'gw': anchor, 'deadline': deadline,
    'budget': 100.0,
    'sellValue': round(sum(p['sell'] for p in squad), 1),
    'marketValue': round(sum(p['price'] for p in squad), 1),
    'squad': squad, 'moves': moves,
    'captain': 'Haaland', 'vice': 'B.Fernandes',
    'chips': {'available': ['Wildcard x2', 'Free Hit x2', 'Bench Boost x2', 'Triple Captain x2'],
              'advice': 'Play none in GW2. Your bench scored 7 in GW1, so a Bench Boost is not yet worth a chip, and no doubles exist. The consensus play is the first Wildcard around GW4, after the transfer window shuts on 1 September and two more gameweeks of real form data. Remember both chip sets expire at the GW19 deadline on 2 Jan 2027 - they do not carry over.'},
    'benchOrder': ['Slater', 'Hughes', 'van Ewijk', 'Dubravka'],
    'advice': ADVICE,          # the verdict panel renders only if this is present

}
json.dump(out, open('squad.json', 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
print(f"squad.json written - GW{anchor}, deadline {deadline}, {len(squad)} players, {len(moves)} moves")
mkt = sum(p['price'] for p in squad)
sell = sum(p['sell'] for p in squad)
print(f"market value GBP {mkt:.1f}m   sell value GBP {sell:.1f}m   locked in rises GBP {mkt-sell:.1f}m")
risers = [p for p in squad if p['rise'] > 0]
fallers = [p for p in squad if p['rise'] < 0]
for p in sorted(risers, key=lambda x: -x['rise']):
    print(f"  UP   {p['name']:15s} paid {p['paid']:.1f} -> now {p['price']:.1f} (+{p['rise']:.1f})  sells for {p['sell']:.1f}")
for p in sorted(fallers, key=lambda x: x['rise']):
    print(f"  DOWN {p['name']:15s} paid {p['paid']:.1f} -> now {p['price']:.1f} ({p['rise']:.1f})  sells for {p['sell']:.1f}")
if not risers and not fallers:
    print("  no price movement yet")
