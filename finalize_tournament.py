#!/usr/bin/env python3
"""
Tournament Finalization Script - FIXED
Fetches final results from ESPN or DataGolf and updates picks in Supabase

The key fix: ESPN has TWO endpoints with DIFFERENT structures:
  - leaderboard: has status.position.displayName AND earnings - USE THIS ONE
  - scoreboard: has order field but NO position object, different competitor structure

Usage:
    python finalize_tournament.py <tournament_id>
    python finalize_tournament.py <tournament_id> --liv
    python finalize_tournament.py <tournament_id> --liv --datagolf
    python finalize_tournament.py <tournament_id> --champions
    python finalize_tournament.py <tournament_id> --debug
    python finalize_tournament.py <tournament_id> --list-events
    python finalize_tournament.py <tournament_id> --event-id <id>
    python finalize_tournament.py <tournament_id> --manual <file>
"""

import sys
import json
import csv
import os
import requests
from datetime import datetime

# Supabase config
SUPABASE_URL = 'https://ttwtifdhlaijdswhehve.supabase.co'
SUPABASE_ANON_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InR0d3RpZmRobGFpamRzd2hlaHZlIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2NzQ5NzkxNiwiZXhwIjoyMDgzMDczOTE2fQ.mM6flxplaQtbKByv1ixGScMeNTytZ0jZBfyXzFgpRUc'
SUPABASE_KEY = os.environ.get('SUPABASE_SERVICE_KEY', SUPABASE_ANON_KEY)

# ESPN API - LEADERBOARD endpoints (these have position.displayName + earnings)
ESPN_LEADERBOARD_APIS = {
    'pga': 'https://site.web.api.espn.com/apis/site/v2/sports/golf/leaderboard?league=pga',
    'liv': 'https://site.web.api.espn.com/apis/site/v2/sports/golf/leaderboard?league=liv',
    'champions': 'https://site.web.api.espn.com/apis/site/v2/sports/golf/leaderboard?league=champions-tour',
}

# ESPN API - SCOREBOARD endpoints (fallback - different structure, less data)
ESPN_SCOREBOARD_APIS = {
    'pga': 'https://site.api.espn.com/apis/site/v2/sports/golf/pga/scoreboard',
    'liv': 'https://site.api.espn.com/apis/site/v2/sports/golf/liv/scoreboard',
    'champions': 'https://site.api.espn.com/apis/site/v2/sports/golf/champions-tour/scoreboard',
}

DEBUG = False
TOUR = 'pga'
USE_DATAGOLF = False

# DataGolf API
DATAGOLF_KEY = '92ca1f66aca56167b4f6e780a6de'
DATAGOLF_TOURS = {'pga': 'pga', 'liv': 'alt', 'champions': 'cha'}

# Fallback payout percentages (PGA Tour standard)
PGA_PAYOUTS = {
    1: 0.18, 2: 0.109, 3: 0.069, 4: 0.049, 5: 0.041,
    6: 0.0363, 7: 0.0338, 8: 0.0313, 9: 0.0293, 10: 0.0273,
    11: 0.0253, 12: 0.0233, 13: 0.0213, 14: 0.0193, 15: 0.0183,
    16: 0.0173, 17: 0.0163, 18: 0.0153, 19: 0.0143, 20: 0.0133,
    21: 0.0123, 22: 0.0113, 23: 0.0105, 24: 0.0097, 25: 0.0089,
    26: 0.0081, 27: 0.0078, 28: 0.0075, 29: 0.0072, 30: 0.0069,
    31: 0.0066, 32: 0.0063, 33: 0.006, 34: 0.0057, 35: 0.0055,
    36: 0.0052, 37: 0.005, 38: 0.0048, 39: 0.0046, 40: 0.0044,
    41: 0.0042, 42: 0.004, 43: 0.0038, 44: 0.0036, 45: 0.0034,
    46: 0.0032, 47: 0.003, 48: 0.0028, 49: 0.0027, 50: 0.0026,
    51: 0.0025, 52: 0.0025, 53: 0.0024, 54: 0.0024, 55: 0.0024,
    56: 0.0023, 57: 0.0023, 58: 0.0023, 59: 0.0023, 60: 0.0023,
    61: 0.0022, 62: 0.0022, 63: 0.0022, 64: 0.0022, 65: 0.0022,
    66: 0.0021, 67: 0.0021, 68: 0.0021, 69: 0.0021, 70: 0.0021,
    71: 0.0020, 72: 0.0020, 73: 0.0020, 74: 0.0020, 75: 0.0020,
    76: 0.0019, 77: 0.0019, 78: 0.0019, 79: 0.0019, 80: 0.0019,
    81: 0.0018, 82: 0.0018, 83: 0.0018, 84: 0.0018, 85: 0.0018,
    86: 0.0017, 87: 0.0017, 88: 0.0017, 89: 0.0017, 90: 0.0017,
}

