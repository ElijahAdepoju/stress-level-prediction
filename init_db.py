#!/usr/bin/env python3
"""
Database initialization script
Run this before running the app for the first time
"""

import os

os.environ["SKIP_MODEL_TRAINING"] = "1"

from app import app, db

if __name__ == '__main__':
    with app.app_context():
        print("Creating database tables...")
        db.create_all()
        print("Database initialized successfully!")
        print("You can now run 'flask run' or 'python app.py'")
