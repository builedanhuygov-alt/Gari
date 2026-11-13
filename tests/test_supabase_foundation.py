"""
GARI AgriTech AI Platform — Supabase Foundation Test Suite (Sprint 1)
File: tests/test_supabase_foundation.py

Validates:
1. Migration files structure, ordering, and syntax.
2. PostgreSQL DDL integrity (profiles, user_preferences, gari_identity_links, account_provisioning).
3. Row Level Security (RLS) policies and least-privilege enforcement.
4. Role escalation guards (protect_profile_privileged_fields).
5. Identity bridge mapping integrity (1:1 constraint enforcement).
6. Idempotent account provisioning.
7. Migration repeatability.
NO PHP — Pure Python 3.11+ and SQLite in-memory relational simulation.
"""

import os
import sys
import re
import sqlite3
import unittest
from pathlib import Path

# Setup workspace paths
ROOT_DIR = Path(__file__).resolve().parent.parent
MIGRATIONS_DIR = ROOT_DIR / "supabase" / "migrations"


class TestSupabaseFoundationMigrations(unittest.TestCase):
    """Test suite validating SQL migration files, DDL constraints, RLS, and security policies."""

    @classmethod
    def setUpClass(cls):
        cls.migration_files = sorted(list(MIGRATIONS_DIR.glob("*.sql")))
        cls.combined_sql = ""
        for f in cls.migration_files:
            cls.combined_sql += f"\n-- FILE: {f.name}\n" + f.read_text(encoding="utf-8")

    def test_01_migration_files_present_and_ordered(self):
        """Verify that all required versioned migration files exist in sequence."""
        self.assertGreaterEqual(len(self.migration_files), 5, "Expected at least 5 migration files.")
        
        expected_prefixes = [
            "20261111120000_create_base_schema_and_profiles",
            "20261111120001_create_user_preferences",
            "20261111120002_create_identity_bridge_and_provisioning",
            "20261111120003_create_idempotent_provisioning_trigger",
            "20261111120004_create_rls_and_privilege_guards"
        ]
        
        actual_names = [f.stem for f in self.migration_files]
        for prefix in expected_prefixes:
            matched = any(actual.startswith(prefix) for actual in actual_names)
            self.assertTrue(matched, f"Missing required migration: {prefix}")

    def test_02_ddl_tables_defined_with_proper_constraints(self):
        """Verify all 4 core tables are defined with required columns and foreign keys."""
        # Check profiles
        self.assertIn("CREATE TABLE IF NOT EXISTS public.profiles", self.combined_sql)
        self.assertIn("REFERENCES auth.users(id) ON DELETE CASCADE", self.combined_sql)
        self.assertIn("account_type IN ('farmer', 'enterprise', 'expert', 'host_admin')", self.combined_sql)
        self.assertIn("moderation_status IN ('clean', 'flagged', 'suspended', 'under_review')", self.combined_sql)

        # Check user_preferences
        self.assertIn("CREATE TABLE IF NOT EXISTS public.user_preferences", self.combined_sql)
        self.assertIn("REFERENCES public.profiles(id) ON DELETE CASCADE", self.combined_sql)
        self.assertIn("language IN ('vi', 'en')", self.combined_sql)
        self.assertIn("theme IN ('light', 'dark', 'system')", self.combined_sql)

        # Check gari_identity_links
        self.assertIn("CREATE TABLE IF NOT EXISTS public.gari_identity_links", self.combined_sql)
        self.assertIn("supabase_uid UUID UNIQUE NOT NULL", self.combined_sql)
        self.assertIn("sqlite_user_id INTEGER UNIQUE NOT NULL", self.combined_sql)
        self.assertIn("status IN ('ACTIVE', 'SUSPENDED', 'PENDING_MIGRATION')", self.combined_sql)

        # Check account_provisioning
        self.assertIn("CREATE TABLE IF NOT EXISTS public.account_provisioning", self.combined_sql)
        self.assertIn("status IN ('PENDING', 'ACTIVE', 'FAILED')", self.combined_sql)

    def test_03_row_level_security_explicitly_enabled(self):
        """Verify Row Level Security (RLS) is enabled on all 4 foundation tables."""
        required_tables = ["profiles", "user_preferences", "gari_identity_links", "account_provisioning"]
        for tbl in required_tables:
            pattern = rf"ALTER TABLE public\.{tbl}\s+ENABLE ROW LEVEL SECURITY;"
            match = re.search(pattern, self.combined_sql, re.IGNORECASE)
            self.assertIsNotNone(match, f"RLS not enabled on public.{tbl}")

    def test_04_rls_policies_least_privilege_enforcement(self):
        """Verify RLS policies enforce tenant isolation and least privilege."""
        # 1. profiles: users can update only their own profile
        self.assertIn('CREATE POLICY "profiles_update_own"', self.combined_sql)
        self.assertIn('(auth.uid() = id)', self.combined_sql)

        # 2. preferences: users can select/update only their own
        self.assertIn('CREATE POLICY "prefs_select_own"', self.combined_sql)
        self.assertIn('(auth.uid() = user_id)', self.combined_sql)
        self.assertIn('CREATE POLICY "prefs_update_own"', self.combined_sql)

        # 3. gari_identity_links: Ordinary users have SELECT ONLY. Zero write access.
        self.assertIn('CREATE POLICY "links_select_own"', self.combined_sql)
        self.assertIn('(auth.uid() = supabase_uid)', self.combined_sql)
        self.assertNotIn('FOR INSERT TO authenticated', self.combined_sql.split('-- 5. Row Level Security Policies: public.gari_identity_links')[1].split('-- 6. Row Level Security Policies')[0])
        self.assertNotIn('FOR UPDATE TO authenticated', self.combined_sql.split('-- 5. Row Level Security Policies: public.gari_identity_links')[1].split('-- 6. Row Level Security Policies')[0])

        # 4. account_provisioning: Ordinary users have SELECT ONLY. Zero write access.
        self.assertIn('CREATE POLICY "prov_select_own"', self.combined_sql)
        self.assertIn('(auth.uid() = supabase_uid)', self.combined_sql)

    def test_05_role_escalation_guard_implementation(self):
        """Verify protect_profile_privileged_fields trigger protects administrative columns."""
        self.assertIn("CREATE OR REPLACE FUNCTION public.protect_profile_privileged_fields()", self.combined_sql)
        self.assertIn("trg_protect_profile_privileged_fields", self.combined_sql)
        
        # Check all guarded fields
        guarded_fields = [
            "account_type",
            "is_admin",
            "is_host_admin",
            "is_expert",
            "is_active",
            "moderation_status",
            "feature_restrictions"
        ]
        for field in guarded_fields:
            self.assertIn(f"NEW.{field} IS DISTINCT FROM OLD.{field}", self.combined_sql)
        
        self.assertIn("CANNOT_MODIFY_PRIVILEGED_FIELDS", self.combined_sql)

    def test_06_column_level_security_permissions(self):
        """Verify column-level permissions revoke blanket updates on sensitive fields."""
        self.assertIn("REVOKE UPDATE ON public.profiles FROM authenticated;", self.combined_sql)
        self.assertIn("GRANT UPDATE (full_name, phone, province, address, avatar_url, bio) ON public.profiles TO authenticated;", self.combined_sql)
        self.assertIn("REVOKE INSERT, UPDATE, DELETE ON public.gari_identity_links FROM authenticated;", self.combined_sql)
        self.assertIn("REVOKE INSERT, UPDATE, DELETE ON public.account_provisioning FROM authenticated;", self.combined_sql)

    def test_07_idempotent_provisioning_trigger_design(self):
        """Verify idempotent account provisioning on new user signups."""
        self.assertIn("CREATE OR REPLACE FUNCTION public.handle_new_user_signup()", self.combined_sql)
        self.assertIn("CREATE TRIGGER on_auth_user_created", self.combined_sql)
        self.assertIn("ON CONFLICT (id) DO UPDATE", self.combined_sql)
        self.assertIn("ON CONFLICT (user_id) DO NOTHING", self.combined_sql)
        self.assertIn("ON CONFLICT (supabase_uid) DO NOTHING", self.combined_sql)
        self.assertIn("CREATE OR REPLACE FUNCTION public.provision_user_account_idempotent", self.combined_sql)

    def test_08_migration_repeatability_and_idempotency(self):
        """Verify that all migration statements include idempotent guards."""
        table_creates = re.findall(r"CREATE TABLE (\w+\.\w+)", self.combined_sql)
        self.assertEqual(len(table_creates), 0, "All CREATE TABLE statements must use IF NOT EXISTS")
        
        table_if_not_exists = re.findall(r"CREATE TABLE IF NOT EXISTS", self.combined_sql)
        self.assertGreaterEqual(len(table_if_not_exists), 4)

        trigger_drops = re.findall(r"DROP TRIGGER IF EXISTS", self.combined_sql)
        self.assertGreaterEqual(len(trigger_drops), 5)


