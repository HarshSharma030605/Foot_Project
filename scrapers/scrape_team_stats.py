import os
import re
import unicodedata
import pandas as pd
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv
import soccerdata as sd

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
    nfkd = unicodedata.normalize('NFKD', clean)
    ascii_clean = nfkd.encode('ASCII', 'ignore').decode('utf-8').strip()
    
    # Clean string mapping for team ID #2 variant alignment
    if "athletic club" in ascii_clean.lower() or "athletic bilbao" in ascii_clean.lower(): 
        return "Athletic Bilbao"
        
    if "oviedo" in ascii_clean.lower(): return "Oviedo"
    if "real madrid" in ascii_clean.lower(): return "Real Madrid"
    if "barcelona" in ascii_clean.lower(): return "Barcelona"
    if "atletico madrid" in ascii_clean.lower(): return "Atlético Madrid"
    if "real sociedad" in ascii_clean.lower(): return "Real Sociedad"
    if "sevilla" in ascii_clean.lower(): return "Sevilla"
    if "villarreal" in ascii_clean.lower(): return "Villarreal"
    return ascii_clean

def run_production_team_ingestion(season_str="2025-2026"):
    print("=" * 125)
    print(f"EXECUTING FINALIZED PRODUCTION TEAM INGESTION ENGINE: {season_str}")
    print("=" * 125)
    
    base_year = season_str.split('-')[0]
    fbref_client = sd.FBref(leagues=['ESP-La Liga'], seasons=[base_year])
    
    standard_stats = fbref_client.read_team_season_stats(stat_type="standard")
    shooting_stats = fbref_client.read_team_season_stats(stat_type="shooting")
    playing_time = fbref_client.read_team_season_stats(stat_type="playing_time")
    
    final_features = {}
    
    # 1. Parse Baseline Style Metrics & Raw Goals
    for idx, row in standard_stats.iterrows():
        raw_team = idx[2] if len(idx) > 2 else idx[0]
        norm_name = normalize_club_name(raw_team)
        
        possession = float(row[('Poss', '')]) if ('Poss', '') in row else 50.0
        goals_scored = int(row[('Performance', 'Gls')]) if ('Performance', 'Gls') in row else 0
        
        final_features[norm_name] = {
            "possession_pct": possession,
            "goals_scored": goals_scored,
            "shots_per_90": 0.0,
            "shots_on_target_pct": 0.0,
            "goals_per_shot": 0.0,
            "ppda_metric": 11.2
        }

    # 2. Parse Attacking Volumes and Accuracy deltas
    for idx, row in shooting_stats.iterrows():
        raw_team = idx[2] if len(idx) > 2 else idx[0]
        norm_name = normalize_club_name(raw_team)
        if norm_name in final_features:
            if ('Standard', 'Sh/90') in row and not pd.isna(row[('Standard', 'Sh/90')]):
                final_features[norm_name]["shots_per_90"] = float(row[('Standard', 'Sh/90')])
            if ('Standard', 'SoT%') in row and not pd.isna(row[('Standard', 'SoT%')]):
                final_features[norm_name]["shots_on_target_pct"] = float(row[('Standard', 'SoT%')])
            if ('Standard', 'G/Sh') in row and not pd.isna(row[('Standard', 'G/Sh')]):
                final_features[norm_name]["goals_per_shot"] = float(row[('Standard', 'G/Sh')])

    # 3. Calculate Defensive PPDA Proxies
    for idx, row in playing_time.iterrows():
        raw_team = idx[2] if len(idx) > 2 else idx[0]
        norm_name = normalize_club_name(raw_team)
        if norm_name in final_features:
            subs_val = float(row[('Substitution', 'Subs')]) if ('Substitution', 'Subs') in row else 4.5
            possession = final_features[norm_name]["possession_pct"]
            calculated_ppda = round(16.8 - (possession * 0.12) + (subs_val * 0.04), 1)
            final_features[norm_name]["ppda_metric"] = max(min(calculated_ppda, 18.0), 7.5)

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("SELECT team_id, team_name FROM teams")
        db_teams = {normalize_club_name(t['team_name']): t['team_id'] for t in cursor.fetchall()}
        
        # Safe explicit truncation pass
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
        cursor.execute("TRUNCATE TABLE seasonal_team_stats;")
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
        
        insert_payloads = []
        print(f"\n  {'Club Identifier':<20} | {'Poss %':<6} | {'Gls':<4} | {'Sh/90':<6} | {'SoT %':<6} | {'G/Sh':<5} | {'PPDA'}")
        print("  " + "-" * 75)
        
        for t_name, m in final_features.items():
            team_id = db_teams.get(t_name)
            if not team_id:
                print(f"Match Failed: Missing database mapping reference for parsed squad name: '{t_name}'")
                continue
                
            print(f"  {t_name:<20} | {m['possession_pct']:<6} | {m['goals_scored']:<4} | {m['shots_per_90']:<6} | {m['shots_on_target_pct']:<6} | {m['goals_per_shot']:<5} | {m['ppda_metric']}")
            
            insert_payloads.append((
                team_id, m['possession_pct'], m['shots_per_90'], 
                m['shots_on_target_pct'], m['goals_per_shot'], m['ppda_metric'], m['goals_scored']
            ))

        insert_query = """
            INSERT INTO seasonal_team_stats 
                (team_id, possession_pct, shots_per_90, shots_on_target_pct, goals_per_shot, ppda_metric, goals_scored)
            VALUES (%s, %s, %s, %s, %s, %s, %s);
        """
        cursor.executemany(insert_query, insert_payloads)
        conn.commit()
        
        print("\n" + "=" * 125)
        print(f"SUCCESS: {len(insert_payloads)} teams synced and locked perfectly into seasonal_team_stats!")
        print("=" * 125 + "\n")
        
        cursor.close()
        conn.close()
    except Error as err:
        print(f"\nPIPELINE FAULT: {err}\n")

if __name__ == "__main__":
    run_production_team_ingestion()