import os
import re
import json
import random
import mysql.connector
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="pandas")

class AdvancedScoutingEngine:
    def __init__(self):
        self.db_config = {
            "host": os.getenv("DB_HOST", "127.0.0.1"),
            "port": int(os.getenv("DB_PORT", 3306)),
            "user": os.getenv("DB_USER", "root"),
            "password": os.getenv("DB_PASSWORD"),
            "database": os.getenv("DB_NAME")
        }

    def _get_connection(self):
        return mysql.connector.connect(**self.db_config)

    def run_macro_club_audit(self, team_id):
        """
        ENGINE 1: Macro Club Health & Internal Depth Engine
        Evaluates club urgency based on performance metrics, scans internal roster depth 
        for positions/archetypes entering contract distress, and identifies external targets.
        """
        conn = self._get_connection()
        
        club_query = """
            SELECT team_name, transfer_budget, style_of_play, squad_success_metric 
            FROM teams WHERE team_id = %s
        """
        df_club = pd.read_sql(club_query, conn, params=(team_id,))
        if df_club.empty:
            print(f"❌ Team ID {team_id} not found.")
            conn.close()
            return
            
        club_meta = df_club.iloc[0]
        team_name = club_meta['team_name']
        budget = float(club_meta['transfer_budget'] or 0.0)
        success_metric = float(club_meta['squad_success_metric'] or 0.0)
        
        urgency_months = 12 if success_metric >= 75.0 else 24
        
        print("="*115)
        print(f"🕵️‍♂️ MACRO SQUAD HEALTH AUDIT: {team_name.upper()}")
        print(f"📊 Success Metric: {success_metric:.1f}/100 | Target Expiry Window: < {urgency_months} Months | Budget: €{budget:,.0f}")
        print("="*115)

        distressed_positions_query = """
            SELECT p.player_id, p.player_name, pp.position, tp.archetype_label, sa.contract_end_date,
                   TIMESTAMPDIFF(MONTH, CURDATE(), sa.contract_end_date) as months_left
            FROM squad_assignments sa
            JOIN players p ON sa.player_id = p.player_id
            JOIN player_positions pp ON p.player_id = pp.player_id AND pp.position_priority = 'Primary'
            LEFT JOIN tactical_profiles tp ON p.player_id = tp.player_id
            WHERE sa.team_id = %s AND TIMESTAMPDIFF(MONTH, CURDATE(), sa.contract_end_date) <= %s
        """
        df_distressed = pd.read_sql(distressed_positions_query, conn, params=(team_id, urgency_months))
        
        if df_distressed.empty:
            print(f"✅ Roster Stability High: No core positions face imminent contract distress within {urgency_months} months.")
            conn.close()
            return

        print(f"\n⚠️ Core Vulnerabilities Identified ({len(df_distressed)} players needing long-term replacement strategy):")
        
        for _, row in df_distressed.iterrows():
            pos = row['position']
            arch = row['archetype_label']
            print(f"   - {row['player_name']} ({pos} | {arch}) - {row['months_left']} months remaining on contract.")
            
            internal_clone_query = """
                SELECT p.player_name, p.age, sa.squad_role, tp.confidence
                FROM squad_assignments sa
                JOIN players p ON sa.player_id = p.player_id
                JOIN player_positions pp ON p.player_id = pp.player_id AND pp.position_priority = 'Primary'
                JOIN tactical_profiles tp ON p.player_id = tp.player_id
                WHERE sa.team_id = %s 
                  AND sa.player_id != %s
                  AND (pp.position = %s OR tp.archetype_label = %s)
                ORDER BY tp.confidence DESC
            """
            df_internal = pd.read_sql(internal_clone_query, conn, params=(team_id, row['player_id'], pos, arch))
            
            if not df_internal.empty:
                best_internal = df_internal.iloc[0]
                print(f"     💡 INTERNAL SOLUTION FOUND: {best_internal['player_name']} (Age {best_internal['age']}, Role: {best_internal['squad_role']}) matches profile requirements.")
            else:
                print(f"     🚨 NO INTERNAL CLONE DETECTED: External recruitment triggered for a {pos} ({arch}).")
                
                external_target_query = """
                    SELECT p.player_name, p.age, t.team_name as current_club, sa.market_value, sa.contract_end_date,
                           TIMESTAMPDIFF(MONTH, CURDATE(), sa.contract_end_date) as ext_months_left
                    FROM players p
                    JOIN squad_assignments sa ON p.player_id = sa.player_id
                    JOIN teams t ON sa.team_id = t.team_id
                    JOIN player_positions pp ON p.player_id = pp.player_id AND pp.position_priority = 'Primary'
                    JOIN tactical_profiles tp ON p.player_id = tp.player_id
                    WHERE sa.team_id != %s
                      AND (pp.position = %s OR tp.archetype_label = %s)
                      AND sa.market_value <= %s
                      AND sa.market_value > 0
                    ORDER BY ext_months_left ASC, sa.market_value DESC
                    LIMIT 3
                """
                df_targets = pd.read_sql(external_target_query, conn, params=(team_id, pos, arch, budget))
                
                if not df_targets.empty:
                    print(f"     🎯 Top Affordable External Market Options:")
                    for _, ext_row in df_targets.iterrows():
                        print(f"        * {ext_row['player_name']} ({ext_row['current_club']}) | Age: {ext_row['age']} | Value: €{ext_row['market_value']:,.0f} | Contract: {ext_row['ext_months_left']} mo left")
        print("="*115 + "\n")
        conn.close()

    def generate_xai_payload(self, row, buyer_name, target_archetype, buyer_budget):
        """
        XAI SERIALIZATION ENGINE
        Translates mathematical feature attributions of the suit_score into 
        a structured JSON schema ready to be consumed by a local or cloud LLM agent.
        """
        c_arch = float(row['base_confidence'])
        delta_sys = float(row['System_Fit_Score'])
        rho_fin = 1.0 - (float(row['market_value']) / buyer_budget) if buyer_budget > 0 else 0.0
        rho_fin = max(0.0, min(1.0, rho_fin))

        payload = {
            "rec_metadata": {
                "searching_club": buyer_name,
                "requested_archetype": target_archetype,
                "club_financial_limit_euros": buyer_budget
            },
            "candidate_profile": {
                "player_id": int(row['player_id']),
                "name": row['player_name'],
                "current_club": row['current_club'],
                "age": int(row['age']),
                "position": row['position'],
                "market_value_euros": float(row['market_value'])
            },
            "explainable_ai_matrix": {
                "composite_suit_score": float(row['suit_score']),
                "weights_applied": {"archetype_weight": 0.50, "system_fit_weight": 0.30, "financial_leverage_weight": 0.20},
                "feature_attributions": [
                    {
                        "feature_name": "Tactical Archetype Match (C_arch)",
                        "raw_feature_value": round(c_arch, 3),
                        "weighted_score_impact": round(c_arch * 0.50 * 100, 2),
                        "directional_influence": "Positive"
                    },
                    {
                        "feature_name": "System and Playstyle Compatibility (Delta_sys)",
                        "raw_feature_value": round(delta_sys, 3),
                        "weighted_score_impact": round(delta_sys * 0.30 * 100, 2),
                        "directional_influence": "Positive" if delta_sys >= 0.8 else "Negative/Risk"
                    },
                    {
                        "feature_name": "Financial Efficiency & Budget Headroom (Rho_fin)",
                        "raw_feature_value": round(rho_fin, 3),
                        "weighted_score_impact": round(rho_fin * 0.20 * 100, 2),
                        "directional_influence": "Positive" if row['market_value'] <= (buyer_budget * 0.6) else "Warning"
                    }
                ]
            }
        }
        return json.dumps(payload, indent=2)

    def get_tactical_recommendations(self, search_team_id, target_archetype, position_filter=None):
        """
        ENGINE 2: Profile-Based Tactical & Archetype Search Engine (Enhanced with suit_score & XAI)
        Searches the DB for an archetype, modifies for style alignment, computes composite 
        suit_score, and prepares structural payloads for the XAI reporting layer.
        """
        conn = self._get_connection()
        
        team_query = "SELECT team_name, transfer_budget, style_of_play FROM teams WHERE team_id = %s"
        df_team = pd.read_sql(team_query, conn, params=(search_team_id,))
        if df_team.empty:
            print(f"❌ Searching Team ID {search_team_id} not found.")
            conn.close()
            return
            
        team_meta = df_team.iloc[0]
        buyer_name = team_meta['team_name']
        buyer_budget = float(team_meta['transfer_budget'] or 0.0)
        buyer_style = team_meta['style_of_play']

        query = """
            SELECT 
                p.player_id, p.player_name, p.age, pp.position, tp.confidence as base_confidence,
                sa.market_value, sa.contract_end_date, t.team_name as current_club, t.style_of_play as current_club_style
            FROM players p
            JOIN squad_assignments sa ON p.player_id = sa.player_id
            JOIN teams t ON sa.team_id = t.team_id
            JOIN tactical_profiles tp ON p.player_id = tp.player_id
            JOIN player_positions pp ON p.player_id = pp.player_id AND pp.position_priority = 'Primary'
            WHERE tp.archetype_label = %s
              AND sa.team_id != %s
              AND sa.market_value <= %s
        """
        
        params = [target_archetype, search_team_id, buyer_budget]
        if position_filter:
            query += " AND pp.position = %s"
            params.append(position_filter)
            
        df_candidates = pd.read_sql(query, conn, params=tuple(params))
        conn.close()

        if df_candidates.empty:
            print(f"ℹ️ No affordable candidates matching the archetype '{target_archetype}' found.")
            return

        # 1. Calculate Playstyle Compatibility Modifiers (Delta_sys)
        def evaluate_system_fit(row):
            score = float(row['base_confidence'])
            if row['current_club_style'] == buyer_style:
                score += 0.10
            elif buyer_style == "Tiki-Taka / Possession-Based" and row['current_club_style'] == "Counter-Attacking / Low Block":
                score -= 0.15 
            elif buyer_style == "Gegenpressing / High Intensity" and row['current_club_style'] == "Wing Play / Direct":
                score += 0.05
            return min(1.0, max(0.0, score))

        df_candidates['System_Fit_Score'] = df_candidates.apply(evaluate_system_fit, axis=1)

        # 2. Compute Ultimate Weighted Suitability Prediction Confidence Score (suit_score)
        def calculate_suitability(row):
            c_arch = float(row['base_confidence'])
            delta_sys = float(row['System_Fit_Score'])
            
            # Financial Efficiency component (normalized headroom)
            rho_fin = 1.0 - (float(row['market_value']) / buyer_budget) if buyer_budget > 0 else 0.0
            rho_fin = max(0.0, min(1.0, rho_fin))
            
            # Apply linear configuration weights (0.50 / 0.30 / 0.20)
            suit_score = (0.50 * c_arch) + (0.30 * delta_sys) + (0.20 * rho_fin)
            return round(suit_score * 100, 1)

        df_candidates['suit_score'] = df_candidates.apply(calculate_suitability, axis=1)
        df_candidates = df_candidates.sort_values(by='suit_score', ascending=False)

        print("="*120)
        print(f"🎯 ARCHETYPE TARGET SEARCH REPORT: {buyer_name.upper()}")
        print(f"🔍 Targeted Role: {target_archetype} | Tactical Identity: {buyer_style} | Cap: €{buyer_budget:,.0f}")
        print("="*120)
        print(f"{'PLAYER':<22} | {'AGE':<3} | {'POS':<4} | {'CURRENT CLUB':<18} | {'SYSTEM FIT':<10} | {'SUITABILITY SCORE (SUIT_SCORE)'}")
        print("-" * 120)
        
        top_candidates = df_candidates.head(5)
        for _, row in top_candidates.iterrows():
            print(f"{str(row['player_name'])[:22]:<22} | "
                  f"{int(row['age']):<3} | "
                  f"{str(row['position']):<4} | "
                  f"{str(row['current_club'])[:18]:<18} | "
                  f"{row['System_Fit_Score']*100:<9.1f}% | "
                  f"⭐️ {row['suit_score']:.1f} / 100")
        print("="*120 + "\n")

        # Return a dictionary of candidates paired with their ready-to-use JSON XAI payloads
        xai_outputs = {}
        for _, row in top_candidates.iterrows():
            xai_outputs[row['player_name']] = self.generate_xai_payload(row, buyer_name, target_archetype, buyer_budget)
            
        return xai_outputs

if __name__ == "__main__":
    engine = AdvancedScoutingEngine()
    
    # Run Macro Audit Strategy
    engine.run_macro_club_audit(team_id=1)
    
    # Run Profile / Archetype Search and capture the XAI Serializer payloads
    xai_data = engine.get_tactical_recommendations(search_team_id=1, target_archetype="Playmaker")
    
    # Quick terminal verification of the payload format for our first candidate
    if xai_data:
        first_candidate = list(xai_data.keys())[0]
        print(f"📦 PREVIEWING GENERATED XAI JSON STREAM FOR: {first_candidate.upper()}")
        print(xai_data[first_candidate])