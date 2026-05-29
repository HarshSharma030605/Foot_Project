import os
import re
import unicodedata
from bs4 import BeautifulSoup
import mysql.connector
from mysql.connector import Error
import requests
from dotenv import load_dotenv

load_dotenv()

def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv('DB_HOST'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        database=os.getenv('DB_NAME')
    )

def normalize_club_name(name):
    if not name:
        return ""
    clean = re.sub(r'\([\w\s]+\)|\[\w+\]', '', name)
    clean = re.sub(r'\bwon\s+\d+–\d+\s+on\s+penalties\b', '', clean, flags=re.IGNORECASE)
    clean = clean.replace('–', '-')
    
    nfkd = unicodedata.normalize('NFKD', clean)
    ascii_only = nfkd.encode('ASCII', 'ignore').decode('utf-8')
    ascii_clean = ascii_only.strip()
    
    # Force the parser to return the exact string expected by your database primary keys
    if "oviedo" in ascii_clean.lower(): return "Oviedo"
    
    if "real madrid" in ascii_clean.lower(): return "Real Madrid"
    if "barcelona" in ascii_clean.lower(): return "Barcelona"
    if "atletico madrid" in ascii_clean.lower(): return "Atlético Madrid"
    if "real sociedad" in ascii_clean.lower(): return "Real Sociedad"
    if "sevilla" in ascii_clean.lower(): return "Sevilla"
    if "villarreal" in ascii_clean.lower(): return "Villarreal"
    return ascii_clean

def scrape_infobox_winner(url, trophy_label):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = requests.get(url, headers=headers)
        if resp.status_code != 200:
            return None
            
        soup = BeautifulSoup(resp.text, 'html.parser')
        infobox = soup.find('table', class_=lambda x: x and ('infobox' in x or 'veevent' in x))
        if not infobox:
            raise RuntimeError(f"Structure Error: Infobox/Veevent missing on {trophy_label} page.")
            
        for row in infobox.find_all('tr'):
            row_text = row.text.lower()
            if 'champions' in row_text:
                cell = row.find('td')
                if cell:
                    winner_text = cell.text.strip()
                    if winner_text and not any(x in winner_text.lower() for x in ["tbd", "to be decided"]):
                        return normalize_club_name(winner_text)
            
            if 'won' in row_text and 'on penalties' in row_text:
                match = re.search(r'(.+?)\s+won\s+\d+–\d+\s+on\s+penalties', row.text, re.IGNORECASE)
                if match:
                    return normalize_club_name(match.group(1))
    except Exception as e:
        if isinstance(e, RuntimeError):
            raise e
    return None

