-- ============================================================================
-- GARI AgriTech AI Platform — Supabase Migration: Hybrid Cloud & AI Worker Queue
-- File: supabase/migrations/20261111120005_create_hybrid_cloud_and_ai_worker_queue.sql
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. Table: public.farms (Farms & Landholdings)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.farms (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    location TEXT,
    province TEXT DEFAULT 'Lâm Đồng',
    area_ha NUMERIC(10, 2) DEFAULT 1.0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_farms_user ON public.farms(user_id);

DROP TRIGGER IF EXISTS trg_farms_updated_at ON public.farms;
CREATE TRIGGER trg_farms_updated_at
    BEFORE UPDATE ON public.farms
    FOR EACH ROW
    EXECUTE FUNCTION public.handle_updated_at();

-- ----------------------------------------------------------------------------
-- 2. Table: public.farm_plots (Individual Plots / Zones)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.farm_plots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    farm_id UUID NOT NULL REFERENCES public.farms(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    plot_name TEXT NOT NULL,
    crop_type TEXT NOT NULL DEFAULT 'coffee',
    planting_date DATE,
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'fallow', 'harvested', 'quarantine')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_farm_plots_farm ON public.farm_plots(farm_id);
CREATE INDEX IF NOT EXISTS idx_farm_plots_user ON public.farm_plots(user_id);

DROP TRIGGER IF EXISTS trg_farm_plots_updated_at ON public.farm_plots;
CREATE TRIGGER trg_farm_plots_updated_at
    BEFORE UPDATE ON public.farm_plots
    FOR EACH ROW
    EXECUTE FUNCTION public.handle_updated_at();

-- ----------------------------------------------------------------------------
-- 3. Table: public.cultivation_tasks (Farming Calendar & Operational Tasks)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.cultivation_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    farm_id UUID REFERENCES public.farms(id) ON DELETE SET NULL,
    plot_id UUID REFERENCES public.farm_plots(id) ON DELETE SET NULL,
    task_title TEXT NOT NULL,
    task_type TEXT NOT NULL DEFAULT 'general'
        CHECK (task_type IN ('general', 'fertilizing', 'watering', 'pesticide', 'pruning', 'harvesting', 'scouting')),
    due_date DATE NOT NULL DEFAULT CURRENT_DATE,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'in_progress', 'completed', 'cancelled')),
    priority TEXT NOT NULL DEFAULT 'medium'
        CHECK (priority IN ('low', 'medium', 'high', 'urgent')),
    notes TEXT DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tasks_user_due ON public.cultivation_tasks(user_id, due_date);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON public.cultivation_tasks(status);

DROP TRIGGER IF EXISTS trg_tasks_updated_at ON public.cultivation_tasks;
CREATE TRIGGER trg_tasks_updated_at
    BEFORE UPDATE ON public.cultivation_tasks
    FOR EACH ROW
    EXECUTE FUNCTION public.handle_updated_at();

