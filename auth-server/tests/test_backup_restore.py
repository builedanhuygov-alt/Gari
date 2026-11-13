"""
Tests for Database Backup, Recovery & Restart Persistence
"""
import pytest
import tempfile
import sqlite3
from pathlib import Path
from scripts.backup_db import backup_database
from scripts.restore_db import restore_database


def test_database_backup_and_recovery():
    """Test 16: Verifies lock-free online backup and safe restoration."""
    temp_dir = tempfile.mkdtemp()
    source_db = Path(temp_dir) / "source_test.db"
    backup_dir = Path(temp_dir) / "backups"
    restored_db = Path(temp_dir) / "restored_test.db"

    # 1. Create and populate source database with WAL mode
    conn = sqlite3.connect(str(source_db))
    cursor = conn.cursor()
    cursor.execute("PRAGMA journal_mode = WAL;")
    cursor.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT, full_name TEXT);")
    for i in range(1, 4):
        cursor.execute("INSERT INTO users (email, full_name) VALUES (?, ?);", (f"farmer_{i}@gari.vn", f"Farmer {i}"))
    conn.commit()
    conn.close()

    # 2. Execute backup
    backup_file = backup_database(str(source_db), str(backup_dir), compress=True)
    assert Path(backup_file).exists()
    assert backup_file.endswith(".gz")

    # 3. Restore to a new location
    success = restore_database(backup_file, str(restored_db))
    assert success is True
    assert restored_db.exists()

    # 4. Connect to restored database and verify data integrity
    res_conn = sqlite3.connect(str(restored_db))
    res_cursor = res_conn.cursor()
    res_cursor.execute("SELECT count(*) FROM users;")
    count = res_cursor.fetchone()[0]
    res_cursor.execute("SELECT email FROM users ORDER BY id;")
    emails = [row[0] for row in res_cursor.fetchall()]
    res_conn.close()

    assert count == 3
    assert emails == ["farmer_1@gari.vn", "farmer_2@gari.vn", "farmer_3@gari.vn"]


def test_restart_persistence():
    """Test 17: Verifies records persist across process restarts."""
    temp_dir = tempfile.mkdtemp()
    db_path = Path(temp_dir) / "persist_test.db"

    # Process 1: Write record
    conn1 = sqlite3.connect(str(db_path))
    c1 = conn1.cursor()
    c1.execute("PRAGMA journal_mode = WAL;")
    c1.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT, account_type TEXT);")
    c1.execute("INSERT INTO users (email, account_type) VALUES ('persist_restart@gari.vn', 'farmer');")
    conn1.commit()
    conn1.close()  # Simulate process shutdown

    # Process 2: Read record after restart
    conn2 = sqlite3.connect(str(db_path))
    c2 = conn2.cursor()
    c2.execute("SELECT email, account_type FROM users WHERE email='persist_restart@gari.vn';")
    row = c2.fetchone()
    conn2.close()

    assert row is not None
    assert row[0] == "persist_restart@gari.vn"
    assert row[1] == "farmer"
