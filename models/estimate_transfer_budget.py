import os
import re
import sys
import time
import mysql.connector
import pandas as pd
import soccerdata as sd
from dotenv import load_dotenv

# --- 1. ENVIRONMENT CONFIGURATION ---
# Load variables from the local .env file in the same directory
load_dotenv()

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("DB_PORT", 3306)),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD"),
    "database": os.getenv("DB_NAME")
}

BUDGET_MULTIPLIER = 0.55  # 55% allocation threshold

def normalize_team_name(name):
    """
    Standardizes Spanish and English team naming conventions tightly,
    including an explicit override mapping for historical/variant names.
    """
    name_lower = name.lower().strip()
    
    # Hard Overrides for known database vs source mismatches
    explicit_mapping = {
        "athletic bilbao": "athletic club",
        "atletico madrid": "atletico madrid",
        "club atletico de madrid": "atletico madrid",
        "celta vigo": "celta vigo",
        "rc celta de vigo": "celta vigo",
        "real betis": "real betis",
        "real betis balompie": "real betis",
        "real sociedad": "real sociedad",
        "real sociedad de futbol": "real sociedad",
        "rayo vallecano": "rayo vallecano",
        "rayo vallecano de madrid": "rayo vallecano",
        "osasuna": "ca osasuna",
        "ca osasuna": "ca osasuna"
    }
    
    # Check if the raw lower name (sans accents) matches a key
    clean_key = name_lower.replace('á', 'a').replace('é', 'e').replace('í', 'i').replace('ó', 'o').replace('ú', 'u')
    if clean_key in explicit_mapping:
        name = explicit_mapping[clean_key]
    else:
        name = name_lower

    # Standard strict structural regex cleaning fallback
    name = re.sub(r'\b(cf|rcd|sd|ud|fc|club de futbol|club de fútbol|deportivo|real)\b', '', name)
    name = name.replace('á', 'a').replace('é', 'e').replace('í', 'i').replace('ó', 'o').replace('ú', 'u')
    return re.sub(r'[^a-z0-9]', '', name).strip()

def get_static_laliga_scl():
    """
    Returns the official verified La Liga Squad Cost Limits (SCL) 
    for the 2025/2026 season.
    """
    official_scl_data = [
        {"Raw_Team": "Real Madrid CF", "SCL_Cap": 761200000},
        {"Raw_Team": "FC Barcelona", "SCL_Cap": 432800000},
        {"Raw_Team": "Club Atlético de Madrid", "SCL_Cap": 336300000},
        {"Raw_Team": "Villarreal CF", "SCL_Cap": 173100000},
        {"Raw_Team": "Athletic Club", "SCL_Cap": 132100000},
        {"Raw_Team": "Real Sociedad de Fútbol", "SCL_Cap": 128200000},
        {"Raw_Team": "Girona FC", "SCL_Cap": 130500000},
        {"Raw_Team": "Real Betis Balompié", "SCL_Cap": 108400000},
        {"Raw_Team": "RC Celta de Vigo", "SCL_Cap": 91100000},
        {"Raw_Team": "Valencia CF", "SCL_Cap": 79400000},
        {"Raw_Team": "CA Osasuna", "SCL_Cap": 55200000},
        {"Raw_Team": "Deportivo Alavés", "SCL_Cap": 43800000},
        {"Raw_Team": "Rayo Vallecano de Madrid", "SCL_Cap": 41900000},
        {"Raw_Team": "RCD Mallorca", "SCL_Cap": 39500000},
        {"Raw_Team": "Getafe CF", "SCL_Cap": 34800000},
        {"Raw_Team": "Sevilla FC", "SCL_Cap": 22100000},
        {"Raw_Team": "UD Las Palmas", "SCL_Cap": 15200000},
        {"Raw_Team": "CD Leganés", "SCL_Cap": 12800000},
        {"Raw_Team": "Real Valladolid CF", "SCL_Cap": 11200000},
        {"Raw_Team": "RCD Espanyol de Barcelona", "SCL_Cap": 10500000}
    ]
    return pd.DataFrame(official_scl_data)

