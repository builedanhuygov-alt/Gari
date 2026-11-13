-- ============================================================================
-- GARI AgriTech AI Platform — Supabase Migration: RLS & Privilege Guards
-- File: supabase/migrations/20261111120004_create_rls_and_privilege_guards.sql
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. Enable Row Level Security (RLS) on all foundation tables
-- ----------------------------------------------------------------------------
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_preferences ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.gari_identity_links ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.account_provisioning ENABLE ROW LEVEL SECURITY;

-- ----------------------------------------------------------------------------
-- 2. Privilege Escalation Guard Trigger for public.profiles
-- Prevents ordinary authenticated users from altering privileged fields:
-- account_type, is_admin, is_host_admin, is_expert, is_active, moderation_status, feature_restrictions.
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.protect_profile_privileged_fields()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, auth, pg_temp
AS $$
DECLARE
    v_caller_role TEXT;
    v_is_service_role BOOLEAN;
BEGIN
    -- Determine execution role context securely from trusted engine, never trusting arbitrary client-controlled headers
    BEGIN
        v_caller_role := COALESCE(
            auth.role(),
            (auth.jwt() ->> 'role'),
            current_user
        );
    EXCEPTION WHEN OTHERS THEN
        v_caller_role := current_user;
    END;

    v_is_service_role := (v_caller_role IN ('service_role', 'supabase_admin', 'postgres'));

    -- If caller is NOT a privileged service role, verify privileged fields are untouched
    IF NOT v_is_service_role THEN
        IF NEW.account_type IS DISTINCT FROM OLD.account_type THEN
            RAISE EXCEPTION 'CANNOT_MODIFY_PRIVILEGED_FIELDS: Updating account_type requires host administrator authorization.'
                USING ERRCODE = '42501';
        END IF;

        IF NEW.is_admin IS DISTINCT FROM OLD.is_admin THEN
            RAISE EXCEPTION 'CANNOT_MODIFY_PRIVILEGED_FIELDS: Updating is_admin is strictly prohibited.'
                USING ERRCODE = '42501';
        END IF;

        IF NEW.is_host_admin IS DISTINCT FROM OLD.is_host_admin THEN
            RAISE EXCEPTION 'CANNOT_MODIFY_PRIVILEGED_FIELDS: Updating is_host_admin is strictly prohibited.'
                USING ERRCODE = '42501';
        END IF;

        IF NEW.is_expert IS DISTINCT FROM OLD.is_expert THEN
            RAISE EXCEPTION 'CANNOT_MODIFY_PRIVILEGED_FIELDS: Updating is_expert requires official certification review.'
                USING ERRCODE = '42501';
        END IF;

        IF NEW.is_active IS DISTINCT FROM OLD.is_active THEN
            RAISE EXCEPTION 'CANNOT_MODIFY_PRIVILEGED_FIELDS: Account active state cannot be toggled directly.'
                USING ERRCODE = '42501';
        END IF;

        IF NEW.moderation_status IS DISTINCT FROM OLD.moderation_status THEN
            RAISE EXCEPTION 'CANNOT_MODIFY_PRIVILEGED_FIELDS: Updating moderation_status is restricted to moderators.'
                USING ERRCODE = '42501';
        END IF;

        IF NEW.feature_restrictions IS DISTINCT FROM OLD.feature_restrictions THEN
            RAISE EXCEPTION 'CANNOT_MODIFY_PRIVILEGED_FIELDS: Updating feature_restrictions is strictly prohibited.'
                USING ERRCODE = '42501';
        END IF;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS trg_protect_profile_privileged_fields ON public.profiles;
CREATE TRIGGER trg_protect_profile_privileged_fields
    BEFORE UPDATE ON public.profiles
    FOR EACH ROW
    EXECUTE FUNCTION public.protect_profile_privileged_fields();

-- ----------------------------------------------------------------------------
-- 3. Row Level Security Policies: public.profiles
-- Private profile isolation: User A cannot read User B's profile.
-- ----------------------------------------------------------------------------
DROP POLICY IF EXISTS "profiles_select_own" ON public.profiles;
DROP POLICY IF EXISTS "profiles_select_authenticated" ON public.profiles;
CREATE POLICY "profiles_select_own"
    ON public.profiles
    FOR SELECT
    TO authenticated
    USING (auth.uid() = id);

DROP POLICY IF EXISTS "profiles_update_own" ON public.profiles;
CREATE POLICY "profiles_update_own"
    ON public.profiles
    FOR UPDATE
    TO authenticated
    USING (auth.uid() = id)
    WITH CHECK (auth.uid() = id);

DROP POLICY IF EXISTS "profiles_service_role" ON public.profiles;
CREATE POLICY "profiles_service_role"
    ON public.profiles
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- ----------------------------------------------------------------------------
-- 4. Row Level Security Policies: public.user_preferences
-- ----------------------------------------------------------------------------
DROP POLICY IF EXISTS "prefs_select_own" ON public.user_preferences;
CREATE POLICY "prefs_select_own"
    ON public.user_preferences
    FOR SELECT
    TO authenticated
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "prefs_update_own" ON public.user_preferences;
CREATE POLICY "prefs_update_own"
    ON public.user_preferences
    FOR UPDATE
    TO authenticated
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "prefs_service_role" ON public.user_preferences;
CREATE POLICY "prefs_service_role"
    ON public.user_preferences
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- ----------------------------------------------------------------------------
-- 5. Row Level Security Policies: public.gari_identity_links
-- CRITICAL LEAST PRIVILEGE: Ordinary users have SELECT ONLY. Zero write access.
-- ----------------------------------------------------------------------------
DROP POLICY IF EXISTS "links_select_own" ON public.gari_identity_links;
CREATE POLICY "links_select_own"
    ON public.gari_identity_links
    FOR SELECT
    TO authenticated
    USING (auth.uid() = supabase_uid);

DROP POLICY IF EXISTS "links_service_role" ON public.gari_identity_links;
CREATE POLICY "links_service_role"
    ON public.gari_identity_links
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- ----------------------------------------------------------------------------
-- 6. Row Level Security Policies: public.account_provisioning
-- CRITICAL LEAST PRIVILEGE: Ordinary users have SELECT ONLY. Zero write access.
-- ----------------------------------------------------------------------------
DROP POLICY IF EXISTS "prov_select_own" ON public.account_provisioning;
CREATE POLICY "prov_select_own"
    ON public.account_provisioning
    FOR SELECT
    TO authenticated
    USING (auth.uid() = supabase_uid);

DROP POLICY IF EXISTS "prov_service_role" ON public.account_provisioning;
CREATE POLICY "prov_service_role"
    ON public.account_provisioning
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- ----------------------------------------------------------------------------
-- 7. Column-Level Permissions (Defense in Depth)
-- Revoke blind UPDATE on profiles; grant only safe profile attributes to authenticated.
-- ----------------------------------------------------------------------------
REVOKE UPDATE ON public.profiles FROM authenticated;
GRANT UPDATE (full_name, phone, province, address, avatar_url, bio) ON public.profiles TO authenticated;
GRANT SELECT ON public.profiles TO authenticated;

-- Identity links and provisioning: Read-only for authenticated
REVOKE INSERT, UPDATE, DELETE ON public.gari_identity_links FROM authenticated;
GRANT SELECT ON public.gari_identity_links TO authenticated;

REVOKE INSERT, UPDATE, DELETE ON public.account_provisioning FROM authenticated;
GRANT SELECT ON public.account_provisioning TO authenticated;

