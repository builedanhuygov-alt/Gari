-- ============================================================================
-- GARI AgriTech AI Platform — Supabase Rollback & Teardown Verification
-- File: supabase/tests/99_rollback_and_cleanup.sql
-- Target: Disposable PostgreSQL 15 Container (GitHub Actions CI)
-- Purpose:
-- Safely tears down all schema objects in reverse dependency order,
-- verifying rollback integrity and absence of dangling references.
-- ============================================================================

-- 1. Drop RLS Policies
DROP POLICY IF EXISTS "profiles_select_own" ON public.profiles;
DROP POLICY IF EXISTS "profiles_update_own" ON public.profiles;
DROP POLICY IF EXISTS "profiles_service_role" ON public.profiles;
DROP POLICY IF EXISTS "prefs_select_own" ON public.user_preferences;
DROP POLICY IF EXISTS "prefs_update_own" ON public.user_preferences;
DROP POLICY IF EXISTS "prefs_service_role" ON public.user_preferences;
DROP POLICY IF EXISTS "links_select_own" ON public.gari_identity_links;
DROP POLICY IF EXISTS "links_service_role" ON public.gari_identity_links;
DROP POLICY IF EXISTS "prov_select_own" ON public.account_provisioning;
DROP POLICY IF EXISTS "prov_service_role" ON public.account_provisioning;

-- 2. Drop Triggers
DROP TRIGGER IF EXISTS trg_protect_profile_privileged_fields ON public.profiles;
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
DROP TRIGGER IF EXISTS trg_account_provisioning_updated_at ON public.account_provisioning;
DROP TRIGGER IF EXISTS trg_gari_identity_links_updated_at ON public.gari_identity_links;
DROP TRIGGER IF EXISTS trg_user_preferences_updated_at ON public.user_preferences;
DROP TRIGGER IF EXISTS trg_profiles_updated_at ON public.profiles;

-- 3. Drop Tables in Reverse Dependency Order
DROP TABLE IF EXISTS public.diagnosis_jobs CASCADE;
DROP TABLE IF EXISTS public.notifications CASCADE;
DROP TABLE IF EXISTS public.diagnoses CASCADE;
DROP TABLE IF EXISTS public.cultivation_tasks CASCADE;
DROP TABLE IF EXISTS public.farm_plots CASCADE;
DROP TABLE IF EXISTS public.farms CASCADE;
DROP TABLE IF EXISTS public.diseases CASCADE;
DROP TABLE IF EXISTS public.crops CASCADE;
DROP TABLE IF EXISTS public.account_provisioning CASCADE;
DROP TABLE IF EXISTS public.gari_identity_links CASCADE;
DROP TABLE IF EXISTS public.user_preferences CASCADE;
DROP TABLE IF EXISTS public.profiles CASCADE;
DROP TABLE IF EXISTS auth.users CASCADE;

-- 4. Drop Schema Functions
DROP FUNCTION IF EXISTS public.recover_stale_diagnosis_jobs(INTEGER);
DROP FUNCTION IF EXISTS public.fail_diagnosis_job(UUID, TEXT, TEXT);
DROP FUNCTION IF EXISTS public.complete_diagnosis_job(UUID, TEXT, JSONB);
DROP FUNCTION IF EXISTS public.update_diagnosis_job_heartbeat(UUID, TEXT);
DROP FUNCTION IF EXISTS public.claim_next_diagnosis_job(TEXT, INTEGER);
DROP FUNCTION IF EXISTS public.provision_user_account_idempotent(UUID, TEXT, TEXT, TEXT, TEXT);
DROP FUNCTION IF EXISTS public.protect_profile_privileged_fields();
DROP FUNCTION IF EXISTS public.handle_new_user_signup();
DROP FUNCTION IF EXISTS public.handle_updated_at();

-- 5. Drop Test Auth Helper Functions
DROP FUNCTION IF EXISTS auth.uid();
DROP FUNCTION IF EXISTS auth.role();
DROP FUNCTION IF EXISTS auth.jwt();
