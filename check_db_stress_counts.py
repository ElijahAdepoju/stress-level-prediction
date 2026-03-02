#!/usr/bin/env python3
"""
Quick report of stress_level counts in the DB.
Run with: .venv\\Scripts\\python check_db_stress_counts.py
"""

import sqlite3
from pathlib import Path


DB_PATH = Path("instance") / "stress_predictor.db"


def main():
    if not DB_PATH.exists():
        print("Database not found:", DB_PATH)
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM stress_record;")
    total = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM stress_record WHERE stress_level IS NULL;")
    nulls = cur.fetchone()[0]

    cur.execute("SELECT stress_level, COUNT(*) FROM stress_record GROUP BY stress_level ORDER BY stress_level;")
    rows = cur.fetchall()

    print("Total records:", total)
    print("Missing stress_level:", nulls)
    for level, count in rows:
        print(f"stress_level={level}: {count}")

    conn.close()


if __name__ == "__main__":
    main()
