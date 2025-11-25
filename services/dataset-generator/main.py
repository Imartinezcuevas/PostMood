# services/dataset-generator/generate_dataset.py
import os
import psycopg2
import pandas as pd
from psycopg2.extras import RealDictCursor

# -----------------
# Config
# -----------------
DB_HOST = os.getenv("POSTGRES_HOST", "postgres")
DB_PORT = int(os.getenv("POSTGRES_PORT", 5432))
DB_NAME = os.getenv("POSTGRES_DB", "postmood")
DB_USER = os.getenv("POSTGRES_USER", "postmood")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postmood")

OUTPUT_DIR = os.getenv("OUTPUT_DIR", "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# -----------------
# Helpers
# -----------------
def get_db_conn():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        cursor_factory=RealDictCursor
    )

def next_dataset_version(base_name):
    files = [f for f in os.listdir(OUTPUT_DIR) if f.startswith(base_name) and f.endswith(".csv")]
    versions = []
    for f in files:
        parts = f.split("_v")
        if len(parts) == 2:
            v = parts[1].split(".csv")[0]
            if v.isdigit():
                versions.append(int(v))
    return max(versions, default=0) + 1

# -----------------
# Main
# -----------------
def generate_dataset():
    conn = get_db_conn()
    df = pd.read_sql("""
        SELECT post_id, keyword, full_text AS text, label AS sentiment, score
        FROM posts
        WHERE full_text IS NOT NULL AND full_text != ''
    """, conn)
    conn.close()

    if df.empty:
        print("No posts available for dataset.")
        return

    version = next_dataset_version("dataset")
    filename = f"dataset_v{version}.csv"
    filepath = os.path.join(OUTPUT_DIR, filename)

    df.to_csv(filepath, index=False)
    print(f"Dataset generado: {filepath} ({len(df)} filas)")

if __name__ == "__main__":
    generate_dataset()
