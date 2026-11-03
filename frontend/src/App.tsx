import { useState, useEffect, useCallback } from 'react';
import type {
  UserProfile,
  UserRole,
  Farm,
  ModelInfo,
  DashboardMetrics,
  PredictionResponse,
  NavTab,
  Theme,
  ToastMessage
} from './types';
import { Header } from './components/Header';
import { Sidebar } from './components/Sidebar';
import { MobileDrawer } from './components/MobileDrawer';
import { SearchModal } from './components/SearchModal';
import { ToastContainer } from './components/Toast';
import { OnboardingModal } from './components/OnboardingModal';
import { DashboardView } from './components/DashboardView';
import { VisionView } from './components/VisionView';
import { FarmsView } from './components/FarmsView';
import { CropLibraryView } from './components/CropLibraryView';
import { DiseaseLibraryView } from './components/DiseaseLibraryView';
import { RiskView } from './components/RiskView';
import { ExpertView } from './components/ExpertView';
import { BusinessView } from './components/BusinessView';
import { SettingsView } from './components/SettingsView';

export default function App() {
  const [activeTab, setActiveTab] = useState<NavTab>('overview');
  const [theme, setTheme] = useState<Theme>(() => {
    const saved = localStorage.getItem('gari_theme');
    if (saved === 'light' || saved === 'dark') return saved;
    return 'dark';
  });

  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState<boolean>(() => {
    return localStorage.getItem('gari_sidebar_collapsed') === 'true';
  });

  const [isMobileDrawerOpen, setIsMobileDrawerOpen] = useState<boolean>(false);
  const [isSearchOpen, setIsSearchOpen] = useState<boolean>(false);
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  const [profile, setProfile] = useState<UserProfile>(() => {
    const saved = localStorage.getItem('gari_user_profile');
    if (saved) {
      try {
        return JSON.parse(saved);
      } catch {}
    }
    return {
      name: 'Bác Hai Nông',
      role: 'FARMER',
      province: 'Lâm Đồng',
      organization: 'Hợp tác xã Nông nghiệp Sạch',
      hasCompletedOnboarding: false,
    };
  });

  const [showOnboarding, setShowOnboarding] = useState<boolean>(!profile.hasCompletedOnboarding);
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [farms, setFarms] = useState<Farm[]>([]);
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [device, setDevice] = useState<string>('cpu');
  const [selectedCropForVision, setSelectedCropForVision] = useState<string>('auto');
  const [expertPreFillData, setExpertPreFillData] = useState<any>(null);

  // Sync theme with document element
  useEffect(() => {
    if (theme === 'dark') {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
    localStorage.setItem('gari_theme', theme);
  }, [theme]);

  // Global keyboard shortcut for Command Palette (⌘K / Ctrl+K)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setIsSearchOpen(prev => !prev);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  // Sync account type from authoritative server backend
  useEffect(() => {
    const fetchAccountType = async () => {
      const token = localStorage.getItem('gari_token') || sessionStorage.getItem('gari_token');
      try {
        const headers: Record<string, string> = {};
        if (token) headers['Authorization'] = `Bearer ${token}`;
        const res = await fetch('/api/user/account-type', { headers });
        if (res.ok) {
          const data = await res.json();
          if (data.account_type) {
            setProfile(prev => ({
              ...prev,
              role: data.account_type as UserRole,
            }));
          }
        }
      } catch (err) {
        console.warn('Could not sync account type from backend:', err);
      }
    };
    fetchAccountType();
  }, []);

  const addToast = useCallback((type: 'success' | 'error' | 'info' | 'warning', title: string, message?: string) => {
    const id = Date.now().toString() + Math.random().toString(36).substring(2, 5);
    setToasts(prev => [...prev, { id, type, title, message }]);
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id));
    }, 4000);
  }, []);

  const dismissToast = (id: string) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  };

  const handleToggleTheme = () => {
    setTheme(prev => (prev === 'dark' ? 'light' : 'dark'));
  };

  const handleToggleSidebarCollapse = () => {
    setIsSidebarCollapsed(prev => {
      const next = !prev;
      localStorage.setItem('gari_sidebar_collapsed', String(next));
      return next;
    });
  };

  useEffect(() => {
    fetchInitialData();
  }, []);

  const fetchInitialData = async () => {
    // 1. Fetch Health & Models
    try {
      const healthRes = await fetch('/api/health');
      if (healthRes.ok) {
        const hData = await healthRes.json();
        setDevice(hData.device || hData.ai_engine?.device || 'cpu');
      }

      const modelsRes = await fetch('/api/models');
      if (modelsRes.ok) {
        const mData = await modelsRes.json();
        if (mData.models && Array.isArray(mData.models)) {
          const diseaseModels = mData.models
            .filter((m: ModelInfo) => m.kind === 'disease')
            .sort((a: ModelInfo, b: ModelInfo) => a.crop_name.localeCompare(b.crop_name));
          setModels(diseaseModels);
        }
      }
    } catch (e) {
      console.warn('Error fetching models:', e);
    }

    // 2. Fetch Farms
    fetchFarms();

    // 3. Fetch Dashboard Metrics
    fetchDashboardMetrics();
  };

  const fetchFarms = async () => {
    try {
      const res = await fetch('/api/farms');
      if (res.ok) {
        const data = await res.json();
        setFarms(data.farms || []);
      }
    } catch (e) {
      console.warn('Error fetching farms:', e);
    }
  };

  const fetchDashboardMetrics = async () => {
    try {
      const res = await fetch('/api/dashboard/stats');
      if (res.ok) {
        const data = await res.json();
        setMetrics(data);
      }
    } catch (e) {
      console.warn('Error fetching dashboard stats:', e);
    }
  };

  const handleUpdateRole = (role: UserRole) => {
    const updated = { ...profile, role };
    setProfile(updated);
    localStorage.setItem('gari_user_profile', JSON.stringify(updated));
    addToast('info', 'Đã chuyển phân quyền', `Đang xem giao diện dành cho ${role}.`);
  };

  const handleUpdateProfile = (updated: UserProfile) => {
    setProfile(updated);
    localStorage.setItem('gari_user_profile', JSON.stringify(updated));
    addToast('success', 'Hồ sơ đã cập nhật', 'Thông tin cá nhân đã được lưu thành công.');
  };

  const handleCompleteOnboarding = async (newProfile: UserProfile, farmData?: any) => {
    setProfile(newProfile);
    localStorage.setItem('gari_user_profile', JSON.stringify(newProfile));
    setShowOnboarding(false);
    addToast('success', 'Chào mừng đến với Gari AI Lab', 'Thiết lập ban đầu hoàn tất.');

    if (farmData) {
      try {
        await handleAddFarm(farmData);
      } catch (e) {
        console.warn('Error adding onboarding farm:', e);
      }
    }
  };

  const handleAddFarm = async (farmData: any) => {
    const res = await fetch('/api/farms', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(farmData),
    });
    if (res.ok) {
      addToast('success', 'Thêm nông trại thành công', `Hồ sơ ${farmData.name} đã được lưu.`);
      fetchFarms();
      fetchDashboardMetrics();
    } else {
      addToast('error', 'Lỗi lưu nông trại', 'Không thể tạo nông trại mới.');
    }
  };

  const handleDeleteFarm = async (farmId: number) => {
    if (!window.confirm('Bạn có chắc chắn muốn xóa nông trại này không?')) return;
    const res = await fetch(`/api/farms/${farmId}`, { method: 'DELETE' });
    if (res.ok) {
      addToast('info', 'Đã xóa nông trại', 'Hồ sơ đã được loại bỏ khỏi hệ thống.');
      fetchFarms();
      fetchDashboardMetrics();
    }
  };

  const handleSelectFarmForDiagnosis = (_farmId: number, crop: string) => {
    setSelectedCropForVision(crop);
    setActiveTab('vision');
  };

  const handleSelectCropForDiagnosis = (cropId: string) => {
    setSelectedCropForVision(cropId);
    setActiveTab('vision');
    addToast('info', 'Đã chọn cây trồng', `Mô hình ${cropId} đã được tải sẵn cho chẩn đoán.`);
  };

  const handleOpenExpertCase = (prediction: PredictionResponse) => {
    setExpertPreFillData(prediction);
    setActiveTab('expert');
    addToast('info', 'Chuyển tiếp chuyên gia', 'Thông tin chẩn đoán đã được điền sẵn vào hồ sơ ca khám.');
  };

  return (
    <div className="min-h-screen bg-[#F7F9F7] dark:bg-[#0B100D] text-[#17231C] dark:text-[#F1F5F2] flex flex-col font-sans transition-colors duration-150">
      {/* Top Application Header */}
      <Header
        profile={profile}
        onUpdateRole={handleUpdateRole}
        onOpenOnboarding={() => setShowOnboarding(true)}
        onOpenSearch={() => setIsSearchOpen(true)}
        onToggleMobileDrawer={() => setIsMobileDrawerOpen(prev => !prev)}
        activeTab={activeTab}
        device={device}
        modelsCount={models.length}
        theme={theme}
        onToggleTheme={handleToggleTheme}
      />

      <div className="flex-1 flex overflow-hidden">
        {/* Left Desktop Collapsible Sidebar */}
        <Sidebar
          activeTab={activeTab}
          onSelectTab={setActiveTab}
          farmsCount={farms.length}
          pendingExpertCount={metrics?.pending_expert_cases ?? 0}
          isCollapsed={isSidebarCollapsed}
          onToggleCollapse={handleToggleSidebarCollapse}
        />

        {/* Main Workspace Content Area */}
        <main className="flex-1 overflow-y-auto p-3.5 sm:p-5 lg:p-6 w-full">
          <div className="max-w-7xl mx-auto w-full">
            {activeTab === 'overview' && (
              <DashboardView
                metrics={metrics}
                onNavigate={setActiveTab}
                onOpenAddFarm={() => setActiveTab('farms')}
              />
            )}

            {activeTab === 'vision' && (
              <VisionView
                models={models}
                farms={farms}
                initialCropId={selectedCropForVision}
                onOpenExpertCase={handleOpenExpertCase}
                onRefreshStats={fetchDashboardMetrics}
              />
            )}

            {activeTab === 'farms' && (
              <FarmsView
                farms={farms}
                onAddFarm={handleAddFarm}
                onDeleteFarm={handleDeleteFarm}
                onSelectFarmForDiagnosis={handleSelectFarmForDiagnosis}
              />
            )}

            {activeTab === 'crops' && (
              <CropLibraryView
                models={models}
                onSelectCropForDiagnosis={handleSelectCropForDiagnosis}
              />
            )}

            {activeTab === 'diseases' && (
              <DiseaseLibraryView
                onSelectCropForDiagnosis={handleSelectCropForDiagnosis}
              />
            )}

            {activeTab === 'predict' && <RiskView />}

            {activeTab === 'expert' && (
              <ExpertView
                farms={farms}
                initialCaseData={expertPreFillData}
                onClearInitialCaseData={() => setExpertPreFillData(null)}
              />
            )}

            {activeTab === 'reports' && <BusinessView farms={farms} />}

            {activeTab === 'settings' && (
              <SettingsView
                profile={profile}
                onUpdateProfile={handleUpdateProfile}
                device={device}
                modelsCount={models.length}
              />
            )}
          </div>
        </main>
      </div>

      {/* Mobile Slide-Over Drawer Navigation */}
      <MobileDrawer
        isOpen={isMobileDrawerOpen}
        onClose={() => setIsMobileDrawerOpen(false)}
        activeTab={activeTab}
        onSelectTab={setActiveTab}
        farmsCount={farms.length}
        pendingExpertCount={metrics?.pending_expert_cases ?? 0}
      />

      {/* Global Command Palette (⌘K / Ctrl+K) */}
      <SearchModal
        isOpen={isSearchOpen}
        onClose={() => setIsSearchOpen(false)}
        onSelectTab={setActiveTab}
        models={models}
        onSelectCropForDiagnosis={handleSelectCropForDiagnosis}
      />

      {/* Subtle Toast Feedback Container */}
      <ToastContainer toasts={toasts} onDismiss={dismissToast} />

      {/* 5-Step Guided Onboarding Modal */}
      <OnboardingModal
        isOpen={showOnboarding}
        onClose={() => setShowOnboarding(false)}
        onComplete={handleCompleteOnboarding}
      />
    </div>
  );
}
