import os
import json
import mysql.connector
import pandas as pd
from dotenv import load_dotenv
import warnings

warnings.filterwarnings("ignore", category=UserWarning, module="pandas")
load_dotenv()

class AdvancedScoutingEngine:
    def __init__(self):
        self.db_config = {
            "host": os.getenv("DB_HOST", "127.0.0.1"),
            "port": int(os.getenv("DB_PORT", 3306)),
            "user": os.getenv("DB_USER", "root"),
            "password": os.getenv("DB_PASSWORD"),
            "database": os.getenv("DB_NAME")
        }

        self.archetype_mapping = {
            'Traditional GK': 'player_gk_stats', 'Shot Stopper': 'player_gk_stats',
            'Ball Playing CB': 'player_def_mid_stats', 'Wing Back': 'player_def_mid_stats',
            'Ball Winner': 'player_def_mid_stats', 'Playmaker': 'player_def_mid_stats',
            'Winger': 'player_att_stats', 'Poacher': 'player_att_stats',
            'False Nine': 'player_att_stats', 'Inside Forward': 'player_att_stats'
        }

        self.table_columns = {
            'player_gk_stats': ['goals_against', 'saves', 'save_pct', 'clean_sheets'],
            'player_def_mid_stats': ['tackles_won', 'interceptions', 'blocks', 'passes_completed', 'progressive_passes', 'assists', 'aerials_won_pct'],
            'player_att_stats': ['goals', 'assists', 'shots_per_90', 'shots_on_target_pct']
        }

    def _get_connection(self):
        return mysql.connector.connect(**self.db_config)

    def _get_target_table_and_cols(self, arch, pos):
        """Intelligent routing: Tries archetype first, falls back to position to prevent zero-stat bugs."""
        if arch and arch in self.archetype_mapping:
            target_table = self.archetype_mapping[arch]
        else:
            pos_upper = str(pos).upper()
            if pos_upper == 'GK': target_table = 'player_gk_stats'
            elif pos_upper in ['ST', 'LW', 'RW', 'CF', 'CAM', 'LM', 'RM']: target_table = 'player_att_stats'
            else: target_table = 'player_def_mid_stats'
            
        return target_table, self.table_columns[target_table]

    def get_all_teams(self):
        conn = self._get_connection()
        try:
            df = pd.read_sql("SELECT team_id, team_name FROM teams ORDER BY team_name", conn)
            return df.to_dict(orient='records')
        finally:
            conn.close()

    def _scale_radar(self, col, val):
        """Unified radar normalization logic."""
        if col in ['saves']: return min(val/120*100, 100)
        elif col in ['goals_against']: return min(val/50*100, 100)
        elif col in ['clean_sheets', 'assists']: return min(val/15*100, 100)
        elif col in ['tackles_won', 'interceptions']: return min(val/50*100, 100)
        elif col in ['blocks']: return min(val/30*100, 100)
        elif col in ['passes_completed']: return min(val/2000*100, 100)
        elif col in ['progressive_passes']: return min(val/100*100, 100)
        elif col in ['goals']: return min(val/25*100, 100)
        elif col in ['shots_per_90']: return min(val/5*100, 100)
        else: return min(val, 100)

    # --- ROSTER & PROFILE LOGIC ---
    def get_team_roster(self, team_id):
        conn = self._get_connection()
        query = """
            SELECT p.player_id, p.player_name, pp.position, tp.archetype_label, sa.squad_role, tp.confidence
            FROM squad_assignments sa
            JOIN players p ON sa.player_id = p.player_id
            JOIN player_positions pp ON p.player_id = pp.player_id AND pp.position_priority = 'Primary'
            LEFT JOIN tactical_profiles tp ON p.player_id = tp.player_id
            WHERE sa.team_id = %s
        """
        df = pd.read_sql(query, conn, params=(team_id,))
        conn.close()
        
        if df.empty: return []
        
        # FIX: Drop duplicates based on the highest confidence archetype
        df['confidence'] = df['confidence'].fillna(0)
        df = df.sort_values('confidence', ascending=False).drop_duplicates(subset=['player_id'])
        df = df.sort_values(by=['position', 'player_name'])
        
        return df.to_dict(orient='records')

    def get_player_profile(self, player_id):
        conn = self._get_connection()
        # FIX: Enforce LIMIT 1 to prevent multiple archetype duplications breaking the query
        base_query = """
            SELECT p.player_id, p.player_name, p.age, pp.position, tp.archetype_label, tp.confidence, sa.market_value, t.team_name as current_club
            FROM players p
            JOIN squad_assignments sa ON p.player_id = p.player_id
            JOIN teams t ON sa.team_id = t.team_id
            JOIN player_positions pp ON p.player_id = pp.player_id AND pp.position_priority = 'Primary'
            LEFT JOIN tactical_profiles tp ON p.player_id = tp.player_id
            WHERE p.player_id = %s
            ORDER BY tp.confidence DESC LIMIT 1
        """
        df_base = pd.read_sql(base_query, conn, params=(player_id,))
        if df_base.empty:
            conn.close()
            return None
            
        row = df_base.iloc[0]
        arch, pos = row['archetype_label'], row['position']
        
        # FIX: Intelligent fallback routing
        target_table, target_cols = self._get_target_table_and_cols(arch, pos)
        sql_cols = ", ".join(target_cols)
        
        stats_query = f"SELECT {sql_cols} FROM {target_table} WHERE player_id = %s"
        df_stats = pd.read_sql(stats_query, conn, params=(player_id,)).fillna(0)
        conn.close()

        raw_stats = {col: float(df_stats.iloc[0][col]) if not df_stats.empty else 0.0 for col in target_cols}
        labels = [col.replace('_', ' ').title() for col in target_cols]
        radar_data = [self._scale_radar(col, raw_stats[col]) for col in target_cols]

        return json.dumps({
            "candidate_profile": { "player_id": int(row['player_id']), "name": row['player_name'], "current_club": row['current_club'], "age": int(row['age']), "position": row['position'], "market_value_euros": float(row['market_value']) },
            "archetype": arch,
            "confidence": float(row['confidence']) if pd.notna(row['confidence']) else 0.0,
            "raw_performance": raw_stats,
            "radar_metrics": { "labels": labels, "data": [round(x) for x in radar_data] }
        })

    # --- MACRO AUDIT ---
    def run_macro_club_audit(self, team_id):
        conn = self._get_connection()
        try:
            club_query = "SELECT team_name, transfer_budget, squad_success_metric FROM teams WHERE team_id = %s"
            df_club = pd.read_sql(club_query, conn, params=(team_id,))
            if df_club.empty: return {"error": "Team not found"}
            
            meta = df_club.iloc[0]
            budget = float(meta['transfer_budget'])
            urgency = 12 if meta['squad_success_metric'] >= 75 else 24
            
            audit_query = """
                SELECT p.player_id, p.player_name, pp.position, tp.archetype_label, TIMESTAMPDIFF(MONTH, CURDATE(), sa.contract_end_date) as months_left
                FROM squad_assignments sa JOIN players p ON sa.player_id = p.player_id JOIN player_positions pp ON p.player_id = pp.player_id AND pp.position_priority = 'Primary' LEFT JOIN tactical_profiles tp ON p.player_id = tp.player_id
                WHERE sa.team_id = %s AND sa.contract_end_date <= DATE_ADD(CURDATE(), INTERVAL %s MONTH)
            """
            df_audit = pd.read_sql(audit_query, conn, params=(team_id, urgency))
            df_audit = df_audit.drop_duplicates(subset=['player_id']) # FIX: Prevent duplicate alerts
            
            vulnerabilities = []
            for _, row in df_audit.iterrows():
                pos, arch = row['position'], row['archetype_label']
                vuln_data = {"distressed_player": row['player_name'], "position": pos, "archetype": arch, "months_left": int(row['months_left']), "internal_solution": None, "external_targets": []}
                
                internal_q = """
                    SELECT p.player_name, p.age, sa.squad_role FROM squad_assignments sa JOIN players p ON sa.player_id = p.player_id JOIN player_positions pp ON p.player_id = pp.player_id AND pp.position_priority = 'Primary' LEFT JOIN tactical_profiles tp ON p.player_id = tp.player_id
                    WHERE sa.team_id = %s AND sa.player_id != %s AND (pp.position = %s OR tp.archetype_label = %s) ORDER BY tp.confidence DESC LIMIT 1
                """
                df_internal = pd.read_sql(internal_q, conn, params=(team_id, row['player_id'], pos, arch))
                if not df_internal.empty: vuln_data["internal_solution"] = {"name": df_internal.iloc[0]['player_name'], "age": int(df_internal.iloc[0]['age']), "role": df_internal.iloc[0]['squad_role']}
                else:
                    ext_q = """
                        SELECT p.player_name, p.age, t.team_name as current_club, sa.market_value FROM players p JOIN squad_assignments sa ON p.player_id = sa.player_id JOIN teams t ON sa.team_id = t.team_id JOIN player_positions pp ON p.player_id = pp.player_id AND pp.position_priority = 'Primary' LEFT JOIN tactical_profiles tp ON p.player_id = tp.player_id
                        WHERE sa.team_id != %s AND (pp.position = %s OR tp.archetype_label = %s) AND sa.market_value <= %s ORDER BY sa.market_value DESC LIMIT 3
                    """
                    df_ext = pd.read_sql(ext_q, conn, params=(team_id, pos, arch, budget))
                    for _, ext_row in df_ext.iterrows(): vuln_data["external_targets"].append({"name": ext_row['player_name'], "club": ext_row['current_club'], "age": int(ext_row['age']), "value": float(ext_row['market_value'])})
                vulnerabilities.append(vuln_data)
                
            return { "team_name": meta['team_name'], "budget": budget, "success_metric": float(meta['squad_success_metric']), "urgency_months": urgency, "vulnerabilities": vulnerabilities }
        finally: conn.close()

    # --- TACTICAL RECOMMENDATIONS ---
    def get_tactical_recommendations(self, search_team_id, target_archetype):
        conn = self._get_connection()
        team_query = "SELECT team_name, transfer_budget, style_of_play FROM teams WHERE team_id = %s"
        df_team = pd.read_sql(team_query, conn, params=(search_team_id,))
        if df_team.empty:
            conn.close()
            return None
        
        buyer_name, buyer_budget, buyer_style = df_team.iloc[0]['team_name'], float(df_team.iloc[0]['transfer_budget'] or 0.0), df_team.iloc[0]['style_of_play']

        target_table, target_cols = self._get_target_table_and_cols(target_archetype, None)
        sql_cols = ", ".join([f"s.{col}" for col in target_cols])

        query = f"""
            SELECT p.player_id, p.player_name, p.age, pp.position, tp.confidence as base_confidence, sa.market_value, t.team_name as current_club, t.style_of_play as current_club_style,
                   {sql_cols}
            FROM players p 
            JOIN squad_assignments sa ON p.player_id = sa.player_id 
            JOIN teams t ON sa.team_id = t.team_id 
            JOIN tactical_profiles tp ON p.player_id = tp.player_id 
            JOIN player_positions pp ON p.player_id = pp.player_id AND pp.position_priority = 'Primary'
            LEFT JOIN {target_table} s ON p.player_id = s.player_id 
            WHERE tp.archetype_label = %s AND sa.team_id != %s AND sa.market_value <= %s
        """
        
        params = [target_archetype, search_team_id, buyer_budget]
        df_candidates = pd.read_sql(query, conn, params=tuple(params))
        df_candidates = df_candidates.drop_duplicates(subset=['player_id']).fillna(0) # FIX: Drop duplicates here as well
        conn.close()

        if df_candidates.empty: return None

        df_candidates['System_Fit_Score'] = df_candidates.apply(lambda r: min(1.0, float(r['base_confidence']) + (0.10 if r['current_club_style'] == buyer_style else 0.0)), axis=1)
        df_candidates['suit_score'] = df_candidates.apply(lambda r: round(((0.50 * float(r['base_confidence'])) + (0.30 * float(r['System_Fit_Score'])) + (0.20 * max(0.0, min(1.0, 1.0 - (float(r['market_value']) / buyer_budget) if buyer_budget > 0 else 0.0)))) * 100, 1), axis=1)
        df_candidates = df_candidates.sort_values(by='suit_score', ascending=False).head(5)
        
        return {row['player_name']: self.generate_xai_payload(row, buyer_name, target_archetype, buyer_budget, target_table, target_cols) for _, row in df_candidates.iterrows()}

    def generate_xai_payload(self, row, buyer_name, target_archetype, buyer_budget, target_table, target_cols):
        raw_stats = {col: float(row[col]) for col in target_cols}
        labels = [col.replace('_', ' ').title() for col in target_cols]
        radar_data = [self._scale_radar(col, raw_stats[col]) for col in target_cols]

        return json.dumps({
            "rec_metadata": { "searching_club": buyer_name, "requested_archetype": target_archetype },
            "candidate_profile": { "player_id": int(row['player_id']), "name": row['player_name'], "current_club": row['current_club'], "age": int(row['age']), "position": row['position'], "market_value_euros": float(row['market_value']) },
            "raw_performance": raw_stats,
            "radar_metrics": { "labels": labels, "data": [round(x) for x in radar_data] },
            "explainable_ai_matrix": { 
                "composite_suit_score": float(row['suit_score']),
                "feature_attributions": [
                    { "feature_name": "Archetype Match", "raw_feature_value": float(row['base_confidence']) },
                    { "feature_name": "System Fit", "raw_feature_value": float(row['System_Fit_Score']) },
                    { "feature_name": "Financial Efficiency", "raw_feature_value": max(0.0, min(1.0, 1.0 - (float(row['market_value']) / buyer_budget) if buyer_budget > 0 else 0.0)) }
                ]
            }
        })