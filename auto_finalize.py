#!/usr/bin/env python3
"""
Auto-Finalize: Automatically detects and finalizes tournaments that ended yesterday.
Designed to run every Monday morning via GitHub Actions or Task Scheduler.

Covers PGA Tour, LIV Golf, and PGA Tour Champions.

Usage:
    python auto_finalize.py              # Auto-detect and finalize yesterday's tournaments
    python auto_finalize.py --dry-run    # Show what would be finalized without doing it
    python auto_finalize.py --date 2026-04-05  # Pretend today is this date (for testing)
"""

import sys
import os
import json
import requests
from datetime import datetime, timedelta

# Import finalize functions from finalize_tournament.py
# (must be in same directory)
import finalize_tournament as ft

# ==================== SCHEDULES ====================
# These must match the schedule in index_source.html

PGA_2026_SCHEDULE = [
    {"id": "sentry-2026", "name": "The Sentry", "endDate": "2026-01-05"},
    {"id": "sony-2026", "name": "Sony Open in Hawaii", "endDate": "2026-01-12"},
    {"id": "amex-2026", "name": "The American Express", "endDate": "2026-01-25"},
    {"id": "farmers-2026", "name": "Farmers Insurance Open", "endDate": "2026-02-01"},
    {"id": "phoenix-2026", "name": "WM Phoenix Open", "endDate": "2026-02-08"},
    {"id": "pebble-2026", "name": "AT&T Pebble Beach Pro-Am", "endDate": "2026-02-15"},
    {"id": "genesis-2026", "name": "The Genesis Invitational", "endDate": "2026-02-22"},
    {"id": "cognizant-2026", "name": "Cognizant Classic", "endDate": "2026-03-01"},
    {"id": "arnold-palmer-2026", "name": "Arnold Palmer Invitational", "endDate": "2026-03-08"},
    {"id": "players-2026", "name": "THE PLAYERS Championship", "endDate": "2026-03-15"},
    {"id": "valspar-2026", "name": "Valspar Championship", "endDate": "2026-03-22"},
    {"id": "houston-2026", "name": "Texas Children's Houston Open", "endDate": "2026-03-29"},
    {"id": "valero-2026", "name": "Valero Texas Open", "endDate": "2026-04-05"},
    {"id": "masters-2026", "name": "Masters Tournament", "endDate": "2026-04-12"},
    {"id": "rbc-heritage-2026", "name": "RBC Heritage", "endDate": "2026-04-19"},
    {"id": "zurich-2026", "name": "Zurich Classic of New Orleans", "endDate": "2026-04-26", "team": True},
    {"id": "cadillac-2026", "name": "Cadillac Championship", "endDate": "2026-05-03"},
    {"id": "truist-2026", "name": "Truist Championship", "endDate": "2026-05-10"},
    {"id": "pga-championship-2026", "name": "PGA Championship", "endDate": "2026-05-17"},
    {"id": "byron-nelson-2026", "name": "THE CJ CUP Byron Nelson", "endDate": "2026-05-24"},
    {"id": "charles-schwab-2026", "name": "Charles Schwab Challenge", "endDate": "2026-05-31"},
    {"id": "memorial-2026", "name": "the Memorial Tournament", "endDate": "2026-06-07"},
    {"id": "canadian-open-2026", "name": "RBC Canadian Open", "endDate": "2026-06-14"},
    {"id": "us-open-2026", "name": "U.S. Open", "endDate": "2026-06-21"},
    {"id": "travelers-2026", "name": "Travelers Championship", "endDate": "2026-06-28"},
    {"id": "john-deere-2026", "name": "John Deere Classic", "endDate": "2026-07-05"},
    {"id": "scottish-open-2026", "name": "Genesis Scottish Open", "endDate": "2026-07-12"},
    {"id": "open-championship-2026", "name": "The Open Championship", "endDate": "2026-07-19"},
    {"id": "3m-open-2026", "name": "3M Open", "endDate": "2026-07-26"},
    {"id": "rocket-classic-2026", "name": "Rocket Classic", "endDate": "2026-08-02"},
    {"id": "wyndham-2026", "name": "Wyndham Championship", "endDate": "2026-08-09"},
    {"id": "fedex-st-jude-2026", "name": "FedEx St. Jude Championship", "endDate": "2026-08-16"},
    {"id": "bmw-2026", "name": "BMW Championship", "endDate": "2026-08-23"},
]

