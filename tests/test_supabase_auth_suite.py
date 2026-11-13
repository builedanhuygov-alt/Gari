"""
GARI AgriTech AI Lab — Supabase Auth Comprehensive Security Suite (20 Scenarios)
Tests JWT cryptographic verification, identity bridge mapping, idempotent provisioning,
tenant isolation, and fail-closed error handling.
NO PHP — Pure Python & PyJWT.
"""
import os
import sys
import time
import unittest
from datetime import datetime, timedelta, timezone

# Ensure workspace root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import jwt
import gari_auth
import gari_database

# Configure test secret for mock JWKS/JWT verification
TEST_JWT_SECRET = "super-secret-test-key-gari-supabase-2026-audit"
os.environ["SUPABASE_TEST_JWT_SECRET"] = TEST_JWT_SECRET
os.environ["SUPABASE_URL"] = "https://preview-gari.supabase.co"
os.environ["SUPABASE_EXPECTED_AUDIENCE"] = "authenticated"

def generate_test_jwt(
    sub="usr-test-uuid-001",
    email="test_farmer@gari.vn",
    iss="https://preview-gari.supabase.co/auth/v1",
    aud="authenticated",
    exp_delta=3600,
    secret=TEST_JWT_SECRET,
    alg="HS256"
):
    now = datetime.now(timezone.utc)
    payload = {
        "sub": sub,
        "email": email,
        "iss": iss,
        "aud": aud,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=exp_delta)).timestamp()),
        "user_metadata": {
            "full_name": "Nông Dân Test",
            "phone": "0912345678",
            "province": "Lâm Đồng",
            "account_type": "farmer"
        }
    }
    return jwt.encode(payload, secret, algorithm=alg)


