import os
import numpy as np
import pandas as pd
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv
from sklearn.preprocessing import StandardScaler

load_dotenv()

def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv('DB_HOST'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        database=os.getenv('DB_NAME')
    )

def run_production_team_styles():
    print("=" * 115)
    print(" EXECUTING PRODUCTION ANCHOR-BASED TACTICAL STYLE INGESTION ENGINE")
    print("=" * 115)
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # 1. Fetch live metrics from engineered table
        query = """
            SELECT team_id, possession_pct, shots_per_90, goals_per_shot, ppda_metric 
            FROM seasonal_team_stats;
        """
        df = pd.read_sql(query, conn)
        
        if df.empty:
            print(" No team statistics found to classify.")
            return
            
        cursor.execute("SELECT team_id, team_name FROM teams;")
        team_names = {t['team_id']: t['team_name'] for t in cursor.fetchall()}
        
        feature_cols = ['possession_pct', 'shots_per_90', 'goals_per_shot', 'ppda_metric']
        X = df[feature_cols].values
        
        # 2. Fit the scaler on our live data space
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        
        # 3. DEFINE SIMPLIFIED TAXONOMY ANCHORS
        # Format: [possession_pct, shots_per_90, goals_per_shot, ppda_metric]
        tactical_anchors = {
            "Possession":  [60.0, 15.0, 0.10, 9.2],
            "Pressing":    [53.0, 14.5, 0.10, 9.8],
            "Vertical":    [55.0, 16.0, 0.13, 11.0],
            "Controlled":  [52.0, 11.5, 0.09, 11.2],
            "Wing Play":   [48.0, 12.0, 0.09, 11.8],
            "Counter":     [44.0, 10.5, 0.11, 12.8],
            "Low Block":   [39.0, 9.0,  0.08, 14.5]
        }
        
        # Standardize the anchor coordinates into the exact same scaled feature space
        scaled_anchors = {}
        for name, metrics in tactical_anchors.items():
            scaled_anchors[name] = scaler.transform([metrics])[0]
            
        update_payloads = []
        print(f"\n  {'Team Name':<22} | Clean Style Assignment")
        print("  " + "-" * 50)
        
        # 4. DISTANCE-BASED ML MAPPING (Euclidean Minimum Vector)
        for idx, row in df.iterrows():
            team_id = int(row['team_id'])
            t_name = team_names.get(team_id, f"ID: {team_id}")
            x_vec = X_scaled[idx]
            
            closest_style = None
            min_distance = float('inf')
            
            for style_name, anchor_vec in scaled_anchors.items():
                dist = np.linalg.norm(x_vec - anchor_vec)
                if dist < min_distance:
                    min_distance = dist
                    closest_style = style_name
            
            print(f"  {t_name:<22} | {closest_style}")
            update_payloads.append((closest_style, team_id))
            
        # 5. SURGICAL DATABASE UPDATE
        print(f"\nCommitting {len(update_payloads)} simplified style updates to 'teams' table...")
        cursor.execute("SET SQL_SAFE_UPDATES = 0;")
        
        update_query = "UPDATE teams SET style_of_play = %s WHERE team_id = %s;"
        cursor.executemany(update_query, update_payloads)
        
        cursor.execute("SET SQL_SAFE_UPDATES = 1;")
        conn.commit()
        
        print("\n" + "=" * 115)
        print(" SUCCESS: Clean, shortened team style classifications synchronized safely!")
        print("=" * 115 + "\n")
        
        cursor.close()
        conn.close()
        
    except Error as err:
        print(f"\nINGESTION ENGINE CRASHED:\n{err}\n")

if __name__ == "__main__":
    run_production_team_styles()