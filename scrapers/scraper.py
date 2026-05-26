import os
from dotenv import load_dotenv
import mysql.connector
from mysql.connector import Error
import pandas as pd
import requests

load_dotenv()

def connect_to_database(teams_list):
    connection = None

    try:
        connection = mysql.connector.connect(
            host = os.getenv('DB_HOST'),
            user = os.getenv('DB_USER'),
            password = os.getenv('DB_PASSWORD'),
            database = os.getenv('DB_NAME')
        )
        print('Connection Established')

        cursor = connection.cursor()
        query = """INSERT IGNORE INTO teams (team_id, team_name, manager, squad_size, style_of_play, squad_success_metric)
                   VALUES (%s, %s, %s, %s, %s, %s)"""
        cursor.executemany(query, teams_list)
        connection.commit()
        cursor.close()
        print(f'Data Inserted Successfully, inserted {cursor.rowcount} rows')

    except Error as e:
        print(f"Error in connecting: {e}")
    
    finally:
        if connection and connection.is_connected():
            connection.close()
            print('Connection Closed')



def get_la_liga_teams():
    # Crisp, curated seasonal data dictionary matching the current 2025–26 layout exactly
    raw_data = [
        ("Alavés", "Quique Sánchez Flores"), 
        ("Athletic Bilbao", "Ernesto Valverde"),
        ("Atlético Madrid", "Diego Simeone"), 
        ("Barcelona", "Hansi Flick"),
        ("Celta Vigo", "Claudio Giráldez"), 
        ("Elche", "Eder Sarabia"), 
        ("Espanyol", "Manolo González"),
        ("Getafe", "José Bordalás"), 
        ("Girona", "Míchel"),
        ("Levante", "Luís Castro"), 
        ("Mallorca", "Martín Demichelis"),
        ("Osasuna", "Alessio Lisci"), 
        ("Real Oviedo", "Guillermo Almada"),
        ("Rayo Vallecano", "Iñigo Pérez"), 
        ("Real Betis", "Manuel Pellegrini"),
        ("Real Madrid", "Álvaro Arbeloa"), 
        ("Real Sociedad", "Pellegrino Matarazzo"),
        ("Sevilla", "Luis García"), 
        ("Valencia", "Carlos Corberán"),
        ("Villarreal", "Marcelino García Toral")
    ]
    
    cleaned_teams = []
    # Deduplicate and build clean tuples matching your structural schema columns
    seen_teams = set()
    generated_id = 1
    
    for team, manager in raw_data:
        if team in seen_teams:
            continue
        seen_teams.add(team)
        
        team_id = generated_id
        generated_id += 1
        
        # Explicit NULLs to keep fields clean for your future ML feature engines
        squad_size = None
        style = None
        success_metric = None
        
        cleaned_teams.append((team_id, team, manager, squad_size, style, success_metric))
        if generated_id > 20: # Lock tightly to the core top-tier 20 clubs
            break

    print(cleaned_teams)            
    return cleaned_teams

if __name__ == "__main__":
    teams_list = get_la_liga_teams()
    connect_to_database(teams_list)