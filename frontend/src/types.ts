export type UserRole =
  | 'farmer'
  | 'cooperative'
  | 'expert'
  | 'enterprise'
  | 'FARMER'
  | 'COOPERATIVE'
  | 'AGRONOMIST'
  | 'ENTERPRISE';

export interface AccountTypeAuditEntry {
  id: number;
  previous_type: string | null;
  new_type: string;
  reason?: string;
  changed_by_user_id: number;
  created_at: string;
}

export interface AccountTypeOption {
  key: string;
  label: string;
  description: string;
}

export interface AccountTypeResponse {
  success: boolean;
  user_id: number;
  account_type: string | null;
  display_name: string | null;
  is_locked: boolean;
  is_admin: boolean;
  available_types: AccountTypeOption[];
  audit_history: AccountTypeAuditEntry[];
  message?: string;
}


export type NavTab =
  | 'overview'
  | 'vision'
  | 'farms'
  | 'crops'
  | 'diseases'
  | 'predict'
  | 'expert'
  | 'reports'
  | 'settings';

export type Theme = 'light' | 'dark';

export interface ToastMessage {
  id: string;
  type: 'success' | 'error' | 'info' | 'warning';
  title: string;
  message?: string;
}

export interface UserProfile {
  name: string;
  role: UserRole;
  phone?: string;
  province?: string;
  organization?: string;
  hasCompletedOnboarding: boolean;
}

export interface Farm {
  id: number;
  user_id?: number;
  name: string;
  location: string;
  province: string;
  area_hectare: number;
  primary_crop: string;
  variety?: string;
  soil_type?: string;
  irrigation_type?: string;
  status?: string;
  notes?: string;
  total_diagnoses?: number;
  healthy_diagnoses?: number;
  created_at?: string;
  updated_at?: string;
  diagnoses?: DiagnosisSummary[];
}

export interface DiagnosisSummary {
  id: number;
  crop_name: string;
  predicted_disease: string;
  disease_name_vi?: string;
  confidence: number;
  severity: string;
  treatment_status?: string;
  created_at?: string;
}

export interface ModelInfo {
  crop_id: string;
  crop_name: string;
  kind: string;
  arch: string;
  classes_count: number;
  classes?: string[];
  labels?: string[];
  weight_size_mb?: number;
  accuracy?: number;
  device?: string;
  is_loaded?: boolean;
}

export interface TopPrediction {
  class_id: string;
  label: string;
  disease?: string;
  name?: string;
  confidence: number;
  confidence_percent: number;
}

export interface DiseaseKnowledge {
  crop_id: string;
  crop_name: string;
  class_id: string;
  disease_name: string;
  disease_vi: string;
  scientific_name: string;
  symptoms: string;
  favorable_conditions: string;
  prevention: string[];
  field_verification: string[];
  chemical_advisory: string;
  references: string;
  is_verified: boolean;
  version: string;
}

export interface PredictionResponse {
  success: boolean;
  status: string;
  crop: string;
  crop_name?: string;
  auto_detected?: boolean;
  crop_detector_confidence?: number;
  prediction: string;
  predicted_disease?: string;
  disease_name_vi?: string;
  confidence: number;
  severity: string;
  top_predictions: TopPrediction[];
  disease_knowledge?: DiseaseKnowledge;
  model: {
    id?: string;
    name: string;
    arch: string;
    classes_count: number;
    device: string;
    was_cached?: boolean;
  };
  inference_time_ms: number;
  timestamp: string;
  saved_diagnosis_id?: number;
}

export interface DiagnosisRecord {
  id: number;
  farm_id?: number;
  farm_name?: string;
  crop_id: string;
  crop_name: string;
  predicted_disease: string;
  disease_name_vi?: string;
  confidence: number;
  confidence_percent?: number;
  severity: string;
  top_predictions?: TopPrediction[];
  model_name?: string;
  model_arch?: string;
  inference_time_ms?: number;
  device?: string;
  user_notes?: string;
  treatment_status?: string;
  is_verified_by_expert?: boolean;
  created_at: string;
}

export interface ExpertCase {
  id: number;
  diagnosis_id?: number;
  farm_id?: number;
  farm_name?: string;
  farmer_name: string;
  phone?: string;
  crop_name: string;
  suspected_disease?: string;
  symptoms_description: string;
  field_conditions?: string;
  status: 'Submitted' | 'Under review' | 'More information required' | 'Resolved';
  expert_notes?: string;
  assigned_expert?: string;
  created_at: string;
  updated_at?: string;
}

export interface RiskAlert {
  id: number;
  region: string;
  crop: string;
  disease_threat: string;
  risk_level: 'Low' | 'Moderate' | 'High' | 'Critical';
  source_type: 'OBSERVED_WEATHER' | 'RULE_BASED_MODEL' | 'ML_PREDICTION';
  temperature_c?: number;
  humidity_pct?: number;
  rainfall_mm?: number;
  recommendation: string;
  created_at: string;
}

export interface DashboardMetrics {
  farms_total: number;
  total_hectares: number;
  diagnoses_total: number;
  healthy_rate_percent: number;
  disease_distribution: { disease: string; count: number }[];
  crop_distribution: { crop: string; count: number }[];
  pending_expert_cases: number;
  recent_diagnoses: DiagnosisRecord[];
  recent_alerts: RiskAlert[];
  timestamp: string;
}
