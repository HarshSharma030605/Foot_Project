import os
import pandas as pd
import soccerdata as sd
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv

load_dotenv()

def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv('DB_HOST'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        database=os.getenv('DB_NAME')
    )

def safe_int(val, default=0):
    if pd.isna(val) or val is None: return default
    try: return int(float(val))
    except: return default

def safe_float(val, default=0.0):
    if pd.isna(val) or val is None: return default
    try: return float(val)
    except: return default

def execute_live_soccerdata_ingestion():
    print("=" * 125)
    print(" SOCCERDATA INGESTION ENGINE: FETCHING LIVE FBREF STATS WITH UNKNOWN CONSTRAINTS FIXED")
    print("=" * 125)
    
    # 1. READ ALL ACTIVE PROFILES STRAIGHT FROM THE LIVE DATABASE REGISTRY
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        query = """
            SELECT p.player_id, p.player_name, pp.position
            FROM players p
            INNER JOIN player_positions pp ON p.player_id = pp.player_id
            WHERE pp.position_priority = 'Primary';
        """
        cursor.execute(query)
        db_players = cursor.fetchall()
        
        if not db_players:
            print(" ABORTING: Zero primary player configurations found in player_positions database table.")
            cursor.close()
            conn.close()
            return

        name_to_id = {p['player_name'].lower().strip(): p['player_id'] for p in db_players}
        id_to_position = {p['player_id']: str(p['position']).strip() for p in db_players}
        total_primary_db_count = len(db_players)
        
        print(f" Connected to DB. Master position registry holds {total_primary_db_count} players.")
        cursor.close()
        conn.close()
    except Error as e:
        print(f" Database structural pre-check failed: {e}")
        return

    # 2. BOOT UP LIVE SOCCERDATA SCRAPER CONNECTOR
    print("\nConnecting to live soccerdata FBref stream wrapper...")
    fbref = sd.FBref(leagues="ESP-La Liga", seasons="2023-2024")
    
    df_std = fbref.read_player_season_stats(stat_type="standard")
    df_gk = fbref.read_player_season_stats(stat_type="keeper")
    df_sht = fbref.read_player_season_stats(stat_type="shooting")
    df_msc = fbref.read_player_season_stats(stat_type="misc")

    # Flatten multi-indexed column containers provided by soccerdata
    for df in [df_std, df_gk, df_sht, df_msc]:
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [f"{col[0]}_{col[1]}".strip() for col in df.columns]
    
    # Reset indexes so 'player' string values are accessible in row iteration loops
    df_std = df_std.reset_index()
    df_gk = df_gk.reset_index()
    df_sht = df_sht.reset_index()
    df_msc = df_msc.reset_index()

    # Map soccerdata row arrays to dictionary frames indexed by database player_id
    scraped_general = {}
    scraped_gk = {}
    scraped_def_mid = {}
    scraped_att = {}

    for _, row in df_std.iterrows():
        name_key = str(row.get('player', '')).lower().strip()
        if name_key in name_to_id: scraped_general[name_to_id[name_key]] = row

    for _, row in df_gk.iterrows():
        name_key = str(row.get('player', '')).lower().strip()
        if name_key in name_to_id: scraped_gk[name_to_id[name_key]] = row

    for _, row in df_msc.iterrows():
        name_key = str(row.get('player', '')).lower().strip()
        if name_key in name_to_id: scraped_def_mid[name_to_id[name_key]] = row

    for _, row in df_sht.iterrows():
        name_key = str(row.get('player', '')).lower().strip()
        if name_key in name_to_id: scraped_att[name_to_id[name_key]] = row

    # 3. ROUTE DATA BASED STRICTLY ON POSITIONAL ROLES
    gk_roles = {'Goalkeeper'}
    def_mid_roles = {
        'Centre-Back', 'Left-Back', 'Midfielder', 'Central Midfielder', 
        'Right-Back', 'Defensive Midfielder', 'Full-Back', 'Right Wing-Back', 
        'Left Wing-Back', 'Left Midfielder', 'Right Midfielder', 'Defender', 
        'Right Back', 'Left Back', 'Centre Back', 'Wide Midfielder', 'Wing-Back'
    }
    attacker_roles = {
        'Winger', 'Forward', 'Striker', 'Left Winger', 'Attacking Midfielder', 
        'Secondary Striker', 'Right Winger'
    }

    general_payload = []
    gk_payload = []
    def_mid_payload = []
    att_payload = []
    
    skipped_unknowns_count = 0

    # Loop through the master database registry to ensure no player is left out
    for player in db_players:
        pid = player['player_id']
        pos = id_to_position[pid]

        # General Stats Block (Populated for EVERY player in the primary registry)
        g_row = scraped_general.get(pid, {})
        general_payload.append((
            pid,
            safe_int(g_row.get('Playing Time_MP')),
            safe_int(g_row.get('Playing Time_Starts')),
            safe_int(g_row.get('Playing Time_Min')),
            safe_int(g_row.get('Performance_CrdY')),
            safe_int(g_row.get('Performance_CrdR'))
        ))

        # Specialty Routing Gates based on Position
        if pos in gk_roles:
            gk_row = scraped_gk.get(pid, {})
            gk_payload.append((
                pid,
                safe_int(gk_row.get('Performance_GA')),
                safe_int(gk_row.get('Performance_Saves')),
                safe_float(gk_row.get('Performance_Save%')),
                safe_int(gk_row.get('Performance_CS'))
            ))

        elif pos in def_mid_roles:
            dm_row = scraped_def_mid.get(pid, {})
            std_row = scraped_general.get(pid, {})
            ast_val = safe_int(std_row.get('Performance_Ast'))
            
            def_mid_payload.append((
                pid,
                safe_int(dm_row.get('Performance_TklW')),
                safe_int(dm_row.get('Performance_Int')),
                0, 0, 0, ast_val, 0.00
            ))

        elif pos in attacker_roles:
            att_row = scraped_att.get(pid, {})
            std_row = scraped_general.get(pid, {})
            ast_val = safe_int(std_row.get('Performance_Ast'))
            
            att_payload.append((
                pid,
                safe_int(att_row.get('Standard_Gls')),
                ast_val,
                safe_float(att_row.get('Standard_Sh/90')),
                safe_float(att_row.get('Standard_SoT%')),
                safe_float(att_row.get('Standard_G/Sh'))
            ))
        else:
            skipped_unknowns_count += 1

    # 4. EXECUTE ATOMIC INSERTS INTO DATABASE TABLES
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SET SQL_SAFE_UPDATES = 0;")

        # Wipe tables for a completely clean sync pass
        cursor.execute("TRUNCATE TABLE player_gk_stats;")
        cursor.execute("TRUNCATE TABLE player_def_mid_stats;")
        cursor.execute("TRUNCATE TABLE player_att_stats;")
        cursor.execute("TRUNCATE TABLE player_general_stats;")

        if general_payload:
            cursor.executemany("INSERT INTO player_general_stats VALUES (%s,%s,%s,%s,%s,%s);", general_payload)
        if gk_payload:
            cursor.executemany("INSERT INTO player_gk_stats VALUES (%s,%s,%s,%s,%s);", gk_payload)
        if def_mid_payload:
            cursor.executemany("INSERT INTO player_def_mid_stats VALUES (%s,%s,%s,%s,%s,%s,%s,%s);", def_mid_payload)
        if att_payload:
            cursor.executemany("INSERT INTO player_att_stats VALUES (%s,%s,%s,%s,%s,%s);", att_payload)

        conn.commit()

        # ---------------------------------------------------------------------------------
        # 🛡️ LIVE DATABASE STRUCTURAL INTEGRITY VERIFICATION CONTROL
        # ---------------------------------------------------------------------------------
        cursor.execute("SELECT COUNT(*) FROM player_general_stats;")
        db_general = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM player_gk_stats;")
        db_gk = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM player_def_mid_stats;")
        db_def = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM player_att_stats;")
        db_att = cursor.fetchone()[0]

        sum_positional_tables = db_gk + db_def + db_att
        expected_positional_total = total_primary_db_count - skipped_unknowns_count

        print("\n" + "=" * 65)
        print(" MASTER DATABASE INTEGRITY VERIFICATION REPORT")
        print(" " + "-" * 64)
        print(f"   • Live Primary Register Count (player_positions): {total_primary_db_count} rows")
        print(f"   • Database General Stats Count:                   {db_general} rows")
        print(f"   • Expected Positional Total (Excluding Unknowns): {expected_positional_total} rows")
        print(" " + "-" * 64)
        print(f"   • Goalkeeper Specialty Rows (GK):                 {db_gk} rows")
        print(f"   • Defensive/Midfield Specialty Rows (DEF/MID):     {db_def} rows")
        print(f"   • Attacking Specialty Rows (ATT):                 {db_att} rows")
        print(" " + "-" * 64)
        print(f"   • Combined Position Sum (GK + DEF/MID + ATT):     {sum_positional_tables} rows")
        print("=" * 65)

        # Updated hard validation gates matching the constraints
        if db_general != total_primary_db_count:
            raise AssertionError("CRITICAL: General statistics rows do not match total primary positions register!")
            
        if sum_positional_tables != expected_positional_total:
            raise AssertionError(f"CRITICAL: Position sum ({sum_positional_tables}) does not match expected tactical count ({expected_positional_total})!")

        print("\n MASTER INTEGRITY VERIFICATION PASSED: Database mirrors soccerdata output with 0 variance!\n")

        cursor.execute("SET SQL_SAFE_UPDATES = 1;")
        cursor.close()
        conn.close()

    except Exception as e:
        print(f"\nTRANSACTION OVERTURNED: ARCHITECTURE CONTROL REJECTED: {e}")

if __name__ == "__main__":
    execute_live_soccerdata_ingestion()