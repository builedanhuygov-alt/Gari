-- ============================================================================
-- GARI AgriTech AI Platform — Supabase Migration: Idempotent Account Provisioning
-- File: supabase/migrations/20261111120003_create_idempotent_provisioning_trigger.sql
-- ============================================================================

-- 1. Automated Provisioning Trigger Function
-- Fires automatically on auth.users INSERT upon sign-up or invitation.
-- Hardened with explicit search_path to prevent search_path hijacking.
CREATE OR REPLACE FUNCTION public.handle_new_user_signup()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, auth, pg_temp
AS $$
DECLARE
    v_full_name TEXT;
    v_phone TEXT;
    v_province TEXT;
    v_account_type TEXT;
BEGIN
    -- Extract and sanitize metadata from Supabase Auth payload
    v_full_name := COALESCE(
        NEW.raw_user_meta_data->>'full_name',
        NEW.raw_user_meta_data->>'name',
        split_part(COALESCE(NEW.email, 'farmer'), '@', 1)
    );
    v_phone := COALESCE(NEW.raw_user_meta_data->>'phone', '');
    v_province := COALESCE(NEW.raw_user_meta_data->>'province', 'Lâm Đồng');
    v_account_type := COALESCE(NEW.raw_user_meta_data->>'account_type', 'farmer');

    -- Validate account_type check constraint before insert
    IF v_account_type NOT IN ('farmer', 'enterprise', 'expert', 'host_admin') THEN
        v_account_type := 'farmer';
    END IF;

    -- 1. Idempotently insert Profile
    INSERT INTO public.profiles (
        id,
        full_name,
        phone,
        province,
        account_type,
        is_admin,
        is_host_admin,
        is_expert,
        is_active,
        moderation_status
    )
    VALUES (
        NEW.id,
        v_full_name,
        v_phone,
        v_province,
        v_account_type,
        false, -- Never grant admin privileges via metadata
        false, -- Never grant host_admin via metadata
        false, -- Experts require host verification
        true,
        'clean'
    )
    ON CONFLICT (id) DO UPDATE SET
        full_name = EXCLUDED.full_name,
        phone = COALESCE(NULLIF(EXCLUDED.phone, ''), public.profiles.phone),
        updated_at = NOW();

    -- 2. Idempotently insert Preferences
    INSERT INTO public.user_preferences (user_id)
    VALUES (NEW.id)
    ON CONFLICT (user_id) DO NOTHING;

    -- 3. Idempotently register Provisioning State
    INSERT INTO public.account_provisioning (
        supabase_uid,
        status,
        retry_count,
        provisioning_metadata
    )
    VALUES (
        NEW.id,
        'PENDING',
        0,
        jsonb_build_object(
            'source', 'auth_signup_trigger',
            'email', NEW.email,
            'timestamp', NOW()
        )
    )
    ON CONFLICT (supabase_uid) DO NOTHING;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 2. Bind Trigger to auth.users
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW
    EXECUTE FUNCTION public.handle_new_user_signup();

-- 3. Dedicated Idempotent Account Provisioning RPC Function
-- Callable by trusted backend / serverless functions to replay or repair provisioning.
-- Hardened with explicit search_path.
CREATE OR REPLACE FUNCTION public.provision_user_account_idempotent(
    p_user_id UUID,
    p_full_name TEXT DEFAULT NULL,
    p_phone TEXT DEFAULT NULL,
    p_province TEXT DEFAULT 'Lâm Đồng',
    p_account_type TEXT DEFAULT 'farmer'
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, auth, pg_temp
AS $$
DECLARE
    v_clean_name TEXT;
    v_clean_type TEXT;
    v_result JSONB;
BEGIN
    v_clean_name := COALESCE(p_full_name, 'Nông dân Gari');
    v_clean_type := COALESCE(p_account_type, 'farmer');
    IF v_clean_type NOT IN ('farmer', 'enterprise', 'expert', 'host_admin') THEN
        v_clean_type := 'farmer';
    END IF;

    -- Upsert Profile
    INSERT INTO public.profiles (
        id, full_name, phone, province, account_type
    )
    VALUES (
        p_user_id, v_clean_name, p_phone, p_province, v_clean_type
    )
    ON CONFLICT (id) DO UPDATE SET
        full_name = COALESCE(EXCLUDED.full_name, public.profiles.full_name),
        phone = COALESCE(EXCLUDED.phone, public.profiles.phone),
        province = COALESCE(EXCLUDED.province, public.profiles.province),
        updated_at = NOW();

    -- Upsert Preferences
    INSERT INTO public.user_preferences (user_id)
    VALUES (p_user_id)
    ON CONFLICT (user_id) DO NOTHING;

    -- Update Provisioning Status to ACTIVE
    INSERT INTO public.account_provisioning (supabase_uid, status, retry_count)
    VALUES (p_user_id, 'ACTIVE', 0)
    ON CONFLICT (supabase_uid) DO UPDATE SET
        status = 'ACTIVE',
        updated_at = NOW();

    v_result := jsonb_build_object(
        'success', true,
        'user_id', p_user_id,
        'status', 'ACTIVE'
    );
    RETURN v_result;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

