import os
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

def determine_squad_role(jersey_number, position):
    """
    Applies the original position-based tracking matrix and jersey thresholds.
    """
    # 1. Injured / Deep Reserves Rule (High jersey numbers)
    if jersey_number and jersey_number > 35:
        return "Injured"
        
    # Standardize position text formatting for safe checking
    pos_clean = position.strip() if position else ""
    
    # 2. Starters (Heavy-workload defensive backbone roles)
    starter_positions = ['Goalkeeper', 'Centre-Back', 'Left-Back', 'Right-Back']
    if pos_clean in starter_positions:
        return "Starter"
        
    # 3. Substitutes (High-rotation / tactical energy roles)
    sub_positions = ['Attacking Midfielder', 'Secondary Striker', 'Right Winger', 'Left Winger']
    if pos_clean in sub_positions:
        return "Substitute"
        
    # 4. Default baseline fallback for general squad rotation players
    return "Squad Player"

def run_role_update_pipeline():
    print("=" * 85)
    print("        LAUNCHING LOCAL STRUCTURAL SQUAD ROLE INGESTION ENGINE          ")
    print("=" * 85)
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Pull player IDs, jersey numbers, and their primary positions from the DB
        print("Fetching current player allocations and positioning maps...")
        query = """
            SELECT sa.player_id, sa.team_id, sa.jersey_number, pp.position
            FROM squad_assignments sa
            LEFT JOIN player_positions pp ON sa.player_id = pp.player_id AND pp.position_priority = 'Primary'
        """
        cursor.execute(query)
        records = cursor.fetchall()
        print(f"Extracted {len(records)} player contexts from your database.")
        
        update_payloads = []
        for row in records:
            jersey = row['jersey_number']
            pos = row['position']
            player_id = row['player_id']
            team_id = row['team_id']
            
            # Calculate role using the local logic matrix
            assigned_role = determine_squad_role(jersey, pos)
            update_payloads.append((assigned_role, player_id, team_id))
            
        # Execute batch transactional update back into the assignments table
        print("Executing batch database updates...")
        update_query = """
            UPDATE squad_assignments 
            SET squad_role = %s 
            WHERE player_id = %s AND team_id = %s
        """
        cursor.executemany(update_query, update_payloads)
        conn.commit()
        
        print(f"Successfully mapped and saved {len(update_payloads)} roles to the database!")
        
        cursor.close()
        conn.close()
    except Error as e:
        print(f"Relational database transaction failed: {e}")
        
    print("\n" + "=" * 85)
    print(" SQUAD ROLE CLASSIFICATION RUN COMPLETE.")
    print("=" * 85 + "\n")

if __name__ == "__main__":
    run_role_update_pipeline()