#!/usr/bin/env python3
"""
PGA Tour Field Scraper
Automatically finds the upcoming tournament from pgatour.com/schedule
and scrapes the field with headshots and OWGR rankings.

Usage:
    python scrape_field.py              # Auto-detect upcoming tournament
    python scrape_field.py <url>        # Scrape specific tournament
    python scrape_field.py --list       # List upcoming tournaments

Requirements:
    pip install selenium webdriver-manager supabase
"""

import sys
import os
import json
import time
import re
from datetime import datetime, timedelta

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# Supabase credentials
SUPABASE_URL = os.getenv('SUPABASE_URL', 'https://ttwtifdhlaijdswhehve.supabase.co')
SUPABASE_KEY = os.getenv('SUPABASE_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InR0d3RpZmRobGFpamRzd2hlaHZlIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njc0OTc5MTYsImV4cCI6MjA4MzA3MzkxNn0.h4YVDwZ4_TLmbjHnFSbUKPUpqBsY2Lh4WQIqUwZ3faE')

def setup_driver(headless=True):
    """Setup Chrome driver"""
    chrome_options = Options()
    if headless:
        chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver

def parse_tournament_dates(date_text):
    """Parse tournament date text like 'FEB 5 - 8' or 'JAN 29 - FEB 1' into start date"""
    try:
        # Current year
        year = datetime.now().year
        
        # Clean up text
        date_text = date_text.strip().upper()
        
        # Pattern: "FEB 5 - 8" or "JAN 29 - FEB 1"
        # Extract the start date (first month + day)
        match = re.match(r'([A-Z]{3})\s+(\d+)', date_text)
        if match:
            month_str = match.group(1)
            day = int(match.group(2))
            
            months = {'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6,
                     'JUL': 7, 'AUG': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12}
            
            month = months.get(month_str, 1)
            return datetime(year, month, day)
    except:
        pass
    return None

def get_upcoming_tournaments(driver, list_all=False):
    """Get upcoming tournaments from PGA Tour schedule page"""
    print("📅 Finding upcoming tournaments from schedule...")
    
    driver.get("https://www.pgatour.com/schedule")
    time.sleep(4)
    
    # Get today's date
    today = datetime.now()
    
    tournaments = []
    
    # Find all tournament cards/sections
    # The schedule page has tournament entries with dates and links
    page_source = driver.page_source
    
    # Look for tournament links with their surrounding context
    tournament_links = driver.find_elements(By.XPATH, "//a[contains(@href, '/tournaments/2026/') or contains(@href, '/tournaments/2025/')]")
    
    seen_urls = set()
    
    for link in tournament_links:
        try:
            href = link.get_attribute('href')
            
            # Skip duplicates and non-main tournament links
            if href in seen_urls:
                continue
            if '/field' in href or '/past-results' in href or '/leaderboard' in href:
                continue
            
            # Extract tournament info from URL
            match = re.search(r'/tournaments/(\d+)/([^/]+)/(R\d+)', href)
            if not match:
                continue
            
            year = match.group(1)
            slug = match.group(2)
            tournament_id = match.group(3)
            
            seen_urls.add(href)
            
            # Try to get the tournament name and dates from surrounding elements
            name = ''
            dates = ''
            start_date = None
            
            # Go up to find parent container with all info
            try:
                parent = link
                for _ in range(10):
                    parent = parent.find_element(By.XPATH, "./..")
                    parent_text = parent.text
                    
                    # Look for date pattern (e.g., "FEB 5 - 8" or "JAN 29 - FEB 1")
                    date_match = re.search(r'([A-Z]{3}\s+\d+\s*-\s*(?:[A-Z]{3}\s+)?\d+)', parent_text.upper())
                    if date_match:
                        dates = date_match.group(1)
                        start_date = parse_tournament_dates(dates)
                    
                    # Look for tournament name (usually a longer text line)
                    lines = parent_text.split('\n')
                    for line in lines:
                        line = line.strip()
                        # Tournament names are usually longer and contain specific words
                        if len(line) > 10 and any(word in line.lower() for word in ['open', 'championship', 'classic', 'invitational', 'memorial', 'masters', 'players', 'pga']):
                            if not any(skip in line.lower() for skip in ['past results', 'how to watch', 'tickets']):
                                name = line
                                break
                    
                    if dates and name:
                        break
            except:
                pass
            
            # Use slug as fallback name
            if not name:
                name = slug.replace('-', ' ').title()
            
            tournaments.append({
                'name': name,
                'url': href,
                'slug': slug,
                'tournament_id': tournament_id,
                'year': year,
                'dates': dates,
                'start_date': start_date
            })
            
        except Exception as e:
            continue
    
    # Sort by start date
    tournaments.sort(key=lambda t: t['start_date'] or datetime.max)
    
    # Filter to upcoming tournaments (start date >= today - 7 days to catch current week)
    upcoming = []
    cutoff = today - timedelta(days=7)
    
    for t in tournaments:
        if t['start_date'] and t['start_date'] >= cutoff:
            upcoming.append(t)
    
    if list_all:
        print(f"\n📋 Found {len(upcoming)} upcoming tournaments:")
        for i, t in enumerate(upcoming[:10]):
            status = "THIS WEEK" if t['start_date'] and t['start_date'] <= today + timedelta(days=3) else ""
            print(f"   {i+1}. {t['name']}")
            print(f"      Dates: {t['dates']}")
            print(f"      URL: {t['url']}")
            print(f"      ID: {t['tournament_id']} {status}")
            print()
    
    return upcoming

