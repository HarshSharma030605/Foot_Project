import os
from dotenv import load_dotenv
import mysql.connector
from mysql.connector import Error
import pandas as pd
import requests
from bs4 import BeautifulSoup

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
        query = """INSERT IGNORE INTO teams (team_id, team_name, manager, squad_size, style_of_play, squad_success_metric, transfer_budget)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)"""
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


def fetch_live_teams():
    url = "https://en.wikipedia.org/wiki/2025%E2%80%9326_La_Liga"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")

    all_tables = soup.find_all("table")
    if len(all_tables) <= 3:
        raise IndexError("Could not index the expected table. Please check the webpage structure for any changes or updates.")
    

    target_table = all_tables[3]

    cleaned_teams = []
    generated_id = 1

    for row in target_table.find('tbody').find_all('tr'):
        cells = row.find_all(['td', 'th'])

        if len(cells) >= 2:

            team_raw = cells[0].text.split('[')[0].strip()
            manager_raw = cells[1].text.split('[')[0].strip()

            if team_raw.lower() in ['team', 'club', 'personnel and sponsorship'] or manager_raw.lower() in ['manager', 'head coach']:
                continue

            team_id = generated_id
            generated_id += 1

            squad_size = None
            style_of_play = None
            squad_success_metric = None
            transfer_budget = None

            cleaned_teams.append((team_id, team_raw, manager_raw, squad_size, style_of_play, squad_success_metric, transfer_budget))

            if len(cleaned_teams) == 21:
                break

    print(f"Total extracted teams: {len(cleaned_teams)}")
    for team in cleaned_teams:
        print(team)

    return cleaned_teams

if __name__ == "__main__":
    teams_list = fetch_live_teams()
    connect_to_database(teams_list)