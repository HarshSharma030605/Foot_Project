import os
import re
import time
import requests
from bs4 import BeautifulSoup
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv

load_dotenv()

CLUB_MAPPING = {
    "Alavés": {"url": "https://en.wikipedia.org/wiki/Deportivo_Alav%C3%A9s", "index": 12, "layout": "split", "start_row": 0},
    "Athletic Bilbao": {"url": "https://en.wikipedia.org/wiki/2025%E2%80%9326_Athletic_Bilbao_season", "index": 2, "layout": "split", "start_row": 0},
    "Atlético Madrid": {"url": "https://en.wikipedia.org/wiki/2025%E2%80%9326_Atl%C3%A9tico_Madrid_season", "index": 3, "layout": "split", "start_row": 0},
    "Barcelona": {"url": "https://en.wikipedia.org/wiki/2025%E2%80%9326_FC_Barcelona_season", "index": 4, "layout": "single", "start_row": 0},
    "Celta Vigo": {"url": "https://en.wikipedia.org/wiki/2025%E2%80%9326_RC_Celta_de_Vigo_season", "index": 2, "layout": "split", "start_row": 0},
    "Elche": {"url": "https://en.wikipedia.org/wiki/2025%E2%80%9326_Elche_CF_season", "index": 2, "layout": "single", "start_row": 0},
    "Espanyol": {"url": "https://en.wikipedia.org/wiki/2025%E2%80%9326_RCD_Espanyol_season", "index": 2, "layout": "split", "start_row": 0},
    "Getafe": {"url": "https://en.wikipedia.org/wiki/Getafe_CF", "index": 8, "layout": "split", "start_row": 0},
    "Girona": {"url": "https://en.wikipedia.org/wiki/Girona_FC", "index": 12, "layout": "single", "start_row": 0},
    "Levante": {"url": "https://en.wikipedia.org/wiki/Levante_UD", "index": 12, "layout": "single", "start_row": 0},
    "Mallorca": {"url": "https://en.wikipedia.org/wiki/RCD_Mallorca", "index": 11, "layout": "single", "start_row": 0},
    "Osasuna": {"url": "https://en.wikipedia.org/wiki/CA_Osasuna", "index": 13, "layout": "single", "start_row": 0},
    "Oviedo": {"url": "https://en.wikipedia.org/wiki/2025%E2%80%9326_Real_Oviedo_season", "index": 2, "layout": "single", "start_row": 0},
    "Rayo Vallecano": {"url": "https://en.wikipedia.org/wiki/2025%E2%80%9326_Rayo_Vallecano_season", "index": 3, "layout": "single", "start_row": 0},
    "Real Betis": {"url": "https://en.wikipedia.org/wiki/Real_Betis", "index": 17, "layout": "split", "start_row": 0},
    "Real Madrid": {"url": "https://en.wikipedia.org/wiki/2025%E2%80%9326_Real_Madrid_CF_season", "index": 4, "layout": "split", "start_row": 0},
    "Real Sociedad": {"url": "https://en.wikipedia.org/wiki/2025%E2%80%9326_Real_Sociedad_season", "index": 2, "layout": "split", "start_row": 0},
    "Sevilla": {"url": "https://en.wikipedia.org/wiki/2025%E2%80%9326_Sevilla_FC_season", "index": 2, "layout": "single", "start_row": 0},
    "Valencia": {"url": "https://en.wikipedia.org/wiki/Valencia_CF", "index": 3, "layout": "split", "start_row": 0},
    "Villarreal": {"url": "https://en.wikipedia.org/wiki/2025%E2%80%9326_Villarreal_CF_season", "index": 2, "layout": "split", "start_row": 0}
}

POSITION_MAP = {
    "Attacking Midfielder": "Attacking Midfielder",
    "Secondary Striker": "Secondary Striker",
    "Second Striker": "Secondary Striker",
    "Defensive Midfielder": "Defensive Midfielder",
    "Central Midfielder": "Central Midfielder",
    "Centre-Back": "Centre-Back",
    "Right-Back": "Right-Back",
    "Left-Back": "Left-Back",
    "Right Winger": "Right Winger",
    "Left Winger": "Left Winger"
}