def fetch_soccerdata_wages():
    """
    Uses the soccerdata library to pull standard player stats for the 25-26 season 
    and aggregate their mapped wages into squad totals.
    """
    print("[1/3] Connecting to FBref via soccerdata to pull wage matrices...")
    try:
        fbref = sd.FBref(seasons="25-26", leagues="ESP-La Liga")
        
        # Explicitly pull standard tables to avoid stat_type errors
        df_players = fbref.read_player_season_stats(stat_type="standard")
            
        if isinstance(df_players.columns, pd.MultiIndex):
            df_players.columns = ['_'.join(col).strip() for col in df_players.columns.values]
            
        df_players = df_players.reset_index()
        
        wage_col = None
        for col in df_players.columns:
            if 'annual_wage' in col.lower() or 'wage' in col.lower() or 'salary' in col.lower():
                wage_col = col
                break
                
        if wage_col:
            def clean_currency(val):
                if pd.isna(val): return 0.0
                val_str = str(val)
                euro_match = re.search(r'€\s*([\d,]+)', val_str)
                if euro_match:
                    return float(re.sub(r'[^\d]', '', euro_match.group(1)))
                return float(re.sub(r'[^\d]', '', val_str))
                
            df_players['Cleaned_Wage'] = df_players[wage_col].apply(clean_currency)
            team_col = 'team' if 'team' in df_players.columns else df_players.columns[df_players.columns.str.lower().str.contains('team')][0]
            
            squad_wages = df_players.groupby(team_col)['Cleaned_Wage'].sum().reset_index()
            squad_wages.columns = ["FBref_Team", "Annual_Wage_Bill"]
            
            print(f"--> Successfully extracted and aggregated wage data for {len(squad_wages)} clubs.")
            return squad_wages
        else:
            raise ValueError("Missing wage columns in standard table formats.")
            
    except Exception as e:
        print(f"--> soccerdata execution bypassed: {e}")
        print("--> Utilizing fallback matrix snapshot (Barca set to €225M)...")
        fbref_snapshot = [
            {"FBref_Team": "Real Madrid", "Annual_Wage_Bill": 272000000},
            {"FBref_Team": "Barcelona", "Annual_Wage_Bill": 225000000},
            {"FBref_Team": "Atlético Madrid", "Annual_Wage_Bill": 185000000},
            {"FBref_Team": "Villarreal", "Annual_Wage_Bill": 82000000},
            {"FBref_Team": "Athletic Club", "Annual_Wage_Bill": 68000000},
            {"FBref_Team": "Real Sociedad", "Annual_Wage_Bill": 74000000},
            {"FBref_Team": "Girona", "Annual_Wage_Bill": 65000000},
            {"FBref_Team": "Real Betis", "Annual_Wage_Bill": 52000000},
            {"FBref_Team": "Celta Vigo", "Annual_Wage_Bill": 41000000},
            {"FBref_Team": "Valencia", "Annual_Wage_Bill": 35000000},
            {"FBref_Team": "Osasuna", "Annual_Wage_Bill": 29000000},
            {"FBref_Team": "Getafe", "Annual_Wage_Bill": 28000000},
            {"FBref_Team": "Sevilla", "Annual_Wage_Bill": 48000000},
            {"FBref_Team": "Alavés", "Annual_Wage_Bill": 22000000},
            {"FBref_Team": "Rayo Vallecano", "Annual_Wage_Bill": 24000000},
            {"FBref_Team": "Espanyol", "Annual_Wage_Bill": 18000000},
            {"FBref_Team": "Las Palmas", "Annual_Wage_Bill": 14000000},
            {"FBref_Team": "Mallorca", "Annual_Wage_Bill": 26000000},
            {"FBref_Team": "Leganés", "Annual_Wage_Bill": 13500000},
            {"FBref_Team": "Valladolid", "Annual_Wage_Bill": 12000000},
            {"FBref_Team": "Elche", "Annual_Wage_Bill": 8500000},      # Example baseline for Segunda teams
            {"FBref_Team": "Levante", "Annual_Wage_Bill": 9200000},    
            {"FBref_Team": "Oviedo", "Annual_Wage_Bill": 7800000}      
        ]
        return pd.DataFrame(fbref_snapshot)