def get_upcoming_tournament(driver):
    """Get the next upcoming tournament (this week or next)"""
    upcoming = get_upcoming_tournaments(driver)
    
    if not upcoming:
        return None
    
    today = datetime.now()
    
    # Find tournament that starts this week or next
    for t in upcoming:
        if t['start_date']:
            # Tournament starting within next 7 days
            days_until = (t['start_date'] - today).days
            if days_until >= -3 and days_until <= 7:  # Allow for tournaments that just started
                print(f"✅ Found: {t['name']}")
                print(f"   Dates: {t['dates']}")
                print(f"   URL: {t['url']}")
                print(f"   ID: {t['tournament_id']}")
                return t
    
    # Fallback to first upcoming
    if upcoming:
        t = upcoming[0]
        print(f"✅ Found (next upcoming): {t['name']}")
        print(f"   Dates: {t['dates']}")
        print(f"   URL: {t['url']}")
        print(f"   ID: {t['tournament_id']}")
        return t
    
    return None

def scrape_field(driver, tournament_url):
    """Scrape tournament field from PGA Tour website"""
    # Make sure we're on the field page
    field_url = tournament_url.rstrip('/')
    if not field_url.endswith('/field'):
        field_url += '/field'
    
    print(f"🏌️ Scraping field from: {field_url}")
    driver.get(field_url)
    
    # Wait for page to load
    print("⏳ Waiting for page to load...")
    time.sleep(5)
    
    # Scroll to load all players
    print("📜 Scrolling to load all players...")
    last_height = driver.execute_script("return document.body.scrollHeight")
    for _ in range(15):  # More scrolls
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1.5)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height
    
    # Scroll back to top to ensure all content is rendered
    driver.execute_script("window.scrollTo(0, 0);")
    time.sleep(3)
    
    players = []
    seen_ids = set()
    
    # Method 1: Try to find player rows with all data (name, country, OWGR)
    print("🔍 Looking for player data...")
    
    # PGA Tour field page typically has rows with: Rank | Flag | Name | Country
    # Try to find table rows or card elements
    
    # First, try finding player links
    player_links = driver.find_elements(By.XPATH, "//a[contains(@href, '/player/')]")
    print(f"   Found {len(player_links)} player links")
    
    for link in player_links:
        try:
            href = link.get_attribute('href')
            match = re.search(r'/player/(\d+)/([^/\?]+)', href)
            if not match:
                continue
                
            player_id = match.group(1)
            if player_id in seen_ids:
                continue
            seen_ids.add(player_id)
            
            # Get player name from link text
            name = link.text.strip()
            if not name:
                name = match.group(2).replace('-', ' ').title()
            
            # Try to find OWGR and country by looking at parent/sibling elements
            owgr = None
            country = ''
            
            try:
                # Go up to find the row container and get all text
                parent = link
                for _ in range(8):  # Go up more levels
                    parent = parent.find_element(By.XPATH, "./..")
                    parent_text = parent.text
                    
                    # The row format is: [Name] [Country] | [RANK like T27, 3, -] | [OWGR number] | [How Qualified]
                    lines = parent_text.split('\n')
                    
                    # Collect all pure numbers and T-prefixed values
                    pure_numbers = []
                    rank_values = []
                    
                    for line in lines:
                        line = line.strip()
                        if re.match(r'^T\d+$', line):
                            rank_values.append(line)
                        elif line.isdigit():
                            num = int(line)
                            pure_numbers.append(num)
                        elif line == '-':
                            rank_values.append('-')
                    
                    if rank_values and pure_numbers:
                        for num in reversed(pure_numbers):
                            if num <= 999:
                                owgr = num
                                break
                        if owgr:
                            break
                    elif len(pure_numbers) >= 2:
                        owgr = pure_numbers[1] if pure_numbers[1] <= 999 else None
                        if owgr:
                            break
                    elif len(pure_numbers) == 1 and pure_numbers[0] > 50:
                        owgr = pure_numbers[0]
                        break
                        
                # Try to find country code
                country_match = re.search(r'\b([A-Z]{3})\b', parent_text)
                if country_match and country_match.group(1) not in ['THE', 'PGA', 'AND', 'FOR', 'TOP']:
                    country = country_match.group(1)
                    
            except Exception as e:
                pass
            
            # Build headshot URL using PGA Tour CDN
            headshot_url = f"https://pga-tour-res.cloudinary.com/image/upload/c_thumb,g_face,z_0.7,q_auto,f_auto,dpr_2.0,w_80,h_80/headshots_{player_id}"
            
            players.append({
                'player_id': player_id,
                'player_name': name,
                'country': country,
                'owgr': owgr,
                'headshot_url': headshot_url
            })
            
        except Exception as e:
            continue
    
    # Method 2: Parse page source for JSON data if we didn't get much
    if len(players) < 50:
        print("🔍 Trying to extract data from page source...")
        page_source = driver.page_source
        
        json_patterns = [
            r'__NEXT_DATA__[^>]*>([^<]+)<',
            r'"players"\s*:\s*(\[[^\]]+\])',
            r'"field"\s*:\s*(\[[^\]]+\])',
        ]
        
        for pattern in json_patterns:
            matches = re.findall(pattern, page_source)
            for match in matches:
                try:
                    data = json.loads(match)
                    if isinstance(data, list):
                        for p in data:
                            if isinstance(p, dict):
                                pid = str(p.get('id', p.get('playerId', p.get('player_id', ''))))
                                pname = p.get('name', p.get('playerName', p.get('displayName', '')))
                                if pid and pname and pid not in seen_ids:
                                    seen_ids.add(pid)
                                    players.append({
                                        'player_id': pid,
                                        'player_name': pname,
                                        'country': p.get('country', p.get('countryCode', '')),
                                        'owgr': p.get('owgr', p.get('worldRanking', p.get('rank', None))),
                                        'headshot_url': p.get('headshot', f"https://pga-tour-res.cloudinary.com/image/upload/headshots_{pid}")
                                    })
                except:
                    continue
    
    print(f"✅ Found {len(players)} players")
    return players

