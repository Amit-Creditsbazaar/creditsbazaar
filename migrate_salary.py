
import mysql.connector
from dotenv import load_dotenv
import os

load_dotenv()

def get_db_connection():
    try:
        conn = mysql.connector.connect(
            host=os.getenv('MYSQL_HOST', 'localhost'),
            user=os.getenv('MYSQL_USER', 'root'),
            password=os.getenv('MYSQL_PASSWORD', ''),
            database=os.getenv('MYSQL_DB', 'credit_bazaar')
        )
        return conn
    except mysql.connector.Error as err:
        print(f"Error connecting to database: {err}")
        return None

def migrate():
    conn = get_db_connection()
    if not conn:
        return

    cursor = conn.cursor()
    
    tables = ['loan_applications', 'credit_card_applications']
    
    for table in tables:
        try:
            # Check if column exists
            cursor.execute(f"SHOW COLUMNS FROM {table} LIKE 'monthly_salary'")
            result = cursor.fetchone()
            
            if result:
                print(f"Renaming monthly_salary to annual_salary in {table}...")
                cursor.execute(f"ALTER TABLE {table} CHANGE monthly_salary annual_salary VARCHAR(50)")
                print(f"Successfully renamed column in {table}.")
            else:
                print(f"Column monthly_salary not found in {table} (or already renamed).")
                
                # Verify annual_salary exists
                cursor.execute(f"SHOW COLUMNS FROM {table} LIKE 'annual_salary'")
                if cursor.fetchone():
                    print(f"Column annual_salary exists in {table}.")
                else:
                    print(f"Column annual_salary does NOT exist in {table}. Check schema.")

        except mysql.connector.Error as err:
            print(f"Error migrating {table}: {err}")

    conn.commit()
    cursor.close()
    conn.close()

if __name__ == '__main__':
    migrate()