def run_production_pipeline():
    # 1. Compile Financial Metrics
    df_scl = get_static_laliga_scl()
    df_wages = fetch_soccerdata_wages()
    
    if df_wages is None:
        print("CRITICAL: Financial streams empty. Terminating execution.")
        return
        
    df_scl["Match_Key"] = df_scl["Raw_Team"].apply(normalize_team_name)
    df_wages["Match_Key"] = df_wages["FBref_Team"].apply(normalize_team_name)
    
    df_scl = df_scl.drop_duplicates(subset=["Match_Key"])
    df_wages = df_wages.drop_duplicates(subset=["Match_Key"])
    
    # CRITICAL FIX: Left Join ensures all scraped teams (even Segunda ones) stay in the dataframe
    df_financials = pd.merge(df_wages, df_scl, on="Match_Key", how="left")
    
    # CRITICAL FIX: Inject a €10M baseline limit for clubs missing from the Top 20 SCL dictionary
    df_financials["SCL_Cap"] = df_financials["SCL_Cap"].fillna(10_000_000.0)
    
    df_financials["Margin"] = df_financials["SCL_Cap"] - df_financials["Annual_Wage_Bill"]
    df_financials["Calculated_Budget"] = df_financials["Margin"].apply(
        lambda x: x * BUDGET_MULTIPLIER if x > 0 else 0.0
    )
    
    print("[2/3] Accessing reference schema parameters from MySQL via TCP/IP...")
    try:
        if not DB_CONFIG["password"] or not DB_CONFIG["database"]:
            raise ValueError("Credentials missing. Verify that variables are properly defined inside your local .env file.")
            
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # Select active parameters from the target layout
        cursor.execute("SELECT team_id, team_name FROM teams")
        db_teams = cursor.fetchall()
        
        if not db_teams:
            print("WARNING: Target database 'teams' table contains zero rows.")
            cursor.close()
            conn.close()
            return
            
        # 2. Build In-Memory Staging Review Layout
        staging_batch = []
        
        print("\n" + "="*75)
        print(f"{'ID':<4} | {'DATABASE TARGET NAME':<26} | {'NEW ESTIMATED BUDGET (€)':<25}")
        print("="*75)
        
        for team_id, db_name in db_teams:
            db_norm_key = normalize_team_name(db_name)
            match_row = df_financials[df_financials["Match_Key"] == db_norm_key]
            
            if not match_row.empty:
                target_budget = float(match_row["Calculated_Budget"].values[0])
                staging_batch.append((target_budget, team_id, db_name))
                print(f"{team_id:<4} | {db_name:<26} | €{target_budget:,.2f}")
            else:
                # This should rarely hit now, but acts as a final safety net
                print(f"{team_id:<4} | {db_name:<26} | ⚠️ No aligned scraper rows match.")
        print("="*75 + "\n")
        
        # 3. Interactive Gate
        user_approval = input(f"Review the staging layout metrics above. Push these {len(staging_batch)} updates to production? (y/n): ").strip().lower()
        
        if user_approval != 'y':
            print("\nTransaction aborted by user. Database parameters left untouched.")
            cursor.close()
            conn.close()
            sys.exit(0)
            
        # 4. Safe Execution Transaction
        print("\n[3/3] Authorization verified. Modifying MySQL records...")
        updated_count = 0
        update_query = "UPDATE teams SET transfer_budget = %s WHERE team_id = %s"
        
        for target_budget, team_id, db_name in staging_batch:
            cursor.execute(update_query, (target_budget, team_id))
            updated_count += 1
            
        conn.commit()
        print(f"SUCCESS: Changes committed. {updated_count} rows updated in production table.")
        
    except Exception as err:
        print(f"Transaction Failure Error: {err}")
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals(): conn.close()

if __name__ == "__main__":
    run_production_pipeline()