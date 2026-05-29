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

def normalize_string(text):
    if not text: return ""
    nfkd = unicodedata.normalize('NFKD', str(text))
    return nfkd.encode('ASCII', 'ignore').decode('utf-8').strip().lower()

def run_surgical_role_updates(season_str="2025-2026"):
    print("=" * 115)
    print(f"EXECUTING SURGICAL SQUAD ROLE UPDATE PIPELINE (SAFE MODE): {season_str}")
    print("=" * 115)
    
    base_year = season_str.split('-')[0]
    fbref_client = sd.FBref(leagues=['ESP-La Liga'], seasons=[base_year])
    
    print("Fetching playing time metrics from local FBref cache...")
    p_playing_time = fbref_client.read_player_season_stats(stat_type="playing_time")
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # 1. PULL EXISTING PLAYERS TO MAP NAMES TO PLAYER_IDs
        print(" 🔍 Loading master player directory to prevent stray insertions...")
        cursor.execute("SELECT player_id, player_name FROM players")
        # Map normalized names directly to their database primary key: {normalized_name: player_id}
        db_player_map = {normalize_string(p['player_name']): p['player_id'] for p in cursor.fetchall()}
        print(f"    ✅ Master player directory loaded: tracking {len(db_player_map)} database profiles.")
        
        # Flatten MultiIndex columns from SoccerData output
        df_flat = p_playing_time.copy()
        df_flat.columns = ['_'.join(str(lvl) for lvl in col).strip() if isinstance(col, tuple) else str(col) for col in df_flat.columns]
        df_flat = df_flat.reset_index()
        
        mp_col = [c for c in df_flat.columns if "playing time_mp" in c.lower()][0]
        min_col = [c for c in df_flat.columns if "playing time_min" in c.lower() and "mn/" not in c.lower() and "%" not in c.lower()][0]
        starts_col = [c for c in df_flat.columns if "starts_starts" in c.lower()][0]

        update_payloads = []
        
        for idx, row in df_flat.iterrows():
            raw_player = row['player']
            norm_player = normalize_string(raw_player)
            
            # CRITICAL CHECK: Get the exact player_id from your database
            player_id = db_player_map.get(norm_player)
            if not player_id:
                continue # Skip stray players completely
                
            mp = int(row[mp_col]) if not pd.isna(row[mp_col]) else 0
            starts = int(row[starts_col]) if not pd.isna(row[starts_col]) else 0
            minutes = int(row[min_col]) if not pd.isna(row[min_col]) else 0

            # --- SQUAD ROLE LOGIC ENGINE ---
            if minutes < 90:
                assigned_status = "Injured/Reserve"
            elif starts >= (mp * 0.40) and minutes > 500:
                assigned_status = "Starter"
            else:
                assigned_status = "Substitute"
            
            # Payload order matches the UPDATE query parameters: (squad_role, player_id)
            update_payloads.append((assigned_status, player_id))

        if not update_payloads:
            print("No matching players found between the database and the scraped data. No changes made.")
            cursor.close()
            conn.close()
            return

        # 2. MANDATORY UPDATE ONLY (No data loss possible)
        print(f"Executing mandatory updates for {len(update_payloads)} player assignments...")
        
        # Turn off safe updates temporarily for the session if needed, though matching by PK is fine
        cursor.execute("SET SQL_SAFE_UPDATES = 0;")
        
        update_query = """
            UPDATE squad_assignments 
            SET squad_role = %s 
            WHERE player_id = %s;
        """
        cursor.executemany(update_query, update_payloads)
        
        cursor.execute("SET SQL_SAFE_UPDATES = 1;")
        conn.commit()
        
        print("\n" + "=" * 115)
        print(f"SUCCESS: {len(update_payloads)} roles updated in squad_assignments with zero data loss!")
        print("=" * 115 + "\n")
        
        cursor.close()
        conn.close()
    except Error as err:
        print(f"\nUPDATE TRANSACTION FAILED:\n{err}\n")

if __name__ == "__main__":
    run_surgical_role_updates()