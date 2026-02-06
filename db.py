"""
Database connection and initialization module
Supports both SQLite (local development) and PostgreSQL (production/Railway)
"""

import os
import sqlite3
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)

# Determine database type from environment
DATABASE_URL = os.environ.get("DATABASE_URL")
USE_POSTGRES = DATABASE_URL is not None

# Fix Railway's postgres:// to postgresql://
if USE_POSTGRES and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)


@contextmanager
def get_conn():
    """
    Context manager for database connections
    Automatically handles PostgreSQL or SQLite based on environment
    """
    if USE_POSTGRES:
        # PostgreSQL connection
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        try:
            yield conn
        finally:
            conn.close()
    else:
        # SQLite connection (local development)
        conn = sqlite3.connect("clinic.db")
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()


def init_db():
    """Initialize database with all required tables"""
    logger.info(f"Initializing database (PostgreSQL: {USE_POSTGRES})")
    
    with get_conn() as conn:
        cursor = conn.cursor()
        
        # Appointment requests table
        if USE_POSTGRES:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS appointment_requests (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    contact VARCHAR(255) NOT NULL,
                    preferred_times TEXT,
                    service VARCHAR(255),
                    note TEXT,
                    status VARCHAR(50) DEFAULT 'new',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        else:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS appointment_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    contact TEXT NOT NULL,
                    preferred_times TEXT,
                    service TEXT,
                    note TEXT,
                    status TEXT DEFAULT 'new',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        
        # Admin credentials table
        if USE_POSTGRES:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS admin_credentials (
                    id SERIAL PRIMARY KEY,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        else:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS admin_credentials (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        
        # Password reset tokens table
        if USE_POSTGRES:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS password_reset_tokens (
                    id SERIAL PRIMARY KEY,
                    email VARCHAR(255) NOT NULL,
                    token VARCHAR(255) UNIQUE NOT NULL,
                    expires_at TIMESTAMP NOT NULL,
                    used BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        else:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS password_reset_tokens (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT NOT NULL,
                    token TEXT UNIQUE NOT NULL,
                    expires_at TIMESTAMP NOT NULL,
                    used INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        
        # Admin audit log table
        if USE_POSTGRES:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS admin_audit_log (
                    id SERIAL PRIMARY KEY,
                    action VARCHAR(255) NOT NULL,
                    details TEXT,
                    ip_address VARCHAR(45),
                    user_agent TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        else:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS admin_audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action TEXT NOT NULL,
                    details TEXT,
                    ip_address TEXT,
                    user_agent TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        
        # Create indexes for better performance
        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_appointment_status ON appointment_requests(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_appointment_created ON appointment_requests(created_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_reset_token ON password_reset_tokens(token)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_reset_email ON password_reset_tokens(email)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_created ON admin_audit_log(created_at)")
        except Exception as e:
            logger.warning(f"Index creation warning (may already exist): {e}")
        
        conn.commit()
        logger.info("Database initialization completed successfully")


def seed_admin_user():
    """
    Create initial admin user if none exists
    Only runs if ADMIN_EMAIL and ADMIN_PASSWORD_HASH are set in environment
    """
    admin_email = os.environ.get("ADMIN_EMAIL")
    admin_hash = os.environ.get("ADMIN_PASSWORD_HASH")
    
    if not admin_email or not admin_hash:
        logger.warning("ADMIN_EMAIL or ADMIN_PASSWORD_HASH not set - skipping admin seed")
        return
    
    try:
        with get_conn() as conn:
            cursor = conn.cursor()
            
            # Check if admin exists
            if USE_POSTGRES:
                cursor.execute("SELECT id FROM admin_credentials WHERE email = %s", (admin_email,))
            else:
                cursor.execute("SELECT id FROM admin_credentials WHERE email = ?", (admin_email,))
            
            if cursor.fetchone() is None:
                # Create admin user
                if USE_POSTGRES:
                    cursor.execute(
                        "INSERT INTO admin_credentials (email, password_hash) VALUES (%s, %s)",
                        (admin_email, admin_hash)
                    )
                else:
                    cursor.execute(
                        "INSERT INTO admin_credentials (email, password_hash) VALUES (?, ?)",
                        (admin_email, admin_hash)
                    )
                conn.commit()
                logger.info(f"Admin user created: {admin_email}")
            else:
                logger.info(f"Admin user already exists: {admin_email}")
    
    except Exception as e:
        logger.error(f"Error seeding admin user: {e}")


if __name__ == "__main__":
    # For testing
    logging.basicConfig(level=logging.INFO)
    init_db()
    seed_admin_user()
    print("Database initialized successfully!")