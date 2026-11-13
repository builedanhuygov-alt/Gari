-- ============================================================================
-- GARI AgriTech AI Platform — Supabase Migration: Base Schema & Profiles
-- File: supabase/migrations/20261111120000_create_base_schema_and_profiles.sql
-- ============================================================================

-- 1. Enable Required Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 2. Mock auth.users table for local standalone testing if not in managed Supabase
CREATE SCHEMA IF NOT EXISTS auth;
CREATE TABLE IF NOT EXISTS auth.users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE,
    raw_user_meta_data JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 3. Universal updated_at Timestamp Handler
-- Hardened with explicit search_path to prevent search_path hijacking
CREATE OR REPLACE FUNCTION public.handle_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

-- 4. Table: public.profiles
-- Stores user profile and RBAC authorization state.
CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    full_name TEXT NOT NULL,
    phone TEXT,
    province TEXT DEFAULT 'Lâm Đồng',
    address TEXT,
    avatar_url TEXT,
    bio TEXT,
    account_type TEXT NOT NULL DEFAULT 'farmer'
        CHECK (account_type IN ('farmer', 'enterprise', 'expert', 'host_admin')),
    is_admin BOOLEAN NOT NULL DEFAULT false,
    is_host_admin BOOLEAN NOT NULL DEFAULT false,
    is_expert BOOLEAN NOT NULL DEFAULT false,
    is_active BOOLEAN NOT NULL DEFAULT true,
    moderation_status TEXT NOT NULL DEFAULT 'clean'
        CHECK (moderation_status IN ('clean', 'flagged', 'suspended', 'under_review')),
    feature_restrictions TEXT DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 5. Indexes for Profiles
CREATE INDEX IF NOT EXISTS idx_profiles_phone ON public.profiles(phone);
CREATE INDEX IF NOT EXISTS idx_profiles_account_type ON public.profiles(account_type);
CREATE INDEX IF NOT EXISTS idx_profiles_is_admin ON public.profiles(is_admin) WHERE is_admin = true;
CREATE INDEX IF NOT EXISTS idx_profiles_moderation ON public.profiles(moderation_status);

-- 6. Trigger for updated_at
DROP TRIGGER IF EXISTS trg_profiles_updated_at ON public.profiles;
CREATE TRIGGER trg_profiles_updated_at
    BEFORE UPDATE ON public.profiles
    FOR EACH ROW
    EXECUTE FUNCTION public.handle_updated_at();

