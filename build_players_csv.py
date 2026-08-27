import json
import csv
from collections import defaultdict

with open('bootstrap.json', encoding='utf-8') as f:
    d = json.load(f)

teams = {t['id']: t['name'] for t in d['teams']}
pos = {1: 'GK', 2: 'DEF', 3: 'MID', 4: 'FWD'}
threshold = {1: None, 2: 10, 3: 12, 4: 12}  # GK has no DefCon

# current gameweek = last event with is_current True, else the next unfinished one
events = d['events']
current_gw = next((e['id'] for e in events if e['is_current']), None)
next_gw = next((e['id'] for e in events if e['is_next']), None)
# anchor on the gameweek still to be played - once GW1 is finished the decisions
# and fixtures that matter are GW2's, even while is_current still points at GW1
open_gw = next((e['id'] for e in events if not e['finished']), None)
anchor_gw = open_gw or next_gw or current_gw or 1
print(f"current_gw={current_gw} next_gw={next_gw} anchor_gw={anchor_gw}")

fields = [
    'id', 'web_name', 'first_name', 'second_name', 'team_name', 'position',
    'now_cost', 'selected_by_percent', 'cost_change_start', 'cost_change_event',
    'transfers_in_event', 'transfers_out_event',
    'total_points', 'points_per_game', 'form', 'bonus', 'bps', 'value_season',
    'starts', 'minutes',
    'goals_scored', 'assists', 'expected_goals', 'expected_assists',
    'expected_goal_involvements', 'penalties_order', 'corners_and_indirect_freekicks_order',
    'defensive_contribution', 'clearances_blocks_interceptions', 'recoveries', 'tackles',
    'clean_sheets', 'goals_conceded', 'expected_goals_conceded', 'saves',
    'status', 'chance_of_playing_next_round', 'news', 'news_added',
    # derived
    'points_per_million', 'points_per_90', 'defcon_per_90', 'defcon_threshold',
    'defcon_avg_meets_threshold', 'goals_per_90', 'assists_per_90',
    'xgi_per_90', 'availability_flag',
]

rows = []
for p in d['elements']:
    minutes = p['minutes'] or 0
    now_cost = p['now_cost'] / 10.0
    total_points = p['total_points']
    defcon = p['defensive_contribution'] or 0
    goals = p['goals_scored'] or 0
    assists = p['assists'] or 0
    xgi = float(p['expected_goal_involvements'] or 0)

    per90 = (lambda v: round(v / minutes * 90, 3) if minutes > 0 else None)

    et = p['element_type']
    thr = threshold.get(et)
    defcon_per90 = per90(defcon)
    meets_avg = None
    if thr is not None and defcon_per90 is not None:
        meets_avg = defcon_per90 >= thr

    flag = (p['status'] != 'a') or (
        p['chance_of_playing_next_round'] is not None and p['chance_of_playing_next_round'] < 100
    )

    row = {
        'id': p['id'],
        'web_name': p['web_name'],
        'first_name': p['first_name'],
        'second_name': p['second_name'],
        'team_name': teams.get(p['team'], ''),
        'position': pos.get(et, ''),
        'now_cost': now_cost,
        'selected_by_percent': p['selected_by_percent'],
        'cost_change_start': p['cost_change_start'] / 10.0,
        'cost_change_event': p['cost_change_event'] / 10.0,
        'transfers_in_event': p['transfers_in_event'],
        'transfers_out_event': p['transfers_out_event'],
        'total_points': total_points,
        'points_per_game': p['points_per_game'],
        'form': p['form'],
        'bonus': p['bonus'],
        'bps': p['bps'],
        'value_season': p['value_season'],
        'starts': p['starts'],
        'minutes': minutes,
        'goals_scored': goals,
        'assists': assists,
        'expected_goals': p['expected_goals'],
        'expected_assists': p['expected_assists'],
        'expected_goal_involvements': p['expected_goal_involvements'],
        'penalties_order': p['penalties_order'],
        'corners_and_indirect_freekicks_order': p['corners_and_indirect_freekicks_order'],
        'defensive_contribution': defcon,
        'clearances_blocks_interceptions': p['clearances_blocks_interceptions'],
        'recoveries': p['recoveries'],
        'tackles': p['tackles'],
        'clean_sheets': p['clean_sheets'],
        'goals_conceded': p['goals_conceded'],
        'expected_goals_conceded': p['expected_goals_conceded'],
        'saves': p['saves'],
        'status': p['status'],
        'chance_of_playing_next_round': p['chance_of_playing_next_round'],
        'news': p['news'],
        'news_added': p['news_added'],
        'points_per_million': round(total_points / now_cost, 2) if now_cost > 0 else None,
        'points_per_90': per90(total_points),
        'defcon_per_90': defcon_per90,
        'defcon_threshold': thr,
        'defcon_avg_meets_threshold': meets_avg,
        'goals_per_90': per90(goals),
        'assists_per_90': per90(assists),
        'xgi_per_90': per90(xgi),
        'availability_flag': flag,
    }
    rows.append(row)

rows.sort(key=lambda r: (r['total_points'] or 0), reverse=True)

with open('players.csv', 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    w.writerows(rows)

print(f"Wrote {len(rows)} players to players.csv")

# ---- Fixture difficulty + double/blank gameweek table ----
# Window: next 10 gameweeks from the current/upcoming one (rolling, not hardcoded).
with open('fixtures.json', encoding='utf-8') as f:
    fx = json.load(f)

WINDOW = 10
gw_range = list(range(anchor_gw, anchor_gw + WINDOW))

team_gw_fdr = defaultdict(dict)     # team -> gw -> [difficulty, difficulty, ...] (2 entries = DGW)
team_gw_opp = defaultdict(dict)     # team -> gw -> ["OPP (H/A)", ...]
for match in fx:
    gw = match['event']
    if gw is None or gw not in gw_range:
        continue
    th, ta = match['team_h'], match['team_a']
    team_gw_fdr[th].setdefault(gw, []).append(match['team_h_difficulty'])
    team_gw_fdr[ta].setdefault(gw, []).append(match['team_a_difficulty'])
    team_gw_opp[th].setdefault(gw, []).append(f"{teams.get(ta,'?')} (H)")
    team_gw_opp[ta].setdefault(gw, []).append(f"{teams.get(th,'?')} (A)")

fdr_fields = ['team'] + [f'gw{g}' for g in gw_range] + ['avg_fdr', 'blank_gws', 'double_gws']
with open('fixture_difficulty.csv', 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=fdr_fields)
    w.writeheader()
    for tid in sorted(teams, key=lambda x: teams[x]):
        row = {'team': teams[tid]}
        vals = []
        blanks, doubles = [], []
        for gw in gw_range:
            fdrs = team_gw_fdr[tid].get(gw, [])
            opps = team_gw_opp[tid].get(gw, [])
            if not fdrs:
                row[f'gw{gw}'] = 'BLANK'
                blanks.append(str(gw))
            elif len(fdrs) == 1:
                row[f'gw{gw}'] = f"{opps[0]} [{fdrs[0]}]"
                vals.append(fdrs[0])
            else:
                row[f'gw{gw}'] = ' + '.join(f"{o} [{fd}]" for o, fd in zip(opps, fdrs))
                doubles.append(str(gw))
                vals.extend(fdrs)
        row['avg_fdr'] = round(sum(vals) / len(vals), 2) if vals else None
        row['blank_gws'] = ';'.join(blanks)
        row['double_gws'] = ';'.join(doubles)
        w.writerow(row)

print(f"Wrote fixture_difficulty.csv for GW{gw_range[0]}-GW{gw_range[-1]}")