LIV_2026_SCHEDULE = [
    {"id": "liv-riyadh-2026", "name": "LIV Golf Riyadh", "endDate": "2026-02-07"},
    {"id": "liv-adelaide-2026", "name": "LIV Golf Adelaide", "endDate": "2026-02-15"},
    {"id": "liv-hongkong-2026", "name": "LIV Golf Hong Kong", "endDate": "2026-03-08"},
    {"id": "liv-singapore-2026", "name": "LIV Golf Singapore", "endDate": "2026-03-15"},
    {"id": "liv-southafrica-2026", "name": "LIV Golf South Africa", "endDate": "2026-03-22"},
    {"id": "liv-mexico-2026", "name": "LIV Golf Mexico City", "endDate": "2026-04-19"},
    {"id": "liv-virginia-2026", "name": "LIV Golf Virginia", "endDate": "2026-05-10"},
    {"id": "liv-andalucia-2026", "name": "LIV Golf Andalucía", "endDate": "2026-06-07"},
    {"id": "liv-louisiana-2026", "name": "LIV Golf Louisiana", "endDate": "2026-06-28"},
    {"id": "liv-uk-2026", "name": "LIV Golf United Kingdom", "endDate": "2026-07-26"},
    {"id": "liv-newyork-2026", "name": "LIV Golf New York", "endDate": "2026-08-09"},
    {"id": "liv-indianapolis-2026", "name": "LIV Golf Indianapolis", "endDate": "2026-08-23"},
]

CHAMPIONS_2026_SCHEDULE = [
    {"id": "chubb-champ-2026", "name": "Chubb Classic", "endDate": "2026-02-15"},
    {"id": "hardie-champ-2026", "name": "James Hardie Pro Football HOF Invitational", "endDate": "2026-03-08"},
    {"id": "cologuard-champ-2026", "name": "Cologuard Classic", "endDate": "2026-03-22"},
    {"id": "hoag-champ-2026", "name": "Hoag Classic", "endDate": "2026-03-29"},
    {"id": "senior-pga-2026", "name": "Senior PGA Championship", "endDate": "2026-04-19"},
    {"id": "mitsubishi-classic-2026", "name": "Mitsubishi Electric Classic", "endDate": "2026-04-26"},
    {"id": "regions-tradition-2026", "name": "Regions Tradition", "endDate": "2026-05-03"},
    {"id": "insperity-2026", "name": "Insperity Invitational", "endDate": "2026-05-10"},
    {"id": "trophy-hassan-2026", "name": "Trophy Hassan II", "endDate": "2026-05-23"},
    {"id": "american-family-2026", "name": "American Family Insurance Championship", "endDate": "2026-06-07"},
    {"id": "principal-charity-2026", "name": "Principal Charity Classic", "endDate": "2026-06-14"},
    {"id": "dicks-open-2026", "name": "DICK'S Open", "endDate": "2026-06-28"},
    {"id": "us-senior-open-2026", "name": "U.S. Senior Open Championship", "endDate": "2026-07-05"},
    {"id": "kaulig-2026", "name": "Kaulig Companies Championship", "endDate": "2026-07-12"},
    {"id": "senior-open-2026", "name": "ISPS HANDA Senior Open", "endDate": "2026-07-26"},
    {"id": "portugal-2026", "name": "Portugal Invitational", "endDate": "2026-08-02"},
    {"id": "boeing-2026", "name": "Boeing Classic", "endDate": "2026-08-16"},
    {"id": "rogers-charity-2026", "name": "Rogers Charity Classic", "endDate": "2026-08-23"},
    {"id": "ally-challenge-2026", "name": "The Ally Challenge", "endDate": "2026-08-30"},
    {"id": "sanford-2026", "name": "Sanford International", "endDate": "2026-09-13"},
    {"id": "pure-insurance-2026", "name": "PURE Insurance Championship", "endDate": "2026-09-20"},
    {"id": "lehigh-valley-2026", "name": "Jefferson Lehigh Valley Classic", "endDate": "2026-10-04"},
    {"id": "furyk-2026", "name": "Constellation FURYK & FRIENDS", "endDate": "2026-10-11"},
    {"id": "sas-2026", "name": "SAS Championship", "endDate": "2026-10-18"},
    {"id": "stifel-charity-2026", "name": "Stifel Charity Classic", "endDate": "2026-10-25"},
    {"id": "simmons-bank-2026", "name": "Simmons Bank Championship", "endDate": "2026-11-01"},
    {"id": "schwab-cup-2026", "name": "Charles Schwab Cup Championship", "endDate": "2026-11-15"},
]


def find_tournaments_ending_on(target_date):
    """Find all tournaments that ended on the target date (Sunday before Monday run)."""
    target = target_date.strftime('%Y-%m-%d')
    found = []

    for t in PGA_2026_SCHEDULE:
        if t['endDate'] == target:
            found.append({**t, 'tour': 'pga'})

    for t in LIV_2026_SCHEDULE:
        if t['endDate'] == target:
            found.append({**t, 'tour': 'liv'})

    for t in CHAMPIONS_2026_SCHEDULE:
        if t['endDate'] == target:
            found.append({**t, 'tour': 'champions'})

    return found


