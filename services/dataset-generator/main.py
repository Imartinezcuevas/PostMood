# services/dataset-generator/main.py
import os
from datetime import datetime
from pathlib import Path

OUTPUT_DIR = os.getenv("OUTPUT_DIR", "output")
Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

def get_db_conn():
    import psycopg2
    from psycopg2.extras import RealDictCursor
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "postgres"),
        port=int(os.getenv("POSTGRES_PORT", 5432)),
        dbname=os.getenv("POSTGRES_DB", "postmood"),
        user=os.getenv("POSTGRES_USER", "postmood"),
        password=os.getenv("POSTGRES_PASSWORD", "postmood"),
        cursor_factory=RealDictCursor
    )

def next_dataset_version(base_name):
    import os
    files = [f for f in os.listdir(OUTPUT_DIR) if f.startswith(base_name) and f.endswith(".csv")]
    versions = []
    for f in files:
        parts = f.split("_v")
        if len(parts) == 2:
            v = parts[1].split(".csv")[0]
            if v.isdigit():
                versions.append(int(v))
    return max(versions, default=0) + 1

def clean_text(s: str) -> str:
    import re
    if not s:
        return ""
    s = re.sub(r"http\S+", "", s)
    s = re.sub(r"@\w+", "<USER>", s)
    s = re.sub(r"[\r\n]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s.lower()

def generate_dataset():
    import csv
    conn = get_db_conn()
    try:
        with conn.cursor() as cur:
            # obtener último id procesado
            cur.execute("SELECT last_post_id FROM dataset_generation_log ORDER BY id DESC LIMIT 1")
            last = cur.fetchone()
            last_id = last['last_post_id'] if last and 'last_post_id' in last else 0

            # seleccionar nuevas correcciones (puedes paginar si esperas >1000)
            cur.execute("""
                SELECT id, post_id, keyword, text, corrected_sentiment, score, created_at
                FROM sentiment_corrections
                WHERE id > %s AND approved IS TRUE
                ORDER BY id ASC
            """, (last_id,))
            rows = cur.fetchall()

            if not rows:
                print("No new corrections to process.")
                return

            # preparar dataset rows
            dataset_rows = []
            max_id = last_id
            for r in rows:
                rid = r['id']
                raw_text = r.get('text') or ""
                text = clean_text(raw_text)
                if not text:
                    continue
                label = r.get('corrected_sentiment') or r.get('original_sentiment')
                dataset_rows.append({"text": text, "label": label, "post_id": r.get('post_id'), "keyword": r.get('keyword')})
                if rid > max_id:
                    max_id = rid

            if not dataset_rows:
                print("No valid text rows after cleaning.")
                return

            # versionado y escritura CSV
            date_str = datetime.utcnow().strftime("%Y%m%d")
            base_name = f"dataset_{date_str}"
            version = next_dataset_version(base_name)
            filename = f"{base_name}_v{version}.csv"
            filepath = os.path.join(OUTPUT_DIR, filename)

            with open(filepath, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=["text", "label", "post_id", "keyword"])
                writer.writeheader()
                writer.writerows(dataset_rows)

            print(f"Dataset written to {filepath} rows={len(dataset_rows)}")

            # insert log: marcar hasta qué id hemos procesado
            cur.execute("INSERT INTO dataset_generation_log (last_post_id) VALUES (%s)", (max_id,))
            conn.commit()
            print(f"Updated dataset_generation_log with last_post_id={max_id}")

    finally:
        conn.close()

if __name__ == "__main__":
    generate_dataset()