# LIV Golf individual payout structure ($20M individual purse for 2026)
LIV_PAYOUTS = {
    1: 4000000, 2: 2250000, 3: 1500000, 4: 1000000, 5: 800000,
    6: 700000, 7: 600000, 8: 525000, 9: 450000, 10: 415000,
    11: 380000, 12: 360000, 13: 340000, 14: 320000, 15: 300000,
    16: 285000, 17: 270000, 18: 260000, 19: 250000, 20: 240000,
    21: 230000, 22: 220000, 23: 210000, 24: 200000, 25: 195000,
    26: 190000, 27: 185000, 28: 180000, 29: 175000, 30: 170000,
    31: 165000, 32: 160000, 33: 155000, 34: 150000, 35: 147500,
    36: 145000, 37: 142500, 38: 140000, 39: 137500, 40: 135000,
    41: 132500, 42: 130000, 43: 129000, 44: 128000, 45: 127000,
    46: 126000, 47: 50000, 48: 50000, 49: 50000, 50: 50000,
    51: 50000, 52: 50000, 53: 50000, 54: 50000, 55: 50000,
    56: 50000, 57: 50000,
}


def calculate_tie_adjusted_earnings(leaderboard, purse):
    """Calculate tie-adjusted earnings for all players using payout percentages."""
    payouts = PGA_PAYOUTS
    max_pos = 90

    position_groups = {}
    for key, data in leaderboard.items():
        pos = data['position']
        if pos in ('CUT', 'MC', 'WD', 'DQ', '-', ''):
            data['earnings'] = 0
            continue
        if pos not in position_groups:
            position_groups[pos] = []
        position_groups[pos].append(key)

    for pos, player_keys in position_groups.items():
        try:
            pos_num = int(pos.replace('T', '').strip())
        except ValueError:
            for key in player_keys:
                leaderboard[key]['earnings'] = 0
            continue

        if pos_num > max_pos:
            for key in player_keys:
                leaderboard[key]['earnings'] = 0
            continue

        num_tied = len(player_keys)
        total_payout_pct = sum(payouts.get(pos_num + i, 0.002) for i in range(num_tied) if pos_num + i <= max_pos)
        per_player_pct = total_payout_pct / num_tied
        earnings = int(purse * per_player_pct)

        for key in player_keys:
            leaderboard[key]['earnings'] = earnings

    return leaderboard


def calculate_liv_earnings(leaderboard):
    """Calculate LIV earnings using fixed payout amounts (no cuts in LIV)."""
    position_groups = {}
    for key, data in leaderboard.items():
        pos = data['position']
        if pos in ('WD', 'DQ', '-', ''):
            data['earnings'] = 0
            continue
        if pos not in position_groups:
            position_groups[pos] = []
        position_groups[pos].append(key)

    for pos, player_keys in position_groups.items():
        try:
            pos_num = int(pos.replace('T', '').strip())
        except ValueError:
            for key in player_keys:
                leaderboard[key]['earnings'] = 50000
            continue

        num_tied = len(player_keys)
        total_payout = sum(LIV_PAYOUTS.get(pos_num + i, 50000) for i in range(num_tied))
        per_player = int(total_payout / num_tied)

        for key in player_keys:
            leaderboard[key]['earnings'] = per_player

    return leaderboard