def sync_trophy_scores_to_db(season_year_str="2025–26"):
    print("=" * 95)
    print(f"RUNNING METRIC INGESTION PIPELINE FOR SEASON: {season_year_str}")
    print("=" * 95)
    
    year_match = re.match(r'(\d{4})–(\d{2,4})', season_year_str)
    if not year_match:
        raise RuntimeError(f"Format Error: Provided season string '{season_year_str}' must match 'YYYY-YY'.")
        
    base_year = year_match.group(1)   
    raw_end = year_match.group(2)     
    end_year = raw_end if len(raw_end) == 4 else f"{base_year[:2]}{raw_end}" 

    dynamic_trophy_map = {}
    spanish_clubs_registry = {"Real Madrid", "Barcelona", "Atlético Madrid", "Real Sociedad", "Sevilla", "Villarreal"}
    spanish_club_contested_supercup = False

    # 1. European Sweep
    print("[DOMAIN 1] Scraping European Continental Domains...")
    long_euro_endpoints = [
        ("UEFA_Champions_League", 75),
        ("UEFA_Europa_League", 45),
        ("UEFA_Conference_League", 30)
    ]
    
    for endpoint, weight in long_euro_endpoints:
        url = f"https://en.wikipedia.org/wiki/{season_year_str}_{endpoint}"
        winner = scrape_infobox_winner(url, endpoint)
        if winner:
            dynamic_trophy_map[winner] = dynamic_trophy_map.get(winner, 0) + weight
            if winner in spanish_clubs_registry and endpoint in ["UEFA_Champions_League", "UEFA_Europa_League"]:
                spanish_club_contested_supercup = True

    if spanish_club_contested_supercup:
        usc_url = f"https://en.wikipedia.org/wiki/{base_year}_UEFA_Super_Cup"
        usc_winner = scrape_infobox_winner(usc_url, "UEFA Super Cup")
        if usc_winner:
            dynamic_trophy_map[usc_winner] = dynamic_trophy_map.get(usc_winner, 0) + 15

    # 2. Domestic Cup Sweep
    print(" 🇪🇸 [DOMAIN 2] Scraping Standalone Spanish Cup Pages...")
    cdr_url = f"https://en.wikipedia.org/wiki/{season_year_str}_Copa_del_Rey"
    cdr_winner = scrape_infobox_winner(cdr_url, "Copa del Rey")
    if cdr_winner:
        dynamic_trophy_map[cdr_winner] = dynamic_trophy_map.get(cdr_winner, 0) + 30
        
    supercopa_url = f"https://en.wikipedia.org/wiki/{end_year}_Supercopa_de_España"
    super_winner = scrape_infobox_winner(supercopa_url, "Supercopa de España")
    if super_winner:
        dynamic_trophy_map[super_winner] = dynamic_trophy_map.get(super_winner, 0) + 10

    # 3. Master Standings & In-Place DB Mapping
    print("[DOMAIN 3] Processing Standings Matrix & Executing Database Sync...")
    la_liga_url = f"https://en.wikipedia.org/wiki/{season_year_str}_La_Liga"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    resp = requests.get(la_liga_url, headers=headers)
    if resp.status_code != 200:
        raise RuntimeError(f"La Liga Master Scrape Failed (HTTP {resp.status_code})")
        
    soup = BeautifulSoup(resp.text, 'html.parser')
    
    infobox = soup.find('table', class_='infobox')
    if not infobox:
        raise RuntimeError("La Liga Structure Error: Season summary Infobox missing.")
        
    la_liga_champ_found = False
    for row in infobox.find_all('tr'):
        if 'champions' in row.text.lower():
            cell = row.find('td')
            if cell:
                champ = normalize_club_name(cell.text)
                dynamic_trophy_map[champ] = dynamic_trophy_map.get(champ, 0) + 50
                la_liga_champ_found = True
                break
                
    if not la_liga_champ_found:
        raise RuntimeError("La Liga Data Error: Unable to locate 'Champions' row inside Infobox.")

    target_table = None
    for table in soup.find_all('table', class_='wikitable'):
        header_text = table.text.lower()
        if 'pos' in header_text and 'pts' in header_text and 'gf' in header_text:
            target_table = table
            break
            
    if not target_table:
        raise RuntimeError("La Liga Structural Error: Master standings table missing.")
        
    # Connect and pull team mappings from database
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT team_id, team_name FROM teams")
    db_teams = {normalize_club_name(t['team_name']): t['team_id'] for t in cursor.fetchall()}
    
    update_payloads = []
    row_count = 0
    
    for row in target_table.find_all('tr'):
        cells = row.find_all(['td', 'th'])
        if len(cells) < 10 or not cells[0].text.strip().isdigit():
            continue
            
        pos = int(cells[0].text.strip())
        team_link = cells[1].find('a')
        if not team_link:
            raise RuntimeError(f"La Liga Layout Exception: Missing link block at row pos #{pos}")
            
        clean_name = normalize_club_name(team_link.text)
        
        # Standardize naming variant convention specifically for database matching
        lookup_name = "Atlético Madrid" if clean_name == "Atletico Madrid" else clean_name
        team_id = db_teams.get(normalize_club_name(lookup_name))
        
        if not team_id:
            continue  # Safely bypass teams not initialized in your primary table seed
            
        goals_for = int(cells[6].text.strip())
        trophy_points = dynamic_trophy_map.get(clean_name, 0)
        
        position_inverse_weight = (21 - pos) / 20.0
        combined_score = round((goals_for * position_inverse_weight) + trophy_points, 2)
        
        # Structure the parameter tuple: (squad_success_metric, team_id)
        update_payloads.append((combined_score, team_id))
        row_count += 1
        
    if row_count == 0:
        raise RuntimeError("Data Mapping Link Error: Zero scraped teams aligned with active database team records.")

    # Execute production write directly into master table
    update_query = """
        UPDATE teams 
        SET squad_success_metric = %s 
        WHERE team_id = %s;
    """
    cursor.executemany(update_query, update_payloads)
    conn.commit()
    
    print(f"\nSUCCESS! Synchronized {len(update_payloads)} rows directly to teams.squad_success_metric.")
    
    cursor.close()
    conn.close()

if __name__ == "__main__":
    try:
        sync_trophy_scores_to_db()
    except RuntimeError as err:
        print(f"\nDATA INGESTION ABORTED CRITICALLY:\n{err}\n")
    except Error as db_err:
        print(f"\nDATABASE TRANSACTION CRASH:\n{db_err}\n")