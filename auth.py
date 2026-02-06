"""
Authentication and security utilities
Handles admin login, password reset, rate limiting, and session management
"""

import os
import time
import secrets
import logging
from functools import wraps
from datetime import datetime, timedelta
from flask import session, abort, request
from werkzeug.security import check_password_hash, generate_password_hash
from db import get_conn, USE_POSTGRES

logger = logging.getLogger(__name__)

# In-memory failed login tracking (resets on restart)
failed_login_attempts = {}
chat_rate_limits = {}


def generate_reset_token():
    """Generate a secure random token for password reset"""
    return secrets.token_urlsafe(32)


def create_password_reset_token(email):
    """
    Create a password reset token for the given email
    Returns: (token, expires_at) or (None, None) if email not found
    """
    try:
        with get_conn() as conn:
            cursor = conn.cursor()
            
            # Verify email exists
            if USE_POSTGRES:
                cursor.execute("SELECT id FROM admin_credentials WHERE email = %s", (email,))
            else:
                cursor.execute("SELECT id FROM admin_credentials WHERE email = ?", (email,))
            
            if cursor.fetchone() is None:
                logger.warning(f"Password reset requested for non-existent email: {email}")
                return None, None
            
            # Generate token and expiration (1 hour from now)
            token = generate_reset_token()
            expires_at = datetime.now() + timedelta(hours=1)
            
            # Store token
            if USE_POSTGRES:
                cursor.execute("""
                    INSERT INTO password_reset_tokens (email, token, expires_at)
                    VALUES (%s, %s, %s)
                """, (email, token, expires_at))
            else:
                cursor.execute("""
                    INSERT INTO password_reset_tokens (email, token, expires_at)
                    VALUES (?, ?, ?)
                """, (email, token, expires_at))
            
            conn.commit()
            logger.info(f"Password reset token created for {email}")
            return token, expires_at
    
    except Exception as e:
        logger.error(f"Error creating reset token: {e}")
        return None, None


def verify_reset_token(token):
    """
    Verify a password reset token
    Returns: email if valid, None if invalid/expired/used
    """
    try:
        with get_conn() as conn:
            cursor = conn.cursor()
            
            if USE_POSTGRES:
                cursor.execute("""
                    SELECT email, expires_at, used 
                    FROM password_reset_tokens 
                    WHERE token = %s
                """, (token,))
            else:
                cursor.execute("""
                    SELECT email, expires_at, used 
                    FROM password_reset_tokens 
                    WHERE token = ?
                """, (token,))
            
            row = cursor.fetchone()
            
            if row is None:
                logger.warning(f"Invalid reset token attempted: {token[:10]}...")
                return None
            
            # Check if already used
            if row['used'] if USE_POSTGRES else row['used'] == 1:
                logger.warning(f"Used reset token attempted: {token[:10]}...")
                return None
            
            # Check if expired
            expires_at = row['expires_at']
            if isinstance(expires_at, str):
                expires_at = datetime.fromisoformat(expires_at)
            
            if datetime.now() > expires_at:
                logger.warning(f"Expired reset token attempted: {token[:10]}...")
                return None
            
            return row['email']
    
    except Exception as e:
        logger.error(f"Error verifying reset token: {e}")
        return None


def mark_token_as_used(token):
    """Mark a password reset token as used"""
    try:
        with get_conn() as conn:
            cursor = conn.cursor()
            
            if USE_POSTGRES:
                cursor.execute(
                    "UPDATE password_reset_tokens SET used = TRUE WHERE token = %s",
                    (token,)
                )
            else:
                cursor.execute(
                    "UPDATE password_reset_tokens SET used = 1 WHERE token = ?",
                    (token,)
                )
            
            conn.commit()
    except Exception as e:
        logger.error(f"Error marking token as used: {e}")


def cleanup_expired_tokens():
    """Remove expired and used password reset tokens"""
    try:
        with get_conn() as conn:
            cursor = conn.cursor()
            
            if USE_POSTGRES:
                cursor.execute("""
                    DELETE FROM password_reset_tokens 
                    WHERE expires_at < CURRENT_TIMESTAMP OR used = TRUE
                """)
            else:
                cursor.execute("""
                    DELETE FROM password_reset_tokens 
                    WHERE expires_at < CURRENT_TIMESTAMP OR used = 1
                """)
            
            deleted = cursor.rowcount
            conn.commit()
            
            if deleted > 0:
                logger.info(f"Cleaned up {deleted} expired/used tokens")
    
    except Exception as e:
        logger.error(f"Failed to cleanup tokens: {e}")