def fetch_datagolf_leaderboard():
    """Fetch leaderboard from DataGolf API"""
    dg_tour = DATAGOLF_TOURS.get(TOUR, 'pga')
    print(f"📡 Fetching DataGolf {TOUR.upper()} leaderboard (tour={dg_tour})...")

    url = f"https://feeds.datagolf.com/preds/in-play?tour={dg_tour}&dead_heat=no&odds_format=percent&file_format=json&key={DATAGOLF_KEY}"
    response = requests.get(url, timeout=15)
    if response.status_code != 200:
        raise Exception(f"DataGolf API error: {response.status_code}")

    data = response.json()
    players = data.get('data', [])
    if not players:
        raise Exception("DataGolf returned no player data")

    tournament_name = data.get('info', {}).get('event_name', 'Unknown Tournament')
    current_round = data.get('current_round', 4)

    print(f"\n🏆 Tournament: {tournament_name}")
    print(f"📊 Round: {current_round}")
    print(f"👥 Players: {len(players)}")

    leaderboard = {}
    for player in players:
        raw_name = player.get('player_name', 'Unknown')
        name_parts = raw_name.split(', ')
        display_name = f"{name_parts[1]} {name_parts[0]}" if len(name_parts) == 2 else raw_name
        dg_id = str(player.get('dg_id', ''))
        position = player.get('current_pos', '-')

        leaderboard[dg_id] = {
            'name': display_name,
            'position': position,
            'earnings': 0
        }

    # Calculate earnings
    if TOUR == 'liv':
        print(f"\n💰 LIV Individual Purse: $20,000,000")
        leaderboard = calculate_liv_earnings(leaderboard)
    else:
        purse = {'pga': 20000000, 'champions': 2500000}.get(TOUR, 20000000)
        print(f"\n💰 Purse: ${purse:,}")
        leaderboard = calculate_tie_adjusted_earnings(leaderboard, purse)

    # Add name-indexed entries AFTER earnings calculation
    name_entries = {}
    for key, data in leaderboard.items():
        name_entries[data['name'].lower()] = data.copy()
    leaderboard.update(name_entries)

    # Show top 5
    print(f"\n🏆 Top finishers:")
    shown = set()
    for key, val in sorted(leaderboard.items(), key=lambda x: x[1].get('earnings', 0), reverse=True):
        name = val['name']
        if name not in shown and val.get('earnings', 0) > 0:
            shown.add(name)
            if len(shown) <= 5:
                print(f"   {val['position']:>4s}  {name:<30s}  ${val['earnings']:>12,}")

    return leaderboard, tournament_name, 20000000 if TOUR == 'liv' else purse


def parse_leaderboard_competitor(comp):
    """Parse a competitor from the LEADERBOARD endpoint.
    This endpoint has status.position.displayName and earnings directly."""
    athlete = comp.get('athlete', {})
    comp_status = comp.get('status', {})

    player_id = str(athlete.get('id', '') or comp.get('id', ''))
    player_name = athlete.get('displayName', '') or athlete.get('fullName', 'Unknown')

    # Position from status.position.displayName (e.g. "T24", "1", "T8")
    position = ''
    pos_obj = comp_status.get('position', {})
    if isinstance(pos_obj, dict):
        position = pos_obj.get('displayName', '')

    if not position:
        # Fallback to sortOrder
        sort_order = comp.get('sortOrder', 999)
        position = str(sort_order)

    # Check for CUT/WD/DQ
    status_type = comp_status.get('type', {}).get('name', '') or ''
    if 'CUT' in status_type.upper():
        position = 'CUT'
    elif 'WD' in status_type.upper() or 'WITHDRAW' in status_type.upper():
        position = 'WD'
    elif 'DQ' in status_type.upper() or 'DISQUAL' in status_type.upper():
        position = 'DQ'

    # Earnings from the competitor object
    earnings = 0
    if comp.get('earnings') and float(comp.get('earnings', 0)) > 0:
        earnings = int(float(comp['earnings']))

    return player_id, player_name, position, earnings


def parse_scoreboard_competitor(comp):
    """Parse a competitor from the SCOREBOARD endpoint.
    This endpoint has order field and score string, but NO status.position object."""
    athlete = comp.get('athlete', {})

    player_id = str(comp.get('id', '') or athlete.get('id', ''))
    player_name = athlete.get('displayName', '') or athlete.get('fullName', 'Unknown')

    # Scoreboard has 'order' for position, NOT status.position
    order = comp.get('order', 999)
    position = str(order)

    # No earnings in scoreboard typically
    earnings = 0

    return player_id, player_name, position, earnings