def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv('DB_HOST'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        database=os.getenv('DB_NAME')
    )

def clean_text_noise(text):
    if not text:
        return ""
    return text.split('(')[0].split('[')[0].strip()

def parse_inline_age(text):
    if not text:
        return None
    match = re.search(r'aged?\s+(\d+)', text, re.IGNORECASE)
    if match:
        return int(match.group(1))
    match_paren = re.search(r'\(age\s+(\d+)\)', text, re.IGNORECASE)
    if match_paren:
        return int(match_paren.group(1))
    return None

def parse_birthplace_country(td_element):
    if not td_element:
        return "Unknown"
    raw_text = clean_text_noise(td_element.text.strip())
    if ',' in raw_text:
        parts = [p.strip() for p in raw_text.split(',')]
        if parts and len(parts[-1]) > 2:
            return parts[-1]
    return raw_text

def deep_crawl_profile_details(relative_url):
    details = {"age": None, "nationality": "Unknown", "positions_list": []}
    if not relative_url:
        return details
    
    url = f"https://en.wikipedia.org{relative_url}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        time.sleep(0.04)
        resp = requests.get(url, headers=headers)
        if resp.status_code != 200:
            return details
        soup = BeautifulSoup(resp.text, 'html.parser')
        infobox = soup.find('table', class_='infobox')
        if not infobox:
            return details
        
        details["age"] = parse_inline_age(infobox.text)
        
        for row in infobox.find_all('tr'):
            th = row.find('th')
            td = row.find('td')
            if th and td:
                header = th.text.lower()
                
                if any(k in header for k in ['nationality', 'citizenship']):
                    details["nationality"] = parse_birthplace_country(td)
                elif 'place of birth' in header or 'birthplace' in header:
                    if details["nationality"] == "Unknown":
                        details["nationality"] = parse_birthplace_country(td)
                elif 'position' in header:
                    raw_chunks = list(td.stripped_strings)
                    processed_chunks = []
                    
                    for chunk in raw_chunks:
                        cleaned_chunk = clean_text_noise(chunk).replace(',', '').strip()
                        cleaned_chunk = re.sub(r'[\d\]\[,]', '', cleaned_chunk).strip()
                        
                        if cleaned_chunk and cleaned_chunk.lower() not in ['and', '/', '']:
                            spaced = re.sub(r'([a-z])([A-Z])', r'\1 / \2', cleaned_chunk)
                            for sub_p in spaced.split('/'):
                                sub_clean = sub_p.strip().title()
                                if sub_clean and len(sub_clean) > 2:
                                    mapped_pos = POSITION_MAP.get(sub_clean, sub_clean)
                                    processed_chunks.append(mapped_pos)
                                    
                    seen = set()
                    details["positions_list"] = [x for x in processed_chunks if not (x in seen or seen.add(x))]
                    
        return details
    except Exception:
        return details

