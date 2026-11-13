"""
GARI AI LAB — Development Seed Script (database/seed_dev.py)
Initializes clearly identified development test accounts, sample farms, and diagnoses.
Does NOT overwrite existing data.
"""

import logging
import sqlite3
import sys
from pathlib import Path

# Add project root to sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import gari_auth
import gari_database

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("gari_seed_dev")


def seed_development_environment():
    app_env = os.getenv("APP_ENV", "development").lower()
    if app_env in ("production", "prod"):
        logger.error("CRITICAL SAFEGUARD: seed_dev.py cannot be executed in production environment!")
        return

    logger.info("Checking development test accounts...")
    
    # 1. Primary Agronomist Test Account
    dan_email = "danhuynh@gari.vn"
    dan_user = None
    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE LOWER(email) = LOWER(?)", (dan_email,))
        row = cursor.fetchone()
        if not row:
            logger.info("Seeding primary test agronomist: %s", dan_email)
            dan_user = gari_auth.register_user(
                full_name="Kỹ sư Đan Huỳnh",
                email=dan_email,
                password="Password123!",
                confirm_password="Password123!",
                account_type="Đơn vị dịch vụ nông nghiệp",
                phone="0912345678"
            )
        else:
            dan_user = dict(row)
            logger.info("Primary test agronomist already exists (ID: %s)", dan_user["id"])

    # 2. Sample Farmer Test Account
    farmer_email = "nongdan.mau@gari.vn"
    with gari_database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE LOWER(email) = LOWER(?)", (farmer_email,))
        row = cursor.fetchone()
        if not row:
            logger.info("Seeding sample farmer account: %s", farmer_email)
            gari_auth.register_user(
                full_name="Nguyễn Văn Nông Dân",
                email=farmer_email,
                password="FarmerPassword123!",
                confirm_password="FarmerPassword123!",
                account_type="Nông hộ",
                phone="0987654321"
            )
        else:
            logger.info("Sample farmer account already exists (ID: %s)", row["id"])

    logger.info("Seed process completed successfully!")
    logger.info("Credentials for local testing:")
    logger.info("  1. Agronomist: danhuynh@gari.vn / Password123!")
    logger.info("  2. Farmer:      nongdan.mau@gari.vn / FarmerPassword123!")


if __name__ == "__main__":
    seed_development_environment()