def check_picks_exist(tournament_id):
    """Check if any picks exist for this tournament in Supabase."""
    url = f"{ft.SUPABASE_URL}/rest/v1/picks"
    headers = {
        'apikey': ft.SUPABASE_KEY,
        'Authorization': f'Bearer {ft.SUPABASE_KEY}',
    }
    params = {
        'tournament_id': f'eq.{tournament_id}',
        'select': 'id',
        'limit': '1'
    }
    try:
        resp = requests.get(url, headers=headers, params=params)
        if resp.status_code == 200:
            return len(resp.json()) > 0
    except:
        pass
    return False


def send_notification(message, is_error=False):
    """Optional: Send notification via email/webhook. Customize as needed."""
    print(f"{'❌' if is_error else '✅'} {message}")
    # You could add Resend email notification here if desired


def main():
    dry_run = '--dry-run' in sys.argv
    
    # Determine "today" (can override for testing)
    today = datetime.utcnow().date()
    if '--date' in sys.argv:
        idx = sys.argv.index('--date')
        if idx + 1 < len(sys.argv):
            today = datetime.strptime(sys.argv[idx + 1], '%Y-%m-%d').date()
    
    # Look for tournaments that ended yesterday (Sunday) or Saturday
    # Run on Monday, so yesterday = Sunday = tournament end day
    # Also check Saturday in case of weather delays pushing to Monday
    yesterday = today - timedelta(days=1)
    two_days_ago = today - timedelta(days=2)
    
    print("=" * 60)
    print(f"🏌️ Auto-Finalize - {today.strftime('%A %B %d, %Y')}")
    print("=" * 60)
    print(f"   Checking for tournaments ending: {yesterday} or {two_days_ago}")
    
    tournaments = find_tournaments_ending_on(yesterday)
    if not tournaments:
        tournaments = find_tournaments_ending_on(two_days_ago)
        if tournaments:
            print(f"   (Found tournament ending {two_days_ago} - possible weather delay)")
    
    if not tournaments:
        print(f"\n📅 No tournaments ended recently. Nothing to finalize.")
        print(f"   Next PGA tournament ends: ", end="")
        for t in PGA_2026_SCHEDULE:
            if t['endDate'] >= today.strftime('%Y-%m-%d'):
                print(f"{t['name']} ({t['endDate']})")
                break
        return
    
    print(f"\n📋 Found {len(tournaments)} tournament(s) to finalize:")
    for t in tournaments:
        has_picks = check_picks_exist(t['id'])
        print(f"   {'✅' if has_picks else '⚠️'} {t['name']} ({t['tour'].upper()}) - {t['id']} {'[has picks]' if has_picks else '[NO PICKS - skipping]'}")
    
    if dry_run:
        print(f"\n🔍 DRY RUN - would finalize the above. Run without --dry-run to execute.")
        return
    
    # Finalize each tournament
    results = []
    for t in tournaments:
        # Skip if no picks exist
        if not check_picks_exist(t['id']):
            print(f"\n⏭️  Skipping {t['name']} - no picks found")
            continue
        
        # Skip team events (need manual handling for now)
        if t.get('team'):
            print(f"\n⚠️  {t['name']} is a TEAM EVENT - skipping auto-finalize")
            print(f"   Run manually: python finalize_tournament.py {t['id']}")
            send_notification(f"Team event {t['name']} needs manual finalization", is_error=True)
            continue
        
        print(f"\n{'='*60}")
        print(f"Finalizing: {t['name']} ({t['tour'].upper()})")
        print(f"{'='*60}")
        
        # Set the tour for finalize_tournament
        ft.TOUR = t['tour']
        ft.DEBUG = False
        ft.USE_DATAGOLF = False
        
        # Champions Tour: ESPN often has $0 earnings, but let's try ESPN first
        # If it fails or has no earnings, we'd need --manual
        # For now, always try ESPN
        
        try:
            ft.finalize_tournament(t['id'])
            results.append({'tournament': t['name'], 'tour': t['tour'], 'status': 'success'})
        except Exception as e:
            error_msg = f"Failed to finalize {t['name']}: {e}"
            print(f"\n❌ {error_msg}")
            results.append({'tournament': t['name'], 'tour': t['tour'], 'status': 'error', 'error': str(e)})
            send_notification(error_msg, is_error=True)
    
    # Summary
    print(f"\n{'='*60}")
    print(f"📊 Auto-Finalize Summary")
    print(f"{'='*60}")
    for r in results:
        status = '✅' if r['status'] == 'success' else '❌'
        print(f"   {status} {r['tournament']} ({r['tour'].upper()})")
        if r.get('error'):
            print(f"      Error: {r['error']}")
    
    # Log to file for audit trail
    log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'finalize_log.json')
    try:
        existing_log = []
        if os.path.exists(log_file):
            with open(log_file, 'r') as f:
                existing_log = json.load(f)
        existing_log.append({
            'date': today.isoformat(),
            'tournaments': results
        })
        # Keep last 52 weeks
        existing_log = existing_log[-52:]
        with open(log_file, 'w') as f:
            json.dump(existing_log, f, indent=2)
    except:
        pass


if __name__ == '__main__':
    main()