def get_admin_by_email(email):
    """Get admin credentials by email"""
    try:
        with get_conn() as conn:
            cursor = conn.cursor()
            
            if USE_POSTGRES:
                cursor.execute(
                    "SELECT * FROM admin_credentials WHERE email = %s",
                    (email,)
                )
            else:
                cursor.execute(
                    "SELECT * FROM admin_credentials WHERE email = ?",
                    (email,)
                )
            
            return cursor.fetchone()
    
    except Exception as e:
        logger.error(f"Error getting admin by email: {e}")
        return None


def update_admin_password(email, new_password):
    """Update admin password"""
    try:
        password_hash = generate_password_hash(new_password)
        
        with get_conn() as conn:
            cursor = conn.cursor()
            
            if USE_POSTGRES:
                cursor.execute("""
                    UPDATE admin_credentials 
                    SET password_hash = %s, updated_at = CURRENT_TIMESTAMP 
                    WHERE email = %s
                """, (password_hash, email))
            else:
                cursor.execute("""
                    UPDATE admin_credentials 
                    SET password_hash = ?, updated_at = CURRENT_TIMESTAMP 
                    WHERE email = ?
                """, (password_hash, email))
            
            conn.commit()
            logger.info(f"Password updated for {email}")
            return True
    
    except Exception as e:
        logger.error(f"Error updating password: {e}")
        return False


def verify_admin_password(email, password):
    """Verify admin password"""
    admin = get_admin_by_email(email)
    if admin and check_password_hash(admin['password_hash'], password):
        return True
    return False


def log_admin_action(action, details=""):
    """Log admin actions to audit log"""
    try:
        with get_conn() as conn:
            cursor = conn.cursor()
            
            ip_address = request.remote_addr if request else None
            user_agent = request.headers.get('User-Agent', 'Unknown') if request else 'Unknown'
            
            if USE_POSTGRES:
                cursor.execute("""
                    INSERT INTO admin_audit_log (action, details, ip_address, user_agent)
                    VALUES (%s, %s, %s, %s)
                """, (action, details, ip_address, user_agent))
            else:
                cursor.execute("""
                    INSERT INTO admin_audit_log (action, details, ip_address, user_agent)
                    VALUES (?, ?, ?, ?)
                """, (action, details, ip_address, user_agent))
            
            conn.commit()
    except Exception as e:
        logger.error(f"Failed to log admin action: {e}")


def check_rate_limit(ip, max_attempts=5, window_minutes=15):
    """
    Check if IP has exceeded rate limit
    Returns: (is_limited, attempts_remaining)
    """
    now = time.time()
    window_seconds = window_minutes * 60
    
    # Clean old attempts
    if ip in failed_login_attempts:
        failed_login_attempts[ip] = [
            t for t in failed_login_attempts[ip] 
            if now - t < window_seconds
        ]
    
    # Check limit
    attempts = len(failed_login_attempts.get(ip, []))
    is_limited = attempts >= max_attempts
    remaining = max(0, max_attempts - attempts)
    
    return is_limited, remaining


def record_failed_login(ip):
    """Record a failed login attempt"""
    failed_login_attempts.setdefault(ip, []).append(time.time())


def clear_failed_logins(ip):
    """Clear failed login attempts for IP (on successful login)"""
    failed_login_attempts.pop(ip, None)


def require_admin(f):
    """Decorator to require admin authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("is_admin"):
            abort(403)
        
        # Check session timeout (60 minutes)
        last_activity = session.get("last_activity")
        if last_activity:
            try:
                last_time = datetime.fromisoformat(last_activity)
                if datetime.now() - last_time > timedelta(minutes=60):
                    session.clear()
                    log_admin_action("SESSION_TIMEOUT", "Session expired due to inactivity")
                    abort(403)
            except (ValueError, TypeError):
                session.clear()
                abort(403)
        
        # Update last activity
        session["last_activity"] = datetime.now().isoformat()
        
        return f(*args, **kwargs)
    
    return decorated_function


def rate_limit_chat(max_per_minute=20):
    """Rate limit chatbot requests"""
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            ip = request.remote_addr
            now = time.time()
            
            # Clean old entries (older than 60 seconds)
            chat_rate_limits[ip] = [
                t for t in chat_rate_limits.get(ip, []) 
                if now - t < 60
            ]
            
            # Check limit
            if len(chat_rate_limits.get(ip, [])) >= max_per_minute:
                from flask import jsonify
                return jsonify({
                    "reply": "Please wait a moment before sending another message. 😊"
                }), 429
            
            # Record this request
            chat_rate_limits.setdefault(ip, []).append(now)
            return f(*args, **kwargs)
        
        return wrapped
    return decorator