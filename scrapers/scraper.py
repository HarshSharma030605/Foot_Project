import os
from dotenv import load_dotenv
import mysql.connector
from mysql.connector import Error

load_dotenv()

def connect_to_database():
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
        mock_data = (1, 'Real Madrid', 'Alvaro Arbeloa', 23, 'Direct Counter', 9.00)
        cursor.execute(query, mock_data)
        connection.commit()
        cursor.close()
        print('Data Inserted Successfully')

    except Error as e:
        print(f"Error in connecting: {e}")
    
    finally:
        if connection and connection.is_connected():
            connection.close()
            print('Connection Closed')

if __name__ == "__main__":
    connect_to_database()