-- ----------------------------------------------------------------------------
-- 4. Table: public.crops (Reference Knowledge Library)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.crops (
    id TEXT PRIMARY KEY,
    name_vi TEXT NOT NULL,
    name_en TEXT,
    scientific_name TEXT,
    category TEXT DEFAULT 'vegetables',
    description TEXT,
    care_guide TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ----------------------------------------------------------------------------
-- 5. Table: public.diseases (Reference Knowledge Library)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.diseases (
    id TEXT PRIMARY KEY,
    crop_id TEXT REFERENCES public.crops(id) ON DELETE CASCADE,
    name_vi TEXT NOT NULL,
    name_en TEXT,
    pathogen TEXT,
    symptoms TEXT,
    treatment TEXT,
    prevention TEXT,
    severity TEXT DEFAULT 'medium' CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ----------------------------------------------------------------------------
-- 6. Table: public.diagnoses (Diagnosis History)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.diagnoses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    farm_id UUID REFERENCES public.farms(id) ON DELETE SET NULL,
    plot_id UUID REFERENCES public.farm_plots(id) ON DELETE SET NULL,
    crop_type TEXT NOT NULL,
    disease_name TEXT NOT NULL,
    confidence NUMERIC(5, 4) DEFAULT 0.9500,
    image_url TEXT,
    treatment_summary TEXT,
    diagnosis_metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_diagnoses_user_created ON public.diagnoses(user_id, created_at DESC);

-- ----------------------------------------------------------------------------
-- 7. Table: public.notifications (User Alerts & Reminders)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    is_read BOOLEAN NOT NULL DEFAULT false,
    type TEXT NOT NULL DEFAULT 'info'
        CHECK (type IN ('info', 'alert', 'diagnosis_ready', 'weather_warning', 'task_reminder')),
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_notifications_user_unread ON public.notifications(user_id, is_read, created_at DESC);

-- ----------------------------------------------------------------------------
-- 8. Table: public.diagnosis_jobs (Durable AI Worker Queue)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.diagnosis_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    farm_id UUID REFERENCES public.farms(id) ON DELETE SET NULL,
    plot_id UUID REFERENCES public.farm_plots(id) ON DELETE SET NULL,
    crop_type TEXT NOT NULL DEFAULT 'auto',
    storage_path TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued', 'processing', 'completed', 'failed')),
    retry_count INTEGER NOT NULL DEFAULT 0,
    worker_id TEXT,
    heartbeat_at TIMESTAMPTZ,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    result JSONB,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_diagnosis_jobs_status_created 
    ON public.diagnosis_jobs(status, created_at) 
    WHERE status = 'queued';

CREATE INDEX IF NOT EXISTS idx_diagnosis_jobs_user 
    ON public.diagnosis_jobs(user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_diagnosis_jobs_heartbeat 
    ON public.diagnosis_jobs(status, heartbeat_at) 
    WHERE status = 'processing';

DROP TRIGGER IF EXISTS trg_diagnosis_jobs_updated_at ON public.diagnosis_jobs;
CREATE TRIGGER trg_diagnosis_jobs_updated_at
    BEFORE UPDATE ON public.diagnosis_jobs
    FOR EACH ROW
    EXECUTE FUNCTION public.handle_updated_at();

-- ----------------------------------------------------------------------------
-- 9. Row Level Security Policies
-- ----------------------------------------------------------------------------
ALTER TABLE public.farms ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.farm_plots ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.cultivation_tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.crops ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.diseases ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.diagnoses ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.notifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.diagnosis_jobs ENABLE ROW LEVEL SECURITY;

-- Farms Policies
DROP POLICY IF EXISTS "farms_select_own" ON public.farms;
CREATE POLICY "farms_select_own" ON public.farms FOR SELECT TO authenticated USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "farms_insert_own" ON public.farms;
CREATE POLICY "farms_insert_own" ON public.farms FOR INSERT TO authenticated WITH CHECK (auth.uid() = user_id);
DROP POLICY IF EXISTS "farms_update_own" ON public.farms;
CREATE POLICY "farms_update_own" ON public.farms FOR UPDATE TO authenticated USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);
DROP POLICY IF EXISTS "farms_delete_own" ON public.farms;
CREATE POLICY "farms_delete_own" ON public.farms FOR DELETE TO authenticated USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "farms_service_role" ON public.farms;
CREATE POLICY "farms_service_role" ON public.farms FOR ALL TO service_role USING (true) WITH CHECK (true);

-- Farm Plots Policies
DROP POLICY IF EXISTS "plots_select_own" ON public.farm_plots;
CREATE POLICY "plots_select_own" ON public.farm_plots FOR SELECT TO authenticated USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "plots_insert_own" ON public.farm_plots;
CREATE POLICY "plots_insert_own" ON public.farm_plots FOR INSERT TO authenticated WITH CHECK (auth.uid() = user_id);
DROP POLICY IF EXISTS "plots_update_own" ON public.farm_plots;
CREATE POLICY "plots_update_own" ON public.farm_plots FOR UPDATE TO authenticated USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);
DROP POLICY IF EXISTS "plots_delete_own" ON public.farm_plots;
CREATE POLICY "plots_delete_own" ON public.farm_plots FOR DELETE TO authenticated USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "plots_service_role" ON public.farm_plots;
CREATE POLICY "plots_service_role" ON public.farm_plots FOR ALL TO service_role USING (true) WITH CHECK (true);

-- Cultivation Tasks Policies
DROP POLICY IF EXISTS "tasks_select_own" ON public.cultivation_tasks;
CREATE POLICY "tasks_select_own" ON public.cultivation_tasks FOR SELECT TO authenticated USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "tasks_insert_own" ON public.cultivation_tasks;
CREATE POLICY "tasks_insert_own" ON public.cultivation_tasks FOR INSERT TO authenticated WITH CHECK (auth.uid() = user_id);
DROP POLICY IF EXISTS "tasks_update_own" ON public.cultivation_tasks;
CREATE POLICY "tasks_update_own" ON public.cultivation_tasks FOR UPDATE TO authenticated USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);
DROP POLICY IF EXISTS "tasks_delete_own" ON public.cultivation_tasks;
CREATE POLICY "tasks_delete_own" ON public.cultivation_tasks FOR DELETE TO authenticated USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "tasks_service_role" ON public.cultivation_tasks;
CREATE POLICY "tasks_service_role" ON public.cultivation_tasks FOR ALL TO service_role USING (true) WITH CHECK (true);

