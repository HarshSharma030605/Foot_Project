import os
import pandas as pd
import numpy as np
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
    if val is None: return default
    try: return int(val)
    except: return default

def safe_float(val, default=0.0):
    if val is None: return default
    try: return float(val)
    except: return default

def compute_sigmoid_confidence(metrics_dict, threshold_dict, mean_dict, std_dict):
    """
    Calculates a multi-variable confidence coefficient using a Sigmoid curve 
    over Z-Scores relative to the population distribution.
    Includes a variance floor to prevent unpopulated column metrics from forcing 1.0 clips.
    """
    scores = []
    for key in metrics_dict.keys():
        val = metrics_dict[key]
        thresh = threshold_dict[key]
        mu = mean_dict[key]
        
        # Core fix: Establish an explicit variance floor if the std dev is zero or unpopulated
        sigma = std_dict[key]
        if pd.isna(sigma) or sigma <= 0.0:
            sigma = max(1.0, thresh * 0.5) # Use 50% of the threshold baseline as a proxy variation
        
        # Compute Z-score relative to the threshold boundary line
        z_score = (val - thresh) / sigma
        
        # Mapped smoothly into a realistic [0.55, 0.98] distribution curve
        sigmoid_score = 0.55 + (0.43 / (1.0 + np.exp(-z_score * 0.7)))
        scores.append(sigmoid_score)
        
    return float(np.mean(scores)) if scores else 0.70

