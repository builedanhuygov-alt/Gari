-- ============================================================================
-- GARI AgriTech AI Platform — Supabase Migration: Identity Bridge & Provisioning
-- File: supabase/migrations/20261111120002_create_identity_bridge_and_provisioning.sql
-- ============================================================================

-- 1. Table: public.gari_identity_links
-- Authoritative bridge mapping a Supabase UUID to a legacy SQLite integer ID.
-- Ensures strict 1:1 mapping with UNIQUE constraints on both keys.
CREATE TABLE IF NOT EXISTS public.gari_identity_links (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    supabase_uid UUID UNIQUE NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    sqlite_user_id INTEGER UNIQUE NOT NULL,
    status TEXT NOT NULL DEFAULT 'ACTIVE'
        CHECK (status IN ('ACTIVE', 'SUSPENDED', 'PENDING_MIGRATION')),
    linked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for bidirectional 1:1 lookups
CREATE INDEX IF NOT EXISTS idx_identity_links_sub ON public.gari_identity_links(supabase_uid);
CREATE INDEX IF NOT EXISTS idx_identity_links_sqlite ON public.gari_identity_links(sqlite_user_id);

-- Trigger for updated_at
DROP TRIGGER IF EXISTS trg_gari_identity_links_updated_at ON public.gari_identity_links;
CREATE TRIGGER trg_gari_identity_links_updated_at
    BEFORE UPDATE ON public.gari_identity_links
    FOR EACH ROW
    EXECUTE FUNCTION public.handle_updated_at();

-- 2. Table: public.account_provisioning
-- Tracks asynchronous or synchronous onboarding state machine between Supabase and the host core.
CREATE TABLE IF NOT EXISTS public.account_provisioning (
    supabase_uid UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'PENDING'
        CHECK (status IN ('PENDING', 'ACTIVE', 'FAILED')),
    error_code TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    provisioning_metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for pending retry queues
CREATE INDEX IF NOT EXISTS idx_account_provisioning_status ON public.account_provisioning(status) WHERE status = 'PENDING';

-- Trigger for updated_at
DROP TRIGGER IF EXISTS trg_account_provisioning_updated_at ON public.account_provisioning;
CREATE TRIGGER trg_account_provisioning_updated_at
    BEFORE UPDATE ON public.account_provisioning
    FOR EACH ROW
    EXECUTE FUNCTION public.handle_updated_at();