def fetch_espn_leaderboard(event_id=None):
    """Fetch leaderboard from ESPN - prefer leaderboard endpoint over scoreboard."""
    print(f"📡 Fetching ESPN {TOUR.upper()} leaderboard...")

    # STRATEGY: Try leaderboard endpoint FIRST (has position + earnings)
    # Then fall back to scoreboard only if leaderboard has no data

    leaderboard_url = ESPN_LEADERBOARD_APIS.get(TOUR, ESPN_LEADERBOARD_APIS['pga'])
    scoreboard_url = ESPN_SCOREBOARD_APIS.get(TOUR, ESPN_SCOREBOARD_APIS['pga'])

    data = None
    endpoint_used = None
    is_leaderboard = False

    # Try leaderboard endpoint first
    try:
        print(f"   Trying leaderboard endpoint...")
        response = requests.get(leaderboard_url, timeout=15)
        if response.status_code == 200:
            resp_data = response.json()
            events = resp_data.get('events', [])

            # If event_id specified, find matching event
            if event_id and events:
                matching = [e for e in events if str(e.get('id')) == str(event_id)]
                if matching:
                    # Replace events list with just the matching one
                    resp_data['events'] = matching
                    events = matching
                    print(f"   ✅ Found event {event_id} in leaderboard")
                else:
                    print(f"   ⚠️  Event {event_id} not found in leaderboard (has: {[e.get('id') for e in events]})")
                    events = []

            if events and events[0].get('competitions', [{}])[0].get('competitors'):
                data = resp_data
                endpoint_used = 'leaderboard'
                is_leaderboard = True
                print(f"   ✅ Got data from leaderboard endpoint")
    except Exception as e:
        print(f"   ⚠️  Leaderboard failed: {e}")

    # Fall back to scoreboard
    if not data:
        try:
            print(f"   Trying scoreboard endpoint...")
            sb_url = scoreboard_url
            if event_id:
                sb_url += f"?event={event_id}"
            response = requests.get(sb_url, timeout=15)
            if response.status_code == 200:
                resp_data = response.json()
                events = resp_data.get('events', [])
                if events:
                    data = resp_data
                    endpoint_used = 'scoreboard'
                    is_leaderboard = False
                    print(f"   ✅ Got data from scoreboard endpoint")
                    print(f"   ⚠️  WARNING: Scoreboard has limited position/earnings data")
        except Exception as e:
            print(f"   ⚠️  Scoreboard failed: {e}")

    if not data or not data.get('events'):
        raise Exception(f"Could not fetch data from ESPN {TOUR.upper()} API")

    events = data['events']
    if len(events) > 1:
        print(f"\n📋 Found {len(events)} events:")
        for i, evt in enumerate(events):
            comp = evt.get('competitions', [{}])[0]
            status = comp.get('status', {}).get('type', {}).get('name', 'Unknown')
            print(f"   [{i}] {evt.get('name', '?')} - {status} (ID: {evt.get('id', '?')})")

    event = events[0]
    competition = event.get('competitions', [{}])[0]
    competitors = competition.get('competitors', [])

    tournament_name = event.get('name', 'Unknown Tournament')

    # Get purse
    purse = event.get('purse', 0) or competition.get('purse', 0)
    if not purse:
        purse = {'pga': 9200000, 'liv': 20000000, 'champions': 2200000}.get(TOUR, 9200000)

    status = competition.get('status', {}).get('type', {}).get('name', 'Unknown')

    print(f"\n🏆 Tournament: {tournament_name}")
    print(f"💰 Purse: ${purse:,}")
    print(f"📊 Status: {status}")
    print(f"👥 Competitors: {len(competitors)}")
    print(f"📡 Endpoint: {endpoint_used}")

    if DEBUG and competitors:
        print("\n🔍 DEBUG - First competitor structure:")
        comp_debug = {k: v for k, v in competitors[0].items() if k != 'linescores'}
        print(json.dumps(comp_debug, indent=2, default=str)[:3000])

    leaderboard = {}
    earnings_found = 0

    for idx, comp in enumerate(competitors):
        if is_leaderboard:
            player_id, player_name, position, earnings = parse_leaderboard_competitor(comp)
        else:
            player_id, player_name, position, earnings = parse_scoreboard_competitor(comp)

        if earnings > 0:
            earnings_found += 1

        if DEBUG and idx < 10:
            print(f"🔍 {player_name}: pos={position}, earnings=${earnings:,}")

        leaderboard[player_id] = {
            'name': player_name,
            'position': position,
            'earnings': earnings
        }

    print(f"💵 Players with ESPN earnings data: {earnings_found}")

    # ALWAYS calculate local tie-adjusted earnings from purse
    # Then use ESPN earnings only where they exist (ESPN is often incomplete)
    # Save ESPN earnings first
    espn_earnings = {}
    for pid, pdata in leaderboard.items():
        if pdata.get('earnings', 0) > 0:
            espn_earnings[pid] = pdata['earnings']

    # Calculate local earnings for ALL players
    if TOUR == 'liv':
        print(f"\n📊 Calculating LIV earnings from payout table...")
        leaderboard = calculate_liv_earnings(leaderboard)
    else:
        print(f"\n📊 Calculating tie-adjusted earnings from ${purse:,} purse...")
        leaderboard = calculate_tie_adjusted_earnings(leaderboard, purse)

    # Override with ESPN earnings where available (ESPN is authoritative when present)
    if earnings_found > 0:
        espn_used = 0
        for pid, espn_earn in espn_earnings.items():
            if pid in leaderboard and espn_earn > 0:
                leaderboard[pid]['earnings'] = espn_earn
                espn_used += 1
        print(f"   Used {espn_used} ESPN earnings, {len(leaderboard) - espn_used} calculated locally")

    # Also index by name for matching
    name_entries = {}
    for player_id, pdata in leaderboard.items():
        name_entries[pdata['name'].lower()] = pdata.copy()
    leaderboard.update(name_entries)

    return leaderboard, tournament_name, purse


