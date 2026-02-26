import sqlite3
import pandas as pd

def init_db():
    conn = sqlite3.connect("zones.db")
    df = pd.read_csv("data/zones_dataset.csv")
    df.to_sql("zones", conn, if_exists="replace", index=False)
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database created successfully!")