def upload_to_supabase(tournament_id, players):
    """Upload player data to Supabase"""
    try:
        from supabase import create_client
        
        print(f"☁️ Uploading {len(players)} players to Supabase...")
        
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        
        # Delete existing field for this tournament
        supabase.table('tournament_field').delete().eq('tournament_id', tournament_id).execute()
        print(f"🗑️ Cleared existing field for {tournament_id}")
        
        # Insert new players
        records = []
        for p in players:
            records.append({
                'tournament_id': tournament_id,
                'player_id': p['player_id'],
                'player_name': p['player_name'],
                'country': p.get('country', ''),
                'owgr': p.get('owgr'),
                'headshot_url': p.get('headshot_url', '')
            })
        
        # Insert in batches
        batch_size = 100
        for i in range(0, len(records), batch_size):
            batch = records[i:i+batch_size]
            supabase.table('tournament_field').insert(batch).execute()
            print(f"📤 Uploaded batch {i//batch_size + 1}: {len(batch)} players")
        
        print(f"✅ Successfully uploaded {len(records)} players to Supabase")
        return True
        
    except Exception as e:
        print(f"❌ Error uploading to Supabase: {e}")
        import traceback
        traceback.print_exc()
        return False

def save_to_json(tournament_id, tournament_name, players):
    """Save players to JSON file as backup"""
    filename = f"field_{tournament_id}.json"
    
    with open(filename, 'w') as f:
        json.dump({
            'tournament_id': tournament_id,
            'tournament_name': tournament_name,
            'scraped_at': datetime.now().isoformat(),
            'player_count': len(players),
            'players': players
        }, f, indent=2)
    
    print(f"💾 Saved backup to {filename}")

def main():
    print("🏌️ PGA Tour Field Scraper")
    print("=" * 50)
    
    # Check for --list flag
    if '--list' in sys.argv:
        driver = setup_driver(headless=True)
        try:
            get_upcoming_tournaments(driver, list_all=True)
        finally:
            driver.quit()
        return
    
    # Check if URL provided or auto-detect
    if len(sys.argv) > 1 and not sys.argv[1].startswith('--'):
        url = sys.argv[1]
        tournament_id = re.search(r'(R\d+)', url)
        tournament_id = tournament_id.group(1) if tournament_id else 'unknown'
        tournament_name = 'Unknown Tournament'
    else:
        url = None
        tournament_id = None
        tournament_name = None
    
    driver = setup_driver(headless=True)
    
    try:
        # Auto-detect upcoming tournament if no URL provided
        if not url:
            tournament = get_upcoming_tournament(driver)
            if not tournament:
                print("❌ Could not find upcoming tournament")
                print("💡 Try running with --list to see available tournaments")
                print("💡 Or provide a URL: python scrape_field.py <tournament_url>")
                return
            
            url = tournament['url']
            tournament_id = tournament['tournament_id']
            tournament_name = tournament['name']
        
        print(f"\n📍 Tournament: {tournament_name or tournament_id}")
        print("-" * 50)
        
        # Scrape the field
        players = scrape_field(driver, url)
        
        if players:
            # Save backup JSON
            save_to_json(tournament_id, tournament_name, players)
            
            # Upload to Supabase
            upload_to_supabase(tournament_id, players)
            
            print("\n✅ Done!")
            print(f"   Tournament: {tournament_name or tournament_id}")
            print(f"   Players: {len(players)}")
        else:
            print("❌ No players found")
            print("💡 Try running with --visible flag to see what's happening")
            
    finally:
        driver.quit()

if __name__ == "__main__":
    main()