class TestRelationalIntegritySimulation(unittest.TestCase):
    """In-memory SQLite simulation of PostgreSQL schema constraints, 1:1 mapping, and RLS behavior."""

    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.execute("PRAGMA foreign_keys = ON;")
        self.cursor = self.conn.cursor()

        # Create auth.users simulation
        self.cursor.execute("""
        CREATE TABLE auth_users (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # Create public.profiles simulation
        self.cursor.execute("""
        CREATE TABLE profiles (
            id TEXT PRIMARY KEY,
            full_name TEXT NOT NULL,
            phone TEXT,
            province TEXT DEFAULT 'Lâm Đồng',
            account_type TEXT NOT NULL DEFAULT 'farmer' CHECK (account_type IN ('farmer', 'enterprise', 'expert', 'host_admin')),
            is_admin INTEGER NOT NULL DEFAULT 0,
            is_host_admin INTEGER NOT NULL DEFAULT 0,
            is_expert INTEGER NOT NULL DEFAULT 0,
            is_active INTEGER NOT NULL DEFAULT 1,
            moderation_status TEXT NOT NULL DEFAULT 'clean' CHECK (moderation_status IN ('clean', 'flagged', 'suspended', 'under_review')),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (id) REFERENCES auth_users(id) ON DELETE CASCADE
        );
        """)

        # Create public.user_preferences simulation
        self.cursor.execute("""
        CREATE TABLE user_preferences (
            user_id TEXT PRIMARY KEY,
            language TEXT NOT NULL DEFAULT 'vi' CHECK (language IN ('vi', 'en')),
            timezone TEXT NOT NULL DEFAULT 'Asia/Ho_Chi_Minh',
            theme TEXT NOT NULL DEFAULT 'system' CHECK (theme IN ('light', 'dark', 'system')),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES profiles(id) ON DELETE CASCADE
        );
        """)

        # Create public.gari_identity_links simulation (Strict 1:1)
        self.cursor.execute("""
        CREATE TABLE gari_identity_links (
            id TEXT PRIMARY KEY,
            supabase_uid TEXT UNIQUE NOT NULL,
            sqlite_user_id INTEGER UNIQUE NOT NULL,
            status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'SUSPENDED', 'PENDING_MIGRATION')),
            linked_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (supabase_uid) REFERENCES auth_users(id) ON DELETE CASCADE
        );
        """)

        # Create public.account_provisioning simulation
        self.cursor.execute("""
        CREATE TABLE account_provisioning (
            supabase_uid TEXT PRIMARY KEY,
            status TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'ACTIVE', 'FAILED')),
            retry_count INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (supabase_uid) REFERENCES auth_users(id) ON DELETE CASCADE
        );
        """)
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_09_foreign_key_cascading_deletion(self):
        """Verify deleting an auth.users record cascades and purges all dependent profile/link records."""
        uid = "usr-uuid-test-01"
        self.cursor.execute("INSERT INTO auth_users (id, email) VALUES (?, ?)", (uid, "farmer1@gari.vn"))
        self.cursor.execute("INSERT INTO profiles (id, full_name) VALUES (?, ?)", (uid, "Nguyen Van A"))
        self.cursor.execute("INSERT INTO user_preferences (user_id) VALUES (?)", (uid,))
        self.cursor.execute("INSERT INTO gari_identity_links (id, supabase_uid, sqlite_user_id) VALUES (?, ?, ?)",
                            ("link-01", uid, 1001))
        self.cursor.execute("INSERT INTO account_provisioning (supabase_uid, status) VALUES (?, ?)", (uid, "ACTIVE"))
        self.conn.commit()

        # Delete from auth_users
        self.cursor.execute("DELETE FROM auth_users WHERE id = ?", (uid,))
        self.conn.commit()

        # Verify cascade
        self.cursor.execute("SELECT COUNT(*) FROM profiles WHERE id = ?", (uid,))
        self.assertEqual(self.cursor.fetchone()[0], 0)
        self.cursor.execute("SELECT COUNT(*) FROM user_preferences WHERE user_id = ?", (uid,))
        self.assertEqual(self.cursor.fetchone()[0], 0)
        self.cursor.execute("SELECT COUNT(*) FROM gari_identity_links WHERE supabase_uid = ?", (uid,))
        self.assertEqual(self.cursor.fetchone()[0], 0)
        self.cursor.execute("SELECT COUNT(*) FROM account_provisioning WHERE supabase_uid = ?", (uid,))
        self.assertEqual(self.cursor.fetchone()[0], 0)

    def test_10_identity_bridge_1_to_1_integrity(self):
        """Verify bidirectional unique constraint prevents multiple mappings for same sqlite_user_id or supabase_uid."""
        self.cursor.execute("INSERT INTO auth_users (id, email) VALUES ('u1', 'u1@gari.vn'), ('u2', 'u2@gari.vn')")
        self.cursor.execute("INSERT INTO gari_identity_links (id, supabase_uid, sqlite_user_id) VALUES ('l1', 'u1', 5001)")
        self.conn.commit()

        # Attempt to map different supabase_uid to the SAME sqlite_user_id (5001) -> Must FAIL
        with self.assertRaises(sqlite3.IntegrityError):
            self.cursor.execute("INSERT INTO gari_identity_links (id, supabase_uid, sqlite_user_id) VALUES ('l2', 'u2', 5001)")

        # Attempt to map same supabase_uid (u1) to different sqlite_user_id (5002) -> Must FAIL
        with self.assertRaises(sqlite3.IntegrityError):
            self.cursor.execute("INSERT INTO gari_identity_links (id, supabase_uid, sqlite_user_id) VALUES ('l3', 'u1', 5002)")

    def test_11_check_constraints_enforcement(self):
        """Verify CHECK constraints strictly reject illegal roles or statuses."""
        self.cursor.execute("INSERT INTO auth_users (id, email) VALUES ('u1', 'u1@gari.vn')")
        
        # Illegal account_type
        with self.assertRaises(sqlite3.IntegrityError):
            self.cursor.execute("INSERT INTO profiles (id, full_name, account_type) VALUES ('u1', 'Hacker', 'root_admin')")

        # Illegal language
        with self.cursor.connection:
            self.cursor.execute("INSERT INTO profiles (id, full_name) VALUES ('u1', 'Farmer')")
        with self.assertRaises(sqlite3.IntegrityError):
            self.cursor.execute("INSERT INTO user_preferences (user_id, language) VALUES ('u1', 'xx')")

    def test_12_idempotent_upsert_simulation(self):
        """Verify idempotent UPSERT prevents duplicate provisioning crashes."""
        uid = "usr-idempotent-01"
        self.cursor.execute("INSERT INTO auth_users (id, email) VALUES (?, ?)", (uid, "idem@gari.vn"))
        
        # First provisioning
        self.cursor.execute("""
        INSERT INTO profiles (id, full_name, phone) VALUES (?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET full_name = excluded.full_name, phone = excluded.phone
        """, (uid, "Initial Name", "0900000001"))
        
        # Second provisioning (Retry / Update)
        self.cursor.execute("""
        INSERT INTO profiles (id, full_name, phone) VALUES (?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET full_name = excluded.full_name, phone = excluded.phone
        """, (uid, "Updated Name", "0900000002"))
        self.conn.commit()

        self.cursor.execute("SELECT full_name, phone FROM profiles WHERE id = ?", (uid,))
        row = self.cursor.fetchone()
        self.assertEqual(row[0], "Updated Name")
        self.assertEqual(row[1], "0900000002")

    def test_13_simulated_role_escalation_guard(self):
        """Simulate protect_profile_privileged_fields logic rejecting unauthorized role updates."""
        uid = "usr-guarded-01"
        self.cursor.execute("INSERT INTO auth_users (id, email) VALUES (?, ?)", (uid, "farmer_guard@gari.vn"))
        self.cursor.execute("INSERT INTO profiles (id, full_name, account_type, is_admin) VALUES (?, ?, 'farmer', 0)", (uid, "Farmer"))
        self.conn.commit()

        # Simulate update logic with guard
        def update_profile(caller_role, user_id, new_full_name, new_is_admin=None, new_account_type=None):
            self.cursor.execute("SELECT account_type, is_admin FROM profiles WHERE id = ?", (user_id,))
            old_type, old_admin = self.cursor.fetchone()
            
            # Guard check: Only service_role can alter is_admin or account_type
            if caller_role != "service_role":
                if new_is_admin is not None and new_is_admin != old_admin:
                    raise PermissionError("CANNOT_MODIFY_PRIVILEGED_FIELDS: Updating is_admin is strictly prohibited.")
                if new_account_type is not None and new_account_type != old_type:
                    raise PermissionError("CANNOT_MODIFY_PRIVILEGED_FIELDS: Updating account_type requires host administrator authorization.")

            self.cursor.execute("""
            UPDATE profiles SET full_name = COALESCE(?, full_name),
                                is_admin = COALESCE(?, is_admin),
                                account_type = COALESCE(?, account_type)
            WHERE id = ?
            """, (new_full_name, new_is_admin, new_account_type, user_id))
            self.conn.commit()

        # 1. Normal user updates own name -> SUCCEEDS
        update_profile(caller_role="authenticated", user_id=uid, new_full_name="Farmer Renamed")
        self.cursor.execute("SELECT full_name FROM profiles WHERE id = ?", (uid,))
        self.assertEqual(self.cursor.fetchone()[0], "Farmer Renamed")

        # 2. Normal user attempts to escalate to is_admin=1 -> FAILS with PermissionError
        with self.assertRaises(PermissionError) as ctx:
            update_profile(caller_role="authenticated", user_id=uid, new_full_name="Hacker", new_is_admin=1)
        self.assertIn("CANNOT_MODIFY_PRIVILEGED_FIELDS", str(ctx.exception))

        # 3. Normal user attempts to change account_type to host_admin -> FAILS with PermissionError
        with self.assertRaises(PermissionError) as ctx:
            update_profile(caller_role="authenticated", user_id=uid, new_full_name="Hacker", new_account_type="host_admin")
        self.assertIn("CANNOT_MODIFY_PRIVILEGED_FIELDS", str(ctx.exception))

        # 4. Service role updates account_type -> SUCCEEDS
        update_profile(caller_role="service_role", user_id=uid, new_full_name="Verified Expert", new_account_type="expert")
        self.cursor.execute("SELECT account_type FROM profiles WHERE id = ?", (uid,))
        self.assertEqual(self.cursor.fetchone()[0], "expert")


if __name__ == "__main__":
    unittest.main()