-- Crops & Diseases Public Reference Library (Read-only for all, write for service_role)
DROP POLICY IF EXISTS "crops_public_read" ON public.crops;
CREATE POLICY "crops_public_read" ON public.crops FOR SELECT TO anon, authenticated USING (true);
DROP POLICY IF EXISTS "crops_service_role" ON public.crops;
CREATE POLICY "crops_service_role" ON public.crops FOR ALL TO service_role USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "diseases_public_read" ON public.diseases;
CREATE POLICY "diseases_public_read" ON public.diseases FOR SELECT TO anon, authenticated USING (true);
DROP POLICY IF EXISTS "diseases_service_role" ON public.diseases;
CREATE POLICY "diseases_service_role" ON public.diseases FOR ALL TO service_role USING (true) WITH CHECK (true);

-- Diagnoses History Policies
DROP POLICY IF EXISTS "diagnoses_select_own" ON public.diagnoses;
CREATE POLICY "diagnoses_select_own" ON public.diagnoses FOR SELECT TO authenticated USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "diagnoses_insert_own" ON public.diagnoses;
CREATE POLICY "diagnoses_insert_own" ON public.diagnoses FOR INSERT TO authenticated WITH CHECK (auth.uid() = user_id);
DROP POLICY IF EXISTS "diagnoses_delete_own" ON public.diagnoses;
CREATE POLICY "diagnoses_delete_own" ON public.diagnoses FOR DELETE TO authenticated USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "diagnoses_service_role" ON public.diagnoses;
CREATE POLICY "diagnoses_service_role" ON public.diagnoses FOR ALL TO service_role USING (true) WITH CHECK (true);

-- Notifications Policies
DROP POLICY IF EXISTS "notif_select_own" ON public.notifications;
CREATE POLICY "notif_select_own" ON public.notifications FOR SELECT TO authenticated USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "notif_update_own" ON public.notifications;
CREATE POLICY "notif_update_own" ON public.notifications FOR UPDATE TO authenticated USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);
DROP POLICY IF EXISTS "notif_service_role" ON public.notifications;
CREATE POLICY "notif_service_role" ON public.notifications FOR ALL TO service_role USING (true) WITH CHECK (true);

-- Diagnosis Jobs Queue Policies
DROP POLICY IF EXISTS "jobs_select_own" ON public.diagnosis_jobs;
CREATE POLICY "jobs_select_own" ON public.diagnosis_jobs FOR SELECT TO authenticated USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "jobs_insert_own" ON public.diagnosis_jobs;
CREATE POLICY "jobs_insert_own" ON public.diagnosis_jobs FOR INSERT TO authenticated WITH CHECK (auth.uid() = user_id);
DROP POLICY IF EXISTS "jobs_service_role" ON public.diagnosis_jobs;
CREATE POLICY "jobs_service_role" ON public.diagnosis_jobs FOR ALL TO service_role USING (true) WITH CHECK (true);

-- ----------------------------------------------------------------------------
-- 10. AI Worker Stored Procedures (Atomic Queue Claiming & Recovery)
-- ----------------------------------------------------------------------------

