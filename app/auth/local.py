import bcrypt
import os
import logging
from app.db import users

logger = logging.getLogger(__name__)

# Get admin credentials from environment variables
ADMIN_USER = os.getenv("ADMIN_USER", "admin@example.com")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

if not ADMIN_PASSWORD:
    logger.warning("ADMIN_PASSWORD environment variable not set. Using default 'admin123' for development only.")
    ADMIN_PASSWORD = "admin123"


def ensure_admin():
    """Ensure admin user exists with password from environment or default."""
    try:
        existing = users.find_one({"email": ADMIN_USER})
        if not existing:
            password_hash = bcrypt.hashpw(
                ADMIN_PASSWORD.encode("utf-8"), bcrypt.gensalt()
            ).decode("utf-8")
            users.insert_one(
                {"email": ADMIN_USER, "password": password_hash, "role": "admin"}
            )
            logger.info(f"Created admin user: {ADMIN_USER}")
        else:
            stored_password = existing.get("password", "")
            if stored_password:
                try:
                    if bcrypt.checkpw(
                        ADMIN_PASSWORD.encode("utf-8"), stored_password.encode("utf-8")
                    ):
                        return
                except Exception as e:
                    logger.error(f"Error checking password: {e}")
            password_hash = bcrypt.hashpw(
                ADMIN_PASSWORD.encode("utf-8"), bcrypt.gensalt()
            ).decode("utf-8")
            users.update_one(
                {"email": ADMIN_USER},
                {"$set": {"password": password_hash}},
            )
            logger.info(f"Updated admin user password: {ADMIN_USER}")
    except Exception as e:
        logger.error(f"Error in ensure_admin: {e}")
        raise