def execute_all_features_multi_label_pipeline():
    print("=" * 125)
    print(" PURE DB MULTI-LABEL ARCHETYPE ENGINE: RUNNING FULL SIGMOID-Z INGESTION PASS")
    print("=" * 125)
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # ---------------------------------------------------------------------------------
        # STEP 1: PRE-CALCULATE POPULATION DISTRIBUTION METRICS (MEAN & STD DEV)
        # ---------------------------------------------------------------------------------
        print("Synthesizing population mean and standard deviation matrices from MySQL...")
        
        threshold_dict = {}
        mean_dict = {}
        std_dict = {}

        # Defenders & Midfielders
        cursor.execute("""
            SELECT tackles_won, interceptions, blocks, passes_completed, 
                   progressive_passes, assists, aerials_won_pct 
            FROM player_def_mid_stats;
        """)
        dm_all = cursor.fetchall()
        if dm_all:
            df_dm = pd.DataFrame(dm_all).astype(float)
            threshold_dict.update({
                'tackles_won': df_dm['tackles_won'].quantile(0.75),
                'interceptions': df_dm['interceptions'].quantile(0.75),
                'blocks': df_dm['blocks'].quantile(0.75),
                'passes_completed': df_dm['passes_completed'].quantile(0.75),
                'progressive_passes': df_dm['progressive_passes'].quantile(0.75),
                'assists_dm': df_dm['assists'].quantile(0.75),
                'aerials_won_pct': df_dm['aerials_won_pct'].quantile(0.75)
            })
            for col in df_dm.columns:
                key_name = 'assists_dm' if col == 'assists' else col
                mean_dict[key_name] = df_dm[col].mean()
                std_dict[key_name] = df_dm[col].std()
        else:
            for k in ['tackles_won', 'interceptions', 'blocks', 'passes_completed', 'progressive_passes', 'assists_dm', 'aerials_won_pct']:
                threshold_dict[k], mean_dict[k], std_dict[k] = 15, 10, 5, 500, 40, 1, 45.0

        # Attackers & Forwards
        cursor.execute("SELECT goals, assists, shots_per_90, shots_on_target_pct, goals_per_shot FROM player_att_stats;")
        att_all = cursor.fetchall()
        if att_all:
            df_att = pd.DataFrame(att_all).astype(float)
            threshold_dict.update({
                'goals': df_att['goals'].quantile(0.75),
                'assists_att': df_att['assists'].quantile(0.75),
                'shots_per_90': df_att['shots_per_90'].quantile(0.75),
                'shots_on_target_pct': df_att['shots_on_target_pct'].quantile(0.75),
                'goals_per_shot': 0.15
            })
            for col in df_att.columns:
                key_name = 'assists_att' if col == 'assists' else col
                mean_dict[key_name] = df_att[col].mean()
                std_dict[key_name] = df_att[col].std()
        else:
            for k in ['goals', 'assists_att', 'shots_per_90', 'shots_on_target_pct', 'goals_per_shot']:
                threshold_dict[k], mean_dict[k], std_dict[k] = 3, 2, 1.0, 30.0, 0.08

        # Goalkeepers
        cursor.execute("SELECT goals_against, saves, save_pct, clean_sheets FROM player_gk_stats;")
        gk_all = cursor.fetchall()
        if gk_all:
            df_gk = pd.DataFrame(gk_all).astype(float)
            threshold_dict.update({
                'goals_against': 35.0,
                'saves': 75.0,
                'save_pct_stopper': 72.0,
                'save_pct_sweeper': 70.0,
                'clean_sheets': 8.0
            })
            for col in df_gk.columns:
                mean_dict[col] = df_gk[col].mean()
                std_dict[col] = df_gk[col].std()
                
            mean_dict['save_pct_stopper'] = mean_dict['save_pct']
            mean_dict['save_pct_sweeper'] = mean_dict['save_pct']
            std_dict['save_pct_stopper'] = std_dict['save_pct']
            std_dict['save_pct_sweeper'] = std_dict['save_pct']
        else:
            for k in ['goals_against', 'saves', 'save_pct_stopper', 'save_pct_sweeper', 'clean_sheets']:
                threshold_dict[k], mean_dict[k], std_dict[k] = 30, 60, 70.0, 70.0, 5

        # Cache explicit threshold limits
        tkl_75 = threshold_dict['tackles_won']
        int_75 = threshold_dict['interceptions']
        blk_75 = threshold_dict['blocks']
        pass_75 = threshold_dict['passes_completed']
        prog_75 = threshold_dict['progressive_passes']
        ast_dm_75 = threshold_dict['assists_dm']
        
        goals_75 = threshold_dict['goals']
        ast_att_75 = threshold_dict['assists_att']
        shots_75 = threshold_dict['shots_per_90']
        sot_75 = threshold_dict['shots_on_target_pct']

        payload_updates = []

        # ---------------------------------------------------------------------------------
        # STEP 2: EVALUATE GOALKEEPERS (Strictly Hierarchical - Max 1 Label)
        # ---------------------------------------------------------------------------------
        print("\nEvaluating Goalkeepers with positional pruning rules...")
        gk_query = """
            SELECT gk.player_id, gk.goals_against, gk.saves, gk.save_pct, gk.clean_sheets,
                   COALESCE(dm.passes_completed, 0) as passes_completed
            FROM player_gk_stats gk
            LEFT JOIN player_def_mid_stats dm ON gk.player_id = dm.player_id;
        """
        cursor.execute(gk_query)
        for row in cursor.fetchall():
            pid = row['player_id']
            ga = safe_int(row['goals_against'])
            saves = safe_int(row['saves'])
            save_pct = safe_float(row['save_pct'])
            cs = safe_int(row['clean_sheets'])
            passes = safe_int(row['passes_completed'])
            
            assigned_archetype = None
            assigned_confidence = 0.60
            
            if saves >= 75 and ga >= 35:
                assigned_archetype = "Under Siege"
                assigned_confidence = compute_sigmoid_confidence(
                    {'saves': saves, 'goals_against': ga},
                    {'saves': 75.0, 'goals_against': 35.0},
                    {'saves': mean_dict['saves'], 'goals_against': mean_dict['goals_against']},
                    {'saves': std_dict['saves'], 'goals_against': std_dict['goals_against']}
                )
            elif save_pct >= 72.0:
                assigned_archetype = "Shot Stopper"
                assigned_confidence = compute_sigmoid_confidence(
                    {'save_pct': save_pct, 'saves': saves},
                    {'save_pct': 72.0, 'saves': mean_dict['saves']},
                    {'save_pct': mean_dict['save_pct_stopper'], 'saves': mean_dict['saves']},
                    {'save_pct': std_dict['save_pct_stopper'], 'saves': std_dict['saves']}
                )
            elif passes >= 400 or (save_pct >= 70.0 and cs >= 8):
                assigned_archetype = "Sweeper"
                assigned_confidence = compute_sigmoid_confidence(
                    {'save_pct': save_pct, 'clean_sheets': cs},
                    {'save_pct': 70.0, 'clean_sheets': 8.0},
                    {'save_pct': mean_dict['save_pct_sweeper'], 'clean_sheets': mean_dict['clean_sheets']},
                    {'save_pct': std_dict['save_pct_sweeper'], 'clean_sheets': std_dict['clean_sheets']}
                )
            else:
                assigned_archetype = "Traditional GK"
                assigned_confidence = 0.60
                
            payload_updates.append((pid, assigned_archetype, assigned_confidence))

        # ---------------------------------------------------------------------------------
        # STEP 3: EVALUATE DEFENDERS & MIDFIELDERS (Center-Back Pruning Enforced)
        # ---------------------------------------------------------------------------------
        print("Evaluating Defenders & Midfielders (Enforcing Central-Back Pruning)...")
        dm_query = """
            SELECT dm.player_id, pp.position, dm.tackles_won, dm.interceptions, dm.blocks, 
                   dm.passes_completed, dm.progressive_passes, dm.assists, dm.aerials_won_pct
            FROM player_def_mid_stats dm
            INNER JOIN player_positions pp ON dm.player_id = pp.player_id
            WHERE pp.position_priority = 'Primary';
        """
        cursor.execute(dm_query)
        for row in cursor.fetchall():
            pid = row['player_id']
            pos_str = str(row['position']).lower().strip()
            tkl = safe_int(row['tackles_won'])
            interc = safe_int(row['interceptions'])
            blks = safe_int(row['blocks'])
            p_comp = safe_int(row['passes_completed'])
            prog = safe_int(row['progressive_passes'])
            ast = safe_int(row['assists'])
            aer = safe_float(row['aerials_won_pct'])
            
            is_cb = "centre-back" in pos_str or "centre back" in pos_str or pos_str == "defender"
            matched = []
            
            if tkl >= tkl_75 or interc >= int_75 or blks >= blk_75:
                matched.append(("Ball Winner", compute_sigmoid_confidence(
                    {'tackles_won': tkl, 'interceptions': interc, 'blocks': blks, 'aerials_won_pct': aer},
                    {k: threshold_dict[k] for k in ['tackles_won', 'interceptions', 'blocks', 'aerials_won_pct']},
                    {k: mean_dict[k] for k in ['tackles_won', 'interceptions', 'blocks', 'aerials_won_pct']},
                    {k: std_dict[k] for k in ['tackles_won', 'interceptions', 'blocks', 'aerials_won_pct']}
                )))
                
            if is_cb:
                if p_comp >= pass_75 or prog >= prog_75 or tkl < tkl_75:
                    matched.append(("Ball Playing CB", compute_sigmoid_confidence(
                        {'passes_completed': p_comp, 'progressive_passes': prog},
                        {k: threshold_dict[k] for k in ['passes_completed', 'progressive_passes']},
                        {k: mean_dict[k] for k in ['passes_completed', 'progressive_passes']},
                        {k: std_dict[k] for k in ['passes_completed', 'progressive_passes']}
                    )))
            else:
                if ast >= ast_dm_75 and ("midfielder" in pos_str or "central" in pos_str):
                    matched.append(("Playmaker", compute_sigmoid_confidence(
                        {'assists_dm': ast, 'passes_completed': p_comp, 'progressive_passes': prog},
                        {'assists_dm': ast_dm_75, 'passes_completed': pass_75, 'progressive_passes': prog_75},
                        {'assists_dm': mean_dict['assists_dm'], 'passes_completed': mean_dict['passes_completed'], 'progressive_passes': mean_dict['progressive_passes']},
                        {'assists_dm': std_dict['assists_dm'], 'passes_completed': std_dict['passes_completed'], 'progressive_passes': std_dict['progressive_passes']}
                    )))
                if ("back" in pos_str or "wing" in pos_str or "full" in pos_str) and ast >= 2:
                    matched.append(("Wing Back", compute_sigmoid_confidence(
                        {'assists_dm': ast, 'progressive_passes': prog},
                        {'assists_dm': 2.0, 'progressive_passes': threshold_dict['progressive_passes']},
                        {'assists_dm': mean_dict['assists_dm'], 'progressive_passes': mean_dict['progressive_passes']},
                        {'assists_dm': std_dict['assists_dm'], 'progressive_passes': std_dict['progressive_passes']}
                    )))
            
            if is_cb:
                if not matched:
                    payload_updates.append((pid, "Box to Box", 0.60))
                else:
                    matched.sort(key=lambda x: x[1], reverse=True)
                    payload_updates.append((pid, matched[0][0], matched[0][1]))
            else:
                if not matched:
                    matched.append(("Box to Box", 0.60))
                for a, c in matched:
                    payload_updates.append((pid, a, c))

        # ---------------------------------------------------------------------------------
        # STEP 4: EVALUATE ATTACKERS & FORWARDS (Standard Multi-Label Mapping)
        # ---------------------------------------------------------------------------------
        print("Evaluating Attackers & Forwards...")
        att_query = """
            SELECT att.player_id, pp.position, att.goals, att.assists, 
                   att.shots_per_90, att.shots_on_target_pct, att.goals_per_shot
            FROM player_att_stats att
            INNER JOIN player_positions pp ON att.player_id = pp.player_id
            WHERE pp.position_priority = 'Primary';
        """
        cursor.execute(att_query)
        for row in cursor.fetchall():
            pid = row['player_id']
            pos_str = str(row['position']).lower().strip()
            goals = safe_int(row['goals'])
            ast = safe_int(row['assists'])
            shots = safe_float(row['shots_per_90'])
            sot = safe_float(row['shots_on_target_pct'])
            g_sh = safe_float(row['goals_per_shot'])
            
            matched = []
            if g_sh >= 0.15 or goals >= goals_75 or sot >= sot_75:
                matched.append(("Poacher", compute_sigmoid_confidence(
                    {'goals': goals, 'goals_per_shot': g_sh, 'shots_on_target_pct': sot},
                    {k: threshold_dict[k] for k in ['goals', 'goals_per_shot', 'shots_on_target_pct']},
                    {'goals': mean_dict['goals'], 'goals_per_shot': mean_dict['goals_per_shot'], 'shots_on_target_pct': mean_dict['shots_on_target_pct']},
                    {'goals': std_dict['goals'], 'goals_per_shot': std_dict['goals_per_shot'], 'shots_on_target_pct': std_dict['shots_on_target_pct']}
                )))
            if ("striker" in pos_str or "forward" in pos_str) and ast >= 3:
                matched.append(("False Nine", compute_sigmoid_confidence(
                    {'assists_att': ast, 'goals': goals},
                    {'assists_att': 3.0, 'goals': mean_dict['goals']},
                    {'assists_att': mean_dict['assists_att'], 'goals': mean_dict['goals']},
                    {'assists_att': std_dict['assists_att'], 'goals': std_dict['goals']}
                )))
            if shots >= shots_75 or sot >= sot_75:
                matched.append(("Inside Forward", compute_sigmoid_confidence(
                    {'shots_per_90': shots, 'shots_on_target_pct': sot, 'goals': goals},
                    {'shots_per_90': shots_75, 'shots_on_target_pct': sot_75, 'goals': mean_dict['goals']},
                    {'shots_per_90': mean_dict['shots_per_90'], 'shots_on_target_pct': mean_dict['shots_on_target_pct'], 'goals': mean_dict['goals']},
                    {'shots_per_90': std_dict['shots_per_90'], 'shots_on_target_pct': std_dict['shots_on_target_pct'], 'goals': std_dict['goals']}
                )))
            if ast >= ast_att_75 or "winger" in pos_str:
                matched.append(("Winger", compute_sigmoid_confidence(
                    {'assists_att': ast, 'shots_on_target_pct': sot},
                    {'assists_att': ast_att_75, 'shots_on_target_pct': threshold_dict['shots_on_target_pct']},
                    {'assists_att': mean_dict['assists_att'], 'shots_on_target_pct': mean_dict['shots_on_target_pct']},
                    {'assists_att': std_dict['assists_att'], 'shots_on_target_pct': mean_dict['shots_on_target_pct']}
                )))
            
            if not matched: 
                matched.append(("Winger", 0.60))
                
            for a, c in matched: payload_updates.append((pid, a, c))

        # ---------------------------------------------------------------------------------
        # STEP 5: ATOMIC COMMIT TO TACTICAL PROFILES
        # ---------------------------------------------------------------------------------
        if payload_updates:
            cursor.execute("SET SQL_SAFE_UPDATES = 0;")
            cursor.execute("TRUNCATE TABLE tactical_profiles;")
            
            upsert_query = "INSERT INTO tactical_profiles (player_id, archetype_label, confidence) VALUES (%s, %s, %s);"
            cursor.executemany(upsert_query, payload_updates)
            conn.commit()
            
            cursor.execute("SELECT AVG(confidence), MIN(confidence), MAX(confidence) FROM tactical_profiles WHERE confidence > 0.60;")
            stats = cursor.fetchone()
            
            print("\n" + "=" * 125)
            print(f"PRODUCTION SUCCESS: ARCHE-LABELS SECURED WITH HIGH-RESOLUTION VARIANCE GRADIENTS")
            print(f"   • Total Active Labeled Rows Instantiated: {len(payload_updates)} rows")
            print(f"   • Mean Contextual Specialist Confidence:  {stats['AVG(confidence)']:.2%}")
            print(f"   • Range Spread of Specialist Scores:     [{stats['MIN(confidence)']:.2%} to {stats['MAX(confidence)']:.2%}]")
            print("=" * 125 + "\n")
            
            cursor.execute("SET SQL_SAFE_UPDATES = 1;")
        
        cursor.close()
        conn.close()
    except Error as e:
        print(f"\nPIPELINE TRANSACTION OVERTURNED: {e}")

if __name__ == "__main__":
    execute_all_features_multi_label_pipeline()