-- Function 1: Claim next queued job atomically (FOR UPDATE SKIP LOCKED)
CREATE OR REPLACE FUNCTION public.claim_next_diagnosis_job(
    p_worker_id TEXT,
    p_lock_duration_seconds INTEGER DEFAULT 120
)
RETURNS TABLE (
    job_id UUID,
    job_user_id UUID,
    job_storage_path TEXT,
    job_crop_type TEXT,
    job_retry_count INTEGER
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, auth, pg_temp
AS $$
DECLARE
    v_job_id UUID;
BEGIN
    -- 1. Identify and lock the oldest queued job without race condition
    SELECT id INTO v_job_id
    FROM public.diagnosis_jobs
    WHERE status = 'queued'
    ORDER BY created_at ASC
    LIMIT 1
    FOR UPDATE SKIP LOCKED;

    -- 2. If a job is claimed, transition state to processing
    IF v_job_id IS NOT NULL THEN
        UPDATE public.diagnosis_jobs
        SET status = 'processing',
            worker_id = p_worker_id,
            heartbeat_at = NOW(),
            started_at = NOW(),
            updated_at = NOW()
        WHERE id = v_job_id;

        RETURN QUERY
        SELECT j.id, j.user_id, j.storage_path, j.crop_type, j.retry_count
        FROM public.diagnosis_jobs j
        WHERE j.id = v_job_id;
    END IF;
END;
$$;

-- Function 2: Heartbeat updater for active worker
CREATE OR REPLACE FUNCTION public.update_diagnosis_job_heartbeat(
    p_job_id UUID,
    p_worker_id TEXT
)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, auth, pg_temp
AS $$
BEGIN
    UPDATE public.diagnosis_jobs
    SET heartbeat_at = NOW(),
        updated_at = NOW()
    WHERE id = p_job_id 
      AND worker_id = p_worker_id 
      AND status = 'processing';
    RETURN FOUND;
END;
$$;

-- Function 3: Complete diagnosis job with result payload
CREATE OR REPLACE FUNCTION public.complete_diagnosis_job(
    p_job_id UUID,
    p_worker_id TEXT,
    p_result JSONB
)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, auth, pg_temp
AS $$
DECLARE
    v_user_id UUID;
    v_farm_id UUID;
    v_plot_id UUID;
    v_crop TEXT;
    v_disease TEXT;
    v_conf NUMERIC;
    v_img TEXT;
    v_treat TEXT;
BEGIN
    UPDATE public.diagnosis_jobs
    SET status = 'completed',
        completed_at = NOW(),
        result = p_result,
        updated_at = NOW()
    WHERE id = p_job_id 
      AND worker_id = p_worker_id 
      AND status = 'processing'
    RETURNING user_id, farm_id, plot_id, crop_type, storage_path
    INTO v_user_id, v_farm_id, v_plot_id, v_crop, v_img;

    IF NOT FOUND THEN
        RETURN FALSE;
    END IF;

    -- Extract result fields
    v_disease := COALESCE(p_result->>'disease_name', 'Bệnh cây trồng');
    v_conf := COALESCE((p_result->>'confidence')::numeric, 0.95);
    v_treat := COALESCE(p_result->>'treatment', 'Tham khảo chuyên gia.');

    -- Automatically archive into diagnoses history table
    INSERT INTO public.diagnoses (
        user_id, farm_id, plot_id, crop_type, disease_name,
        confidence, image_url, treatment_summary, diagnosis_metadata
    ) VALUES (
        v_user_id, v_farm_id, v_plot_id, v_crop, v_disease,
        v_conf, v_img, v_treat, p_result
    );

    -- Insert notification for user
    INSERT INTO public.notifications (
        user_id, title, body, type, metadata
    ) VALUES (
        v_user_id,
        'Chẩn đoán AI đã hoàn tất',
        'Cây trồng ' || v_crop || ': Phát hiện ' || v_disease,
        'diagnosis_ready',
        jsonb_build_object('job_id', p_job_id, 'disease', v_disease)
    );

    RETURN TRUE;
END;
$$;

-- Function 4: Fail diagnosis job with error message
CREATE OR REPLACE FUNCTION public.fail_diagnosis_job(
    p_job_id UUID,
    p_worker_id TEXT,
    p_error TEXT
)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, auth, pg_temp
AS $$
BEGIN
    UPDATE public.diagnosis_jobs
    SET status = 'failed',
        error_message = p_error,
        completed_at = NOW(),
        updated_at = NOW()
    WHERE id = p_job_id 
      AND worker_id = p_worker_id 
      AND status = 'processing';
    RETURN FOUND;
END;
$$;

-- Function 5: Recover stale jobs with expired heartbeat (> 120s)
CREATE OR REPLACE FUNCTION public.recover_stale_diagnosis_jobs(
    p_stale_seconds INTEGER DEFAULT 120
)
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, auth, pg_temp
AS $$
DECLARE
    v_recovered_count INTEGER := 0;
BEGIN
    WITH stale_jobs AS (
        SELECT id, retry_count
        FROM public.diagnosis_jobs
        WHERE status = 'processing'
          AND heartbeat_at < (NOW() - (p_stale_seconds || ' seconds')::interval)
        FOR UPDATE SKIP LOCKED
    )
    UPDATE public.diagnosis_jobs j
    SET status = CASE 
            WHEN s.retry_count >= 3 THEN 'failed'
            ELSE 'queued'
        END,
        error_message = CASE 
            WHEN s.retry_count >= 3 THEN 'Max retries exceeded due to worker disconnect.'
            ELSE 'Worker heartbeat timed out. Automatically re-enqueued.'
        END,
        retry_count = s.retry_count + 1,
        worker_id = NULL,
        heartbeat_at = NULL,
        updated_at = NOW()
    FROM stale_jobs s
    WHERE j.id = s.id;

    GET DIAGNOSTICS v_recovered_count = ROW_COUNT;
    RETURN v_recovered_count;
END;
$$;