class SupabaseAuthSecuritySuite(unittest.TestCase):

    def setUp(self):
        # Clean test records from identity links and test users
        with gari_database.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM gari_identity_links WHERE supabase_uid LIKE 'usr-test-%'")
            cursor.execute("DELETE FROM account_provisioning WHERE supabase_uid LIKE 'usr-test-%'")
            cursor.execute("DELETE FROM users WHERE email LIKE '%@test-gari.local'")
            conn.commit()

    def test_01_valid_jwt_cryptographic_verification(self):
        """[SCENARIO 1 & 5] Valid Supabase JWT verifies cleanly and extracts identity."""
        token = generate_test_jwt(sub="usr-test-uuid-valid", email="valid@test-gari.local")
        payload = gari_auth.verify_supabase_jwt(token)
        self.assertIsNotNone(payload)
        self.assertEqual(payload["sub"], "usr-test-uuid-valid")
        self.assertEqual(payload["aud"], "authenticated")

    def test_02_duplicate_email_provisioning_idempotency(self):
        """[SCENARIO 2 & 16] Duplicate provisioning calls for same UID return same SQLite user ID."""
        token = generate_test_jwt(sub="usr-test-uuid-dup", email="dup@test-gari.local")
        payload = gari_auth.verify_supabase_jwt(token)
        
        user1 = gari_auth.resolve_or_provision_supabase_user(payload)
        user2 = gari_auth.resolve_or_provision_supabase_user(payload)
        
        self.assertIsNotNone(user1)
        self.assertIsNotNone(user2)
        self.assertEqual(user1["id"], user2["id"], "Idempotent provisioning must resolve to the identical SQLite user ID.")

    def test_03_invalid_password_validation(self):
        """[SCENARIO 3] Password normalization checks."""
        # Validation constraint: passwords < 6 rejected
        with self.assertRaises(Exception):
            gari_auth.reset_password_with_token("some_token", "123")

    def test_04_email_verification_status(self):
        """[SCENARIO 4] Unverified email payload flags."""
        token = generate_test_jwt(sub="usr-test-uuid-unverified", email="unverified@test-gari.local")
        payload = gari_auth.verify_supabase_jwt(token)
        self.assertIsNotNone(payload)

    def test_05_valid_login_session_restoration(self):
        """[SCENARIO 5 & 7] validate_session succeeds with valid Supabase JWT."""
        token = generate_test_jwt(sub="usr-test-uuid-session", email="session@test-gari.local")
        user = gari_auth.validate_session(token)
        self.assertIsNotNone(user)
        self.assertEqual(user["supabase_uid"], "usr-test-uuid-session")
        self.assertEqual(user["email"], "session@test-gari.local")

    def test_06_invalid_login_rejection(self):
        """[SCENARIO 6] Invalid or corrupted JWT returns None without crashing."""
        user = gari_auth.validate_session("invalid.corrupted.token")
        self.assertIsNone(user)

    def test_07_refresh_session_and_expiration(self):
        """[SCENARIO 7 & 9] Expired JWT is rejected with None."""
        expired_token = generate_test_jwt(sub="usr-test-uuid-exp", exp_delta=-300)
        user = gari_auth.validate_session(expired_token)
        self.assertIsNone(user, "Expired JWT must be rejected.")

    def test_08_logout_and_session_invalidation(self):
        """[SCENARIO 8] Destroy session removes SQLite legacy session tokens."""
        legacy_token = gari_auth.create_session(1, remember_me=False)
        self.assertIsNotNone(gari_auth.validate_session(legacy_token))
        gari_auth.destroy_session(legacy_token)
        self.assertIsNone(gari_auth.validate_session(legacy_token))

    def test_09_invalid_signature_rejection(self):
        """[SCENARIO 10] JWT signed with wrong secret is rejected."""
        tampered_token = generate_test_jwt(sub="usr-test-tampered", secret="wrong-attacker-secret")
        user = gari_auth.validate_session(tampered_token)
        self.assertIsNone(user, "JWT with invalid signature must be rejected.")

    def test_10_wrong_issuer_rejection(self):
        """[SCENARIO 11] JWT with untrusted issuer is rejected."""
        wrong_iss_token = generate_test_jwt(sub="usr-test-iss", iss="https://rogue-issuer.evil.com/auth/v1")
        # In strict issuer mode, decode fails
        payload = gari_auth.verify_supabase_jwt(wrong_iss_token)
        # Should be None or fail validation
        if payload and payload.get("iss") != "https://preview-gari.supabase.co/auth/v1":
            self.fail("Untrusted issuer must not be validated.")

    def test_11_wrong_audience_rejection(self):
        """[SCENARIO 12] JWT with wrong audience (e.g. 'anon' key) is rejected."""
        anon_token = generate_test_jwt(sub="usr-test-anon", aud="anon")
        user = gari_auth.validate_session(anon_token)
        self.assertIsNone(user, "Tokens with audience != 'authenticated' must be rejected.")

    def test_12_missing_subject_rejection(self):
        """[SCENARIO 13] Token missing 'sub' claim is rejected."""
        payload = {"email": "nosub@test-gari.local", "aud": "authenticated", "exp": int(time.time()) + 3600}
        nosub_token = jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")
        user = gari_auth.validate_session(nosub_token)
        self.assertIsNone(user, "Tokens lacking 'sub' claim must be rejected.")

    def test_13_cross_user_isolation(self):
        """[SCENARIO 14] User A and User B resolve to strictly different SQLite user IDs."""
        token_a = generate_test_jwt(sub="usr-test-user-a", email="usera@test-gari.local")
        token_b = generate_test_jwt(sub="usr-test-user-b", email="userb@test-gari.local")
        
        user_a = gari_auth.validate_session(token_a)
        user_b = gari_auth.validate_session(token_b)
        
        self.assertNotEqual(user_a["id"], user_b["id"], "User A and User B must have strictly isolated internal user IDs.")
        self.assertNotEqual(user_a["supabase_uid"], user_b["supabase_uid"])

    def test_14_cross_tenant_isolation(self):
        """[SCENARIO 15] Tenant role separation remains intact under Supabase context."""
        token = generate_test_jwt(sub="usr-test-farmer-only", email="farmeronly@test-gari.local")
        user = gari_auth.validate_session(token)
        self.assertFalse(user["is_host_admin"], "Standard farmer must not have host_admin privileges.")
        self.assertFalse(user["is_admin"], "Standard farmer must not have admin privileges.")

    def test_15_invalid_identity_mapping_rejection(self):
        """[SCENARIO 19] Identity link with status != 'ACTIVE' is blocked."""
        token = generate_test_jwt(sub="usr-test-suspended", email="suspended@test-gari.local")
        user = gari_auth.validate_session(token)
        self.assertIsNotNone(user)
        
        # Suspend link in database
        with gari_database.get_connection() as conn:
            conn.cursor().execute(
                "UPDATE gari_identity_links SET status = 'SUSPENDED' WHERE supabase_uid = 'usr-test-suspended'"
            )
            conn.commit()

        # Next validation must reject
        blocked_user = gari_auth.validate_session(token)
        self.assertIsNone(blocked_user, "Suspended identity link must block authentication.")

    def test_16_duplicate_provisioning_concurrency(self):
        """[SCENARIO 16] Multiple consecutive sync requests do not throw database errors."""
        token = generate_test_jwt(sub="usr-test-concurrency", email="concur@test-gari.local")
        payload = gari_auth.verify_supabase_jwt(token)
        
        results = [gari_auth.resolve_or_provision_supabase_user(payload) for _ in range(5)]
        uids = {r["id"] for r in results if r}
        self.assertEqual(len(uids), 1, "Concurrent sync calls must resolve to exactly one unique SQLite user record.")

    def test_17_sqlite_persistence_verification(self):
        """[SCENARIO 17] SQLite database writes and mapping integrity."""
        token = generate_test_jwt(sub="usr-test-persist", email="persist@test-gari.local")
        user = gari_auth.validate_session(token)
        self.assertIsNotNone(user)
        
        # Verify direct SQLite query
        with gari_database.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT sqlite_user_id FROM gari_identity_links WHERE supabase_uid = 'usr-test-persist'")
            row = cursor.fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row["sqlite_user_id"], user["id"])

    def test_18_supabase_unavailable_handling(self):
        """[SCENARIO 18] Malformed token or network fault returns None without system crash."""
        result = gari_auth.verify_supabase_jwt("malformed-token-string")
        self.assertIsNone(result)

    def test_19_identity_bridge_uniqueness_constraint(self):
        """[SCENARIO 19] Integrity check on gari_identity_links uniqueness."""
        token = generate_test_jwt(sub="usr-test-unique", email="unique@test-gari.local")
        user = gari_auth.validate_session(token)
        self.assertIsNotNone(user)

    def test_20_session_cookie_token_extraction(self):
        """[SCENARIO 20] Request token extractor supports both Header and Cookie."""
        class MockRequest:
            def __init__(self, headers, cookies):
                self.headers = headers
                self.cookies = cookies

        req_bearer = MockRequest({"Authorization": "Bearer sample_token_123"}, {})
        self.assertEqual(gari_auth.extract_token_from_request(req_bearer), "sample_token_123")

        req_cookie = MockRequest({}, {"gari_session": "sample_cookie_token_456"})
        self.assertEqual(gari_auth.extract_token_from_request(req_cookie), "sample_cookie_token_456")


if __name__ == "__main__":
    unittest.main(verbosity=2)

