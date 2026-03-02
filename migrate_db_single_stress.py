#!/usr/bin/env python3
"""
Migrate DB to single stress_level column on stress_record.
Creates a new table, copies data, drops old table.
Run with: .venv\\Scripts\\python migrate_db_single_stress.py
"""

import sqlite3
from pathlib import Path


DB_PATH = Path("instance") / "stress_predictor.db"


def table_columns(cur, table):
    cur.execute(f"PRAGMA table_info({table});")
    return [row[1] for row in cur.fetchall()]


def main():
    if not DB_PATH.exists():
        print("Database not found:", DB_PATH)
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cols = table_columns(cur, "stress_record")
    if "stress_level" in cols and not any(c in cols for c in ("tree_prediction", "forest_prediction", "svm_prediction", "gbm_prediction")):
        print("stress_record already migrated.")
        conn.close()
        return

    cur.execute("ALTER TABLE stress_record RENAME TO stress_record_old;")

    cur.execute("""
        CREATE TABLE stress_record (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            timestamp DATETIME,
            anxiety_level REAL,
            mental_health_history REAL,
            depression REAL,
            headache REAL,
            sleep_quality REAL,
            breathing_problem REAL,
            living_conditions REAL,
            academic_performance REAL,
            study_load REAL,
            future_career_concerns REAL,
            extracurricular_activities REAL,
            stress_level INTEGER,
            FOREIGN KEY(user_id) REFERENCES user (id)
        );
    """)

    select_cols = [
        "id",
        "user_id",
        "timestamp",
        "anxiety_level",
        "mental_health_history",
        "depression",
        "headache",
        "sleep_quality",
        "breathing_problem",
        "living_conditions",
        "academic_performance",
        "study_load",
        "future_career_concerns",
        "extracurricular_activities",
    ]

    old_cols = table_columns(cur, "stress_record_old")
    if "stress_level" in old_cols:
        stress_expr = "stress_level"
    elif "tree_prediction" in old_cols:
        stress_expr = """
            CASE
                WHEN LOWER(tree_prediction) = 'low' THEN 0
                WHEN LOWER(tree_prediction) = 'medium' THEN 1
                WHEN LOWER(tree_prediction) = 'high' THEN 2
                WHEN tree_prediction IN (0, 1, 2) THEN tree_prediction
                ELSE NULL
            END
        """
    else:
        stress_expr = "NULL"

    cur.execute(f"""
        INSERT INTO stress_record ({", ".join(select_cols)}, stress_level)
        SELECT {", ".join(select_cols)}, {stress_expr}
        FROM stress_record_old;
    """)

    cur.execute("DROP TABLE stress_record_old;")
    conn.commit()
    conn.close()
    print("Migration completed.")


if __name__ == "__main__":
    main()