def load_manual_results(filepath):
    """Load results from a manual JSON or CSV file."""
    print(f"\n📂 Loading manual results from: {filepath}")

    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")

    leaderboard = {}
    tournament_name = "Manual Results"

    if filepath.endswith('.json'):
        with open(filepath, 'r') as f:
            data = json.load(f)
        tournament_name = data.get('tournament_name', 'Manual Results')
        for p in data.get('players', []):
            name = p.get('name', p.get('player_name', ''))
            position = str(p.get('position', p.get('pos', '')))
            earnings = int(p.get('earnings', p.get('money', p.get('prize', 0))))
            if name:
                leaderboard[name.lower()] = {'name': name, 'position': position, 'earnings': earnings}

    elif filepath.endswith('.csv'):
        with open(filepath, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = row.get('name', row.get('player_name', row.get('player', '')))
                position = row.get('position', row.get('pos', row.get('finish', '')))
                earnings_str = row.get('earnings', row.get('money', row.get('prize', '0')))
                earnings = int(float(earnings_str.replace('$', '').replace(',', '').strip() or '0'))
                if name:
                    leaderboard[name.lower()] = {'name': name, 'position': str(position), 'earnings': earnings}
    else:
        raise ValueError(f"Unsupported file format: {filepath}. Use .json or .csv")

    print(f"   Loaded {len(leaderboard)} players")
    sorted_players = sorted(leaderboard.values(), key=lambda x: x['earnings'], reverse=True)
    for p in sorted_players[:5]:
        print(f"   {p['position']:>4} {p['name']:<25} ${p['earnings']:>12,}")

    return leaderboard, tournament_name, 0


def list_espn_events():
    """List available events from ESPN for the current tour."""
    print(f"\n📋 Fetching available ESPN {TOUR.upper()} events...")

    for label, url in [('leaderboard', ESPN_LEADERBOARD_APIS.get(TOUR)), ('scoreboard', ESPN_SCOREBOARD_APIS.get(TOUR))]:
        try:
            response = requests.get(url, timeout=15)
            if response.status_code == 200:
                data = response.json()
                events = data.get('events', [])
                if events:
                    print(f"\n   Found {len(events)} event(s) from {label}:")
                    for evt in events:
                        comp = evt.get('competitions', [{}])[0]
                        status = comp.get('status', {}).get('type', {}).get('name', 'Unknown')
                        competitors = comp.get('competitors', [])
                        purse = evt.get('purse', 0)
                        print(f"\n   🏆 {evt.get('name', '?')}")
                        print(f"      ESPN Event ID: {evt.get('id', '?')}")
                        print(f"      Status: {status}")
                        print(f"      Players: {len(competitors)}")
                        if purse:
                            print(f"      Purse: ${purse:,}")
                    print(f"\n💡 Use --event-id <id> to select a specific event")
                    return
        except Exception as e:
            print(f"   ⚠️  {label} failed: {e}")

    print("   ❌ No events found")


def get_picks(tournament_id):
    """Get all picks for a tournament from Supabase."""
    print(f"\n📋 Fetching picks for tournament: {tournament_id}")
    url = f"{SUPABASE_URL}/rest/v1/picks"
    headers = {
        'apikey': SUPABASE_KEY,
        'Authorization': f'Bearer {SUPABASE_KEY}',
        'Content-Type': 'application/json'
    }
    params = {'tournament_id': f'eq.{tournament_id}', 'select': '*'}
    response = requests.get(url, headers=headers, params=params)
    if response.status_code != 200:
        raise Exception(f"Supabase error: {response.status_code} - {response.text}")
    picks = response.json()
    print(f"   Found {len(picks)} picks")
    return picks


def update_pick(pick_id, position, earnings):
    """Update a pick with final results."""
    url = f"{SUPABASE_URL}/rest/v1/picks"
    headers = {
        'apikey': SUPABASE_KEY,
        'Authorization': f'Bearer {SUPABASE_KEY}',
        'Content-Type': 'application/json',
        'Prefer': 'return=minimal'
    }
    params = {'id': f'eq.{pick_id}'}
    data = {'finish_position': position, 'final_earnings': earnings, 'earnings': earnings}
    response = requests.patch(url, headers=headers, params=params, json=data)
    return response.status_code == 204


def match_player(player_name, player_id, leaderboard):
    """Try to match a player against the leaderboard using multiple strategies."""
    # Strategy 1: Match by player ID
    result = leaderboard.get(player_id)
    if result:
        return result, "ID"

    # Strategy 2: Exact name match (case insensitive)
    player_lower = player_name.lower()
    result = leaderboard.get(player_lower)
    if result:
        return result, "name"

    # Strategy 3: Partial name / last name match
    for key, val in leaderboard.items():
        if not isinstance(key, str) or not any(c.islower() for c in key):
            continue

        if player_lower in key or key in player_lower:
            return val, "partial"

        pick_parts = player_lower.split()
        key_parts = key.split()
        if pick_parts and key_parts:
            pick_last = pick_parts[-1]
            key_last = key_parts[-1]
            if len(pick_last) > 2 and pick_last == key_last:
                if len(pick_parts) > 1 and len(key_parts) > 1:
                    if pick_parts[0][0] == key_parts[0][0]:
                        return val, "lastname+initial"
                else:
                    return val, "lastname"

    # Strategy 4: Normalized (strip accents)
    import unicodedata
    def normalize(s):
        return ''.join(c for c in unicodedata.normalize('NFD', s.lower()) if unicodedata.category(c) != 'Mn')

    player_normalized = normalize(player_name)
    for key, val in leaderboard.items():
        if not isinstance(key, str) or not any(c.islower() for c in key):
            continue
        if normalize(key) == player_normalized:
            return val, "normalized"

    return None, None


def finalize_tournament(tournament_id, event_id=None, manual_file=None):
    """Main function to finalize a tournament."""
    print("=" * 60)
    print(f"🏌️ Tournament Finalization ({TOUR.upper()})")
    print("=" * 60)

    if manual_file:
        leaderboard, tournament_name, purse = load_manual_results(manual_file)
    elif USE_DATAGOLF:
        leaderboard, tournament_name, purse = fetch_datagolf_leaderboard()
    else:
        leaderboard, tournament_name, purse = fetch_espn_leaderboard(event_id)

    if DEBUG:
        print("\n🔍 DEBUG - Sample leaderboard entries:")
        shown = 0
        for key, val in leaderboard.items():
            if isinstance(key, str) and any(c.islower() for c in key) and shown < 20:
                print(f"   [{key}] {val['name']}: {val['position']} - ${val['earnings']:,}")
                shown += 1

    picks = get_picks(tournament_id)

    if not picks:
        print("\n⚠️  No picks found for this tournament!")
        print(f"   Tournament ID used: {tournament_id}")
        try:
            url = f"{SUPABASE_URL}/rest/v1/picks"
            headers = {'apikey': SUPABASE_KEY, 'Authorization': f'Bearer {SUPABASE_KEY}'}
            resp = requests.get(url, headers=headers, params={'select': 'tournament_id'})
            if resp.status_code == 200:
                all_picks = resp.json()
                tournament_ids = list(set(p['tournament_id'] for p in all_picks))
                if tournament_ids:
                    print(f"\n   Available tournament IDs with picks:")
                    for tid in sorted(tournament_ids):
                        count = sum(1 for p in all_picks if p['tournament_id'] == tid)
                        print(f"      • {tid} ({count} picks)")
        except:
            pass
        return

    print(f"\n🔄 Updating picks...")
    print("-" * 60)

    updated = 0
    not_found = 0

    for pick in picks:
        player_id = str(pick.get('player_id', ''))
        player_name = pick.get('player_name', 'Unknown')

        result, match_type = match_player(player_name, player_id, leaderboard)

        if result:
            position = result['position']
            earnings = result['earnings']

            if update_pick(pick['id'], position, earnings):
                updated += 1
                match_info = f" (matched by {match_type})" if DEBUG else ""
                print(f"   ✅ {player_name}: {position} - ${earnings:,}{match_info}")
            else:
                print(f"   ❌ Failed to update: {player_name}")
        else:
            not_found += 1
            if TOUR == 'liv':
                update_pick(pick['id'], 'WD', 0)
                print(f"   ⚠️  {player_name}: Not found (set to WD)")
            else:
                update_pick(pick['id'], 'MC', 0)
                print(f"   ⚠️  {player_name}: Not found (set to MC)")

    print("-" * 60)
    print(f"\n✅ Finalization Complete!")
    print(f"   Tournament: {tournament_name}")
    print(f"   Tour: {TOUR.upper()}")
    print(f"   Picks updated: {updated}")
    print(f"   Not found: {not_found}")
    print(f"   Total: {len(picks)}")


def main():
    global DEBUG, TOUR, USE_DATAGOLF

    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    flags = [a for a in sys.argv[1:] if a.startswith('--')]

    if '--debug' in flags: DEBUG = True
    if '--liv' in flags: TOUR = 'liv'
    if '--champions' in flags: TOUR = 'champions'
    if '--datagolf' in flags: USE_DATAGOLF = True

    if '--template' in flags:
        template = {"tournament_name": "LIV Golf Example", "players": [
            {"name": "Jon Rahm", "position": "1", "earnings": 4000000},
            {"name": "Bryson DeChambeau", "position": "2", "earnings": 2250000},
        ]}
        with open("results_template.json", 'w') as f:
            json.dump(template, f, indent=2)
        print("📝 Template saved to results_template.json")
        return

    if len(args) < 1 and '--list-events' not in flags:
        print("Usage: python finalize_tournament.py <tournament_id> [options]")
        print("\nOptions:")
        print("  --liv              LIV Golf")
        print("  --champions        Champions Tour")
        print("  --datagolf         Use DataGolf API instead of ESPN")
        print("  --debug            Show debug info")
        print("  --list-events      Show available ESPN events")
        print("  --event-id <id>    Use specific ESPN event ID")
        print("  --manual <file>    Use manual results JSON/CSV")
        print("  --template         Generate results template")
        print("\nExamples:")
        print("  python finalize_tournament.py farmers-2026")
        print("  python finalize_tournament.py liv-hongkong-2026 --liv")
        print("  python finalize_tournament.py liv-hongkong-2026 --liv --event-id 401824806")
        print("  python finalize_tournament.py hardie-champ-2026 --champions")
        print("  python finalize_tournament.py hardie-champ-2026 --champions --manual results.csv")
        sys.exit(1)

    if '--list-events' in flags:
        list_espn_events()
        return

    tournament_id = args[0] if args else None

    event_id = None
    if '--event-id' in flags:
        idx = sys.argv.index('--event-id')
        if idx + 1 < len(sys.argv):
            event_id = sys.argv[idx + 1]
        else:
            print("❌ --event-id requires an argument")
            sys.exit(1)

    manual_file = None
    if '--manual' in flags:
        idx = sys.argv.index('--manual')
        if idx + 1 < len(sys.argv):
            manual_file = sys.argv[idx + 1]
        else:
            print("❌ --manual requires a file path")
            sys.exit(1)

    try:
        finalize_tournament(tournament_id, event_id, manual_file)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        if DEBUG:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()