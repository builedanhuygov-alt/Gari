-- ============================================================================
-- GARI AgriTech AI Platform — Supabase Migration: User Preferences
-- File: supabase/migrations/20261111120001_create_user_preferences.sql
-- ============================================================================

-- 1. Table: public.user_preferences
-- Manages localization, timezones, notification channels, and UI appearance.
CREATE TABLE IF NOT EXISTS public.user_preferences (
    user_id UUID PRIMARY KEY REFERENCES public.profiles(id) ON DELETE CASCADE,
    language TEXT NOT NULL DEFAULT 'vi'
        CHECK (language IN ('vi', 'en')),
    timezone TEXT NOT NULL DEFAULT 'Asia/Ho_Chi_Minh',
    notification_preferences JSONB NOT NULL DEFAULT '{"email": true, "sms": false, "push": true}'::jsonb,
    theme TEXT NOT NULL DEFAULT 'system'
        CHECK (theme IN ('light', 'dark', 'system')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2. Index for preferences lookup
CREATE INDEX IF NOT EXISTS idx_user_preferences_lang ON public.user_preferences(language);

-- 3. Trigger for updated_at
DROP TRIGGER IF EXISTS trg_user_preferences_updated_at ON public.user_preferences;
CREATE TRIGGER trg_user_preferences_updated_at
    BEFORE UPDATE ON public.user_preferences
    FOR EACH ROW
    EXECUTE FUNCTION public.handle_updated_at();