def extract_team_roster(team_name, config):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    resp = requests.get(config["url"], headers=headers)
    if resp.status_code != 200:
        return []
        
    soup = BeautifulSoup(resp.text, 'html.parser')
    tables = soup.find_all('table')
    
    if len(tables) <= config["index"]:
        return []
        
    target_table = tables[config["index"]]
    players_extracted = []
    rows = target_table.find_all('tr')[config["start_row"]:]
    
    for row in rows:
        cells = row.find_all(['td', 'th'])
        if len(cells) < 3:
            continue
            
        row_text = row.text.lower()
        if "no." in row_text and "player" in row_text:
            continue
        if len(cells) == 1 and any(h in row_text for h in ['goalkeepers', 'defenders', 'midfielders', 'forwards']):
            continue
            
        if config["layout"] == "single":
            name_cell = None
            jersey_num = None
            
            for idx, cell in enumerate(cells):
                a_tag = cell.find('a')
                if a_tag and len(cell.text.strip()) > 2:
                    clean_cell_check = cell.text.strip().lower()
                    if clean_cell_check in ['gk', 'df', 'mf', 'fw', 'pos.', 'no.', 'nat.', 'transfer fee', 'fee']:
                        continue
                    if cell.find('span', class_='flagicon'):
                        continue
                        
                    name_cell = cell
                    
                    for b_idx in range(idx - 1, -1, -1):
                        b_text = cells[b_idx].text.strip()
                        num_match = re.search(r'\b\d+\b', b_text)
                        if num_match:
                            jersey_num = int(num_match.group(0))
                            break
                    break
            
            if name_cell:
                p_name = clean_text_noise(name_cell.text)
                if p_name and len(p_name) > 3 and not p_name.isupper() and "fee" not in p_name.lower():
                    players_extracted.append({
                        "name": p_name, "jersey": jersey_num, "link": name_cell.find('a').get('href')
                    })
                    
        elif config["layout"] == "split":
            if len(cells) > 3 and cells[3].find('a'):
                l_name = clean_text_noise(cells[3].text)
                if l_name and len(l_name) > 3 and l_name.lower() not in ['player', 'nation', 'no.', 'pos.']:
                    num_l = re.search(r'\d+', cells[0].text.strip())
                    players_extracted.append({
                        "name": l_name, "jersey": int(num_l.group(0)) if num_l else None, "link": cells[3].find('a').get('href')
                    })
            if len(cells) >= 8 and cells[7].find('a'):
                r_name = clean_text_noise(cells[7].text)
                if r_name and len(r_name) > 3 and r_name.lower() not in ['player', 'nation', 'no.', 'pos.']:
                    num_r = re.search(r'\d+', cells[4].text.strip())
                    players_extracted.append({
                        "name": r_name, "jersey": int(num_r.group(0)) if num_r else None, "link": cells[7].find('a').get('href')
                    })
                    
    return players_extracted

def batch_load_data_to_db(players, assignments, positions):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.executemany("INSERT IGNORE INTO players (player_id, player_name, age, nationality) VALUES (%s, %s, %s, %s)", players)
        conn.commit()
        
        cursor.executemany("INSERT IGNORE INTO squad_assignments (player_id, team_id, squad_role, jersey_number, contract_end_date) VALUES (%s, %s, %s, %s, %s)", assignments)
        conn.commit()
        
        cursor.executemany("INSERT IGNORE INTO player_positions (player_id, position, position_priority) VALUES (%s, %s, %s)", positions)
        conn.commit()
        
        cursor.close()
        conn.close()
    except Error as e:
        print(f"  ❌ Database Transaction Write Failure: {e}")

if __name__ == "__main__":
    print("=" * 85)
    print("        LAUNCHING FULLY AUTOMATED UNIFIED INGESTION ENGINE        ")
    print("=" * 85)
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT team_id, team_name FROM teams")
        db_teams = cursor.fetchall()
        cursor.close()
        conn.close()
    except Error as e:
        print(f"Failed to fetch team records from database: {e}")
        exit(1)
        
    global_player_id = 1
    
    for team_id, team_name in db_teams:
        if team_name not in CLUB_MAPPING:
            continue
            
        config = CLUB_MAPPING[team_name]
        print(f"🚀 Processing squad: {team_name.upper()}...")
        
        roster_nodes = extract_team_roster(team_name, config)
        if not roster_nodes:
            continue
            
        team_players = []
        team_assignments = []
        team_positions = []
        
        for node in roster_nodes:
            profile = deep_crawl_profile_details(node["link"])
            
            team_players.append((global_player_id, node["name"], profile["age"], profile["nationality"]))
            team_assignments.append((global_player_id, team_id, None, node["jersey"], None))
            
            p_list = profile["positions_list"] if profile["positions_list"] else ["Unknown"]
            for idx, pos in enumerate(p_list):
                priority = "Primary" if idx == 0 else "Secondary"
                team_positions.append((global_player_id, pos, priority))
                
            global_player_id += 1

        # Automatically batch commit the current club payload immediately
        batch_load_data_to_db(team_players, team_assignments, team_positions)
        print(f"   Saved {len(team_players)} profiles successfully.")
            
    print("\n" + "=" * 85)
    print(" AUTOMATED INGESTION MIGRATION PIPELINE PROCESS COMPLETE.")
    print("=" * 85 + "\n")