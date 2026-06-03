import os
import re
import random
import unicodedata
import mysql.connector
import pandas as pd
import soccerdata as sd
from dotenv import load_dotenv
import sys
from rapidfuzz import process, fuzz

# --- 1. ENVIRONMENT CONFIGURATION ---
load_dotenv()

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("DB_PORT", 3306)),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD"),
    "database": os.getenv("DB_NAME")
}

# Explicit mapping for players where nicknames or surnames vary wildly between systems
EXPLICIT_PLAYER_MAPPING = {
    "youssefenriquez": "youssefenriquezlechal",
    "carlosprotesoni": "carlosbenavidez",  # Handles maternal/paternal surname flips
    "jonnyotto": "jonny",
    "marianodiaz": "marianodiazmejia"
}

def normalize_name(name):
    """Strips accents, spaces, and punctuation for baseline comparisons."""
    if pd.isna(name): return ""
    clean = unicodedata.normalize('NFKD', str(name)).encode('ASCII', 'ignore').decode('utf-8')
    clean = re.sub(r'[^a-z]', '', clean.lower())
    # Apply explicit override mapping if found
    return EXPLICIT_PLAYER_MAPPING.get(clean, clean)

def run_valuation_update_pipeline():
    print("[1/4] Fetching True Ages and Table Metadata from Local Database...")
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM squad_assignments")
        total_assignments = cursor.fetchone()[0]
        print(f"VERIFICATION: Current total rows in 'squad_assignments' = {total_assignments}")
        
        query = "SELECT player_id, player_name, age FROM players" 
        df_db = pd.read_sql(query, conn)
        df_db["Merge_Key"] = df_db["player_name"].apply(normalize_name)
        print(f"--> Loaded {len(df_db)} verified player profiles from 'players' table.")
        
    except Exception as e:
        print(f"Database Error: {e}")
        return

    print("\n[2/4] Extracting On-Pitch Performance Data via soccerdata...")
    try:
        fbref = sd.FBref(seasons="25-26", leagues="ESP-La Liga")
        df_fbref = fbref.read_player_season_stats(stat_type="standard")
        
        if isinstance(df_fbref.columns, pd.MultiIndex):
            df_fbref.columns = ['_'.join(col).strip() for col in df_fbref.columns.values]
        df_fbref = df_fbref.reset_index()
        
        player_col = 'player' if 'player' in df_fbref.columns else df_fbref.columns[df_fbref.columns.str.lower().str.contains('player')][0]
        min_col = next((col for col in df_fbref.columns if 'min' in col.lower() and '90' not in col.lower()), None)
        gls_col = next((col for col in df_fbref.columns if 'gls' in col.lower() or 'goals' in col.lower()), None)
        ast_col = next((col for col in df_fbref.columns if 'ast' in col.lower() or 'assists' in col.lower()), None)
        
        df_fbref["Merge_Key"] = df_fbref[player_col].apply(normalize_name)
        
        def clean_numeric(val):
            try: return float(val) if pd.notna(val) else 0.0
            except: return 0.0

        df_fbref["Minutes"] = df_fbref[min_col].apply(clean_numeric)
        df_fbref["Contributions"] = df_fbref[gls_col].apply(clean_numeric) + df_fbref[ast_col].apply(clean_numeric)
        
        # Keep a list of FBref keys for fuzzy fallback matching logic
        fbref_keys = df_fbref["Merge_Key"].tolist()

    except Exception as e:
        print(f"Scraper Error: {e}")
        return

    print("\n[3/4] Executing Hybrid Fuzzy Name Matching Linker...")
    
    matched_rows = []
    
    # Iterate through database players and check for names with variance
    for _, db_row in df_db.iterrows():
        db_key = db_row["Merge_Key"]
        
        # Try direct matching first
        fbref_match = df_fbref[df_fbref["Merge_Key"] == db_key]
        
        # Fallback to Fuzzy String Matching if direct match fails
        if fbref_match.empty and len(db_key) > 4:
            # Extract closest match based on Token Sort Similarity
            best_match = process.extractOne(db_key, fbref_keys, scorer=fuzz.token_sort_ratio)
            if best_match and best_match[1] >= 82.0:  # 82% match ratio safety threshold
                fbref_match = df_fbref[df_fbref["Merge_Key"] == best_match[0]]
        
        if not fbref_match.empty:
            match_data = fbref_match.iloc[0]
            matched_rows.append({
                "player_id": db_row["player_id"],
                "player_name": db_row["player_name"],
                "age": db_row["age"],
                "Minutes": match_data["Minutes"],
                "Contributions": match_data["Contributions"]
            })
            
    df_merged = pd.DataFrame(matched_rows)
    print(f"--> Fuzzy Matching Resolution Complete. Linked rows expanded to {len(df_merged)} entries.")
    
    # Calculate Synthetic Market Value
    def calculate_synthetic_value(row):
        base_value = 2_000_000.0
        minutes_value = row["Minutes"] * 5000.0
        production_value = row["Contributions"] * 1_000_000.0
        raw_value = base_value + minutes_value + production_value
        
        age = row["age"]
        if age <= 21: multiplier = 1.5
        elif age <= 24: multiplier = 1.2
        elif age <= 28: multiplier = 1.0
        elif age <= 31: multiplier = 0.6
        else: multiplier = 0.3
            
        final_value = raw_value * multiplier
        return final_value if final_value > 500_000.0 else 500_000.0
        
    df_merged["Market_Value_€"] = df_merged.apply(calculate_synthetic_value, axis=1)
    
    # Strategic Contract Deadline Engine
    def allocate_strategic_contract(row):
        age = row["age"]
        value = row["Market_Value_€"]
        current_year = 2026
        
        if age <= 21 and value >= 25_000_000.0:
            end_year = current_year + 5  
        elif age <= 23:
            end_year = current_year + random.choice([3, 4])
        elif age <= 28:
            end_year = current_year + random.choice([2, 3, 4])
        elif age <= 32:
            end_year = current_year + random.choice([1, 2])
        else:
            end_year = current_year + 1
            
        return f"{end_year}-06-30"

    df_merged["Contract_End_Date"] = df_merged.apply(allocate_strategic_contract, axis=1)
    df_merged = df_merged.sort_values(by="Market_Value_€", ascending=False)
    
    print("\n" + "="*90)
    print(f"{'ID':<4} | {'PLAYER':<25} | {'TRUE AGE':<8} | {'CONTRACT END':<12} | {'SYNTHETIC VALUE (€)':<20}")
    print("="*90)
    
    staging_batch = []
    for _, row in df_merged.iterrows():
        player_id = int(row['player_id'])
        market_value = float(row['Market_Value_€'])
        contract_end = row['Contract_End_Date']
        staging_batch.append((market_value, contract_end, player_id))
        
        if len(staging_batch) <= 15:
            print(f"{player_id:<4} | {str(row['player_name'])[:25]:<25} | {row['age']:<8} | {contract_end:<12} | €{market_value:,.0f}")
            
    if len(staging_batch) > 15:
        print(f"... and {len(staging_batch) - 15} more players queued for update.")
    print("="*90 + "\n")

    # --- 4. Interactive Staging Gate ---
    print(f"Cross-Verification Summary:")
    print(f"   - Total rows in Target DB Table ('squad_assignments'): {total_assignments}")
    print(f"   - Matched Scraper Rows Queued for Update: {len(staging_batch)}")
    
    user_approval = input(f"\nPush these {len(staging_batch)} fuzzy-resolved updates to the 'squad_assignments' table? (y/n): ").strip().lower()
    
    if user_approval != 'y':
        print("\nTransaction aborted by user. Database parameters left untouched.")
        cursor.close()
        conn.close()
        sys.exit(0)

    print("\n[4/4] Authorization verified. Executing MySQL UPDATE transaction...")
    try:
        update_query = """
            UPDATE squad_assignments 
            SET market_value = %s, contract_end_date = %s 
            WHERE player_id = %s
        """
        cursor.executemany(update_query, staging_batch)
        conn.commit()
        print(f"SUCCESS: Financial data locked in. {cursor.rowcount} rows updated in 'squad_assignments'.")
        
    except Exception as err:
        print(f"Transaction Failure Error: {err}")
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals(): conn.close()

if __name__ == "__main__":
    run_valuation_update_pipeline()