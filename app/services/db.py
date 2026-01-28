"""
Database connection manager for Inspections PWA.
SQLite with connection pooling per request.
"""
import sqlite3
import os
from flask import g, current_app


def get_db():
    """Get database connection for current request."""
    if 'db' not in g:
        db_path = current_app.config['DATABASE_PATH']
        g.db = sqlite3.connect(db_path)
        g.db.row_factory = sqlite3.Row
        # Enable foreign keys
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(e=None):
    """Close database connection at end of request."""
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db(app):
    """Initialize database with schema if not exists."""
    app.teardown_appcontext(close_db)
    
    db_path = app.config['DATABASE_PATH']
    
    # Ensure data directory exists
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    # Check if database needs initialization
    if not os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        
        # Load schema
        schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
        with open(schema_path, 'r') as f:
            conn.executescript(f.read())
        
        # Load template seed data if exists
        seed_path = os.path.join(os.path.dirname(__file__), 'template_seed.sql')
        if os.path.exists(seed_path):
            with open(seed_path, 'r') as f:
                conn.executescript(f.read())
        
        conn.commit()
        conn.close()
        print(f"Database initialized at {db_path}")


def query_db(query, args=(), one=False):
    """Execute query and return results."""
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv


def execute_db(query, args=()):
    """Execute query and commit."""
    db = get_db()
    cur = db.execute(query, args)
    db.commit()
    return cur.lastrowid
