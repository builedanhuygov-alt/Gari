import React, { useState } from 'react';
import {
  Menu,
  Search,
  Sun,
  Moon,
  Bell,
  CheckCircle2,
  ExternalLink,
  ChevronDown,
  UserCheck,
  Building2,
  Leaf,
  Briefcase,
  HelpCircle,
  Lock,
  ShieldCheck,
  AlertCircle,
  X
} from 'lucide-react';
import type { UserRole, UserProfile, NavTab, Theme } from '../types';

interface HeaderProps {
  profile: UserProfile;
  onUpdateRole: (role: UserRole) => void;
  onOpenOnboarding: () => void;
  onOpenSearch: () => void;
  onToggleMobileDrawer: () => void;
  activeTab: NavTab;
  device: string;
  modelsCount: number;
  theme: Theme;
  onToggleTheme: () => void;
}

type CanonicalAccountType = 'farmer' | 'cooperative' | 'expert' | 'enterprise';

const normalizeToCanonical = (r?: string): CanonicalAccountType => {
  const s = (r || '').toLowerCase().trim();
  if (s === 'cooperative' || s === 'hợp tác xã') return 'cooperative';
  if (s === 'agronomist' || s === 'expert' || s === 'chuyên gia bvtv' || s === 'chuyên gia' || s === 'đơn vị dịch vụ nông nghiệp') return 'expert';
  if (s === 'enterprise' || s === 'doanh nghiệp') return 'enterprise';
  return 'farmer';
};

export const Header: React.FC<HeaderProps> = ({
  profile,
  onUpdateRole,
  onOpenOnboarding,
  onOpenSearch,
  onToggleMobileDrawer,
  activeTab,
  device,
  modelsCount,
  theme,
  onToggleTheme,
}) => {
  const [showRoleMenu, setShowRoleMenu] = useState(false);
  const [showNotifications, setShowNotifications] = useState(false);
  const [pendingChangeType, setPendingChangeType] = useState<CanonicalAccountType | null>(null);
  const [changeReason, setChangeReason] = useState<string>('');
  const [isSubmittingChange, setIsSubmittingChange] = useState<boolean>(false);
  const [changeError, setChangeError] = useState<string | null>(null);

  const tabTitles: Record<NavTab, { section: string; title: string }> = {
    overview: { section: 'Workspace', title: 'Tổng quan' },
    vision: { section: 'AI Engine', title: 'Chẩn đoán AI' },
    farms: { section: 'Operations', title: 'Nông trại của tôi' },
    crops: { section: 'Knowledge Base', title: 'Thư viện cây trồng' },
    diseases: { section: 'Knowledge Base', title: 'Thư viện bệnh lý' },
    predict: { section: 'Monitoring', title: 'Giám sát rủi ro' },
    expert: { section: 'Advisory', title: 'Hỗ trợ chuyên gia' },
    reports: { section: 'Analytics', title: 'Báo cáo & HTX' },
    settings: { section: 'System', title: 'Cài đặt & Hồ sơ' },
  };

  const accountTypeDefinitions: Record<
    CanonicalAccountType,
    { label: string; icon: any; color: string; description: string }
  > = {
    farmer: {
      label: 'Nông Hộ Cá Thể',
      icon: UserCheck,
      color: 'text-emerald-600 dark:text-emerald-400 bg-emerald-500/10',
      description: 'Dành cho nông dân cá thể, chủ ruộng và người làm vườn.',
    },
    cooperative: {
      label: 'Hợp Tác Xã',
      icon: Building2,
      color: 'text-teal-600 dark:text-teal-400 bg-teal-500/10',
      description: 'Dành cho Hợp tác xã, ban quản lý vùng trồng tập trung.',
    },
    expert: {
      label: 'Chuyên Gia BVTV',
      icon: Leaf,
      color: 'text-cyan-600 dark:text-cyan-400 bg-cyan-500/10',
      description: 'Dành cho kỹ sư nông học & chuyên gia chẩn đoán bảo vệ thực vật.',
    },
    enterprise: {
      label: 'Doanh Nghiệp',
      icon: Briefcase,
      color: 'text-indigo-600 dark:text-indigo-400 bg-indigo-500/10',
      description: 'Dành cho doanh nghiệp chế biến xuất khẩu & chuỗi vật tư BVTV.',
    },
  };

  const currentCanonical = normalizeToCanonical(profile.role);
  const currentRole = accountTypeDefinitions[currentCanonical] || accountTypeDefinitions.farmer;
  const RoleIcon = currentRole.icon;
  const currentTabInfo = tabTitles[activeTab] || { section: 'Workspace', title: 'Tổng quan' };

  // Handle Safe Confirmation Flow for Account Type Change
  const handleConfirmAccountTypeChange = async () => {
    if (!pendingChangeType) return;
    setIsSubmittingChange(true);
    setChangeError(null);

    const token = localStorage.getItem('gari_token') || sessionStorage.getItem('gari_token');
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    try {
      const res = await fetch('/api/user/account-type/change', {
        method: 'POST',
        headers,
        body: JSON.stringify({
          account_type: pendingChangeType,
          confirm: true,
          reason: changeReason.trim() || 'Xác nhận thay đổi loại tài khoản qua giao diện người dùng',
        }),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || 'Không thể thay đổi loại tài khoản.');
      }

      onUpdateRole(pendingChangeType as UserRole);
      setPendingChangeType(null);
      setChangeReason('');
      setShowRoleMenu(false);
    } catch (err: any) {
      setChangeError(err.message || 'Lỗi khi kết nối đến máy chủ.');
    } finally {
      setIsSubmittingChange(false);
    }
  };

  return (
    <>
      <header className="h-14 border-b border-[#E5EBE6] dark:border-[#202C23] bg-white/90 dark:bg-[#121914]/90 backdrop-blur-md sticky top-0 z-40 px-3 sm:px-6 flex items-center justify-between transition-colors">
        {/* Left: Mobile Toggle & Breadcrumbs */}
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={onToggleMobileDrawer}
            className="lg:hidden p-1.5 rounded-lg text-slate-500 hover:text-slate-700 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800"
            aria-label="Open navigation menu"
          >
            <Menu className="w-5 h-5" />
          </button>

          {/* Clean Breadcrumb Hierarchy */}
          <nav aria-label="Breadcrumb" className="flex items-center gap-2 text-xs">
            <span className="font-semibold text-slate-400 dark:text-slate-500 hidden sm:inline">
              GARI
            </span>
            <span className="text-slate-300 dark:text-slate-600 hidden sm:inline">/</span>
            <span className="text-slate-500 dark:text-slate-400 hidden md:inline">
              {currentTabInfo.section}
            </span>
            <span className="text-slate-300 dark:text-slate-600 hidden md:inline">/</span>
            <span className="font-bold text-slate-900 dark:text-slate-100">
              {currentTabInfo.title}
            </span>
          </nav>
        </div>

        {/* Middle: Command Search Bar Entry Point */}
        <div className="flex-1 max-w-md mx-4 hidden md:block">
          <button
            type="button"
            onClick={onOpenSearch}
            className="w-full flex items-center justify-between px-3 py-1.5 text-xs text-slate-400 bg-[#F4F7F4] dark:bg-[#162019] hover:bg-[#EAEFEA] dark:hover:bg-[#1B271F] border border-[#E5EBE6] dark:border-[#202C23] rounded-lg transition group"
          >
            <div className="flex items-center gap-2">
              <Search className="w-3.5 h-3.5 text-slate-400 group-hover:text-emerald-500 transition" />
              <span className="text-slate-500 dark:text-slate-400">Tìm kiếm cây trồng, bệnh lý, nông trại...</span>
            </div>
            <div className="flex items-center gap-1 font-mono text-[10px] bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 px-1.5 py-0.5 rounded text-slate-500 dark:text-slate-400">
              <span>⌘K</span>
            </div>
          </button>
        </div>

        {/* Right: Actions, System Metrics & User Role */}
        <div className="flex items-center gap-1 sm:gap-2">
          {/* Models Status Pill */}
          <div
            className="hidden xl:flex items-center gap-1.5 text-[11px] bg-[#F4F7F4] dark:bg-[#162019] border border-[#E5EBE6] dark:border-[#202C23] px-2.5 py-1 rounded-full text-slate-600 dark:text-slate-400"
            title="Local AI Models Ready"
          >
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
            <span className="font-semibold text-emerald-700 dark:text-emerald-400 font-mono">
              {modelsCount} Models
            </span>
            <span className="text-slate-300 dark:text-slate-600">•</span>
            <span className="uppercase text-[10px] font-mono font-medium">{device}</span>
          </div>

          {/* Theme Toggle Button */}
          <button
            type="button"
            onClick={onToggleTheme}
            className="p-1.5 rounded-lg text-slate-500 hover:text-slate-700 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-[#1A241C] transition"
            aria-label="Toggle Theme"
          >
            {theme === 'dark' ? (
              <Sun className="w-4 h-4 text-amber-400" />
            ) : (
              <Moon className="w-4 h-4 text-slate-600" />
            )}
          </button>

          {/* Notification Bell with Dropdown */}
          <div className="relative">
            <button
              type="button"
              onClick={() => setShowNotifications(!showNotifications)}
              className="p-1.5 rounded-lg text-slate-500 hover:text-slate-700 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-[#1A241C] transition relative"
              title="Thông báo hệ thống"
            >
              <Bell className="w-4 h-4" />
              <span className="absolute top-1 right-1 w-1.5 h-1.5 bg-emerald-500 rounded-full"></span>
            </button>

            {showNotifications && (
              <div className="absolute right-0 mt-2 w-72 bg-white dark:bg-[#141C16] border border-[#E5EBE6] dark:border-[#243328] rounded-xl shadow-xl p-3 z-50 text-xs animate-fadeIn">
                <div className="flex items-center justify-between pb-2 mb-2 border-b border-slate-100 dark:border-slate-800">
                  <span className="font-bold text-slate-900 dark:text-slate-100">Thông báo vận hành</span>
                  <span className="text-[10px] text-emerald-600 dark:text-emerald-400 font-semibold">Tất cả đã đọc</span>
                </div>
                <div className="space-y-2">
                  <div className="p-2 bg-slate-50 dark:bg-[#19231B] rounded-lg">
                    <div className="font-semibold text-slate-800 dark:text-slate-200 flex items-center gap-1.5">
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
                      44 Mô hình ConvNeXt sẵn sàng
                    </div>
                    <div className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">
                      Hệ thống AI cục bộ đã nạp đầy đủ trọng số kiểm định.
                    </div>
                  </div>
                  <div className="p-2 bg-slate-50 dark:bg-[#19231B] rounded-lg">
                    <div className="font-semibold text-slate-800 dark:text-slate-200">
                      Cảnh báo thời tiết nông nghiệp
                    </div>
                    <div className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">
                      Độ ẩm cao tại Lâm Đồng có nguy cơ bùng phát mốc sương cà chua.
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Onboarding Guide Shortcut */}
          <button
            type="button"
            onClick={onOpenOnboarding}
            className="hidden sm:flex items-center gap-1 text-xs text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 px-2 py-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-[#1A241C] transition"
            title="Hướng dẫn bắt đầu"
          >
            <HelpCircle className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
            <span className="hidden lg:inline">Trợ giúp</span>
          </button>

          {/* API Docs Link */}
          <a
            href="/docs"
            target="_blank"
            rel="noreferrer"
            className="hidden md:flex items-center gap-1 text-xs text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200 px-2 py-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-[#1A241C] transition"
            title="FastAPI Swagger Documentation"
          >
            <span>API Docs</span>
            <ExternalLink className="w-3 h-3 opacity-60" />
          </a>

          {/* User Account Type Dropdown Menu (Enforces Exactly 1 Active Type) */}
          <div className="relative">
            <button
              type="button"
              onClick={() => setShowRoleMenu(!showRoleMenu)}
              className="flex items-center gap-2 pl-2 pr-1.5 py-1 rounded-lg border border-[#E5EBE6] dark:border-[#202C23] bg-[#F7F9F7] dark:bg-[#162019] hover:bg-[#EAEFEA] dark:hover:bg-[#1B271F] transition text-left"
              aria-label="Account Type Profile Menu"
            >
              <div className={`w-5 h-5 rounded-md flex items-center justify-center ${currentRole.color}`}>
                <RoleIcon className="w-3 h-3" />
              </div>
              <div className="hidden sm:block text-left">
                <div className="text-[11px] font-bold text-slate-900 dark:text-slate-100 leading-none">
                  {profile.name}
                </div>
                <div className="text-[9px] text-slate-500 dark:text-slate-400 leading-tight flex items-center gap-1 mt-0.5">
                  <span>{currentRole.label}</span>
                  <Lock className="w-2.5 h-2.5 text-slate-400" />
                </div>
              </div>
              <ChevronDown className="w-3 h-3 text-slate-400" />
            </button>

            {showRoleMenu && (
              <div className="absolute right-0 mt-2 w-64 bg-white dark:bg-[#141C16] border border-[#E5EBE6] dark:border-[#243328] rounded-xl shadow-2xl p-2 z-50 animate-fadeIn text-xs">
                {/* Header info */}
                <div className="px-2.5 py-1.5 border-b border-slate-100 dark:border-slate-800 mb-1.5">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                      Loại tài khoản
                    </span>
                    <span className="inline-flex items-center gap-1 text-[9px] font-bold text-emerald-700 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/40 px-1.5 py-0.5 rounded">
                      <ShieldCheck className="w-3 h-3" /> 1 Loại Duy Nhất
                    </span>
                  </div>
                  <div className="text-[10.5px] text-slate-500 dark:text-slate-400 mt-1">
                    Đang hoạt động: <strong className="text-slate-800 dark:text-slate-200">{currentRole.label}</strong>
                  </div>
                </div>

                {/* Account Type Options List */}
                <div className="space-y-1">
                  {(['farmer', 'cooperative', 'expert', 'enterprise'] as CanonicalAccountType[]).map((typeKey) => {
                    const info = accountTypeDefinitions[typeKey];
                    const Icon = info.icon;
                    const isSelected = currentCanonical === typeKey;

                    return (
                      <div
                        key={typeKey}
                        className={`relative rounded-lg p-2 transition flex items-start gap-2.5 ${
                          isSelected
                            ? 'bg-[#166534]/10 dark:bg-[#166534]/25 border border-[#166534]/30'
                            : 'opacity-65 hover:opacity-90 bg-slate-50/50 dark:bg-slate-900/30'
                        }`}
                      >
                        <div
                          className={`w-6 h-6 rounded-md flex items-center justify-center flex-shrink-0 mt-0.5 ${info.color}`}
                        >
                          <Icon className="w-3.5 h-3.5" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center justify-between">
                            <span className="font-bold text-slate-900 dark:text-slate-100 text-[11.5px]">
                              {info.label}
                            </span>
                            {isSelected ? (
                              <span className="inline-flex items-center gap-0.5 text-[9px] font-bold text-emerald-600 dark:text-emerald-400">
                                <CheckCircle2 className="w-3 h-3" /> Đang dùng
                              </span>
                            ) : (
                              <span className="inline-flex items-center gap-0.5 text-[9px] text-slate-400 font-semibold">
                                <Lock className="w-2.5 h-2.5" /> Đã khóa
                              </span>
                            )}
                          </div>
                          <p className="text-[10px] text-slate-500 dark:text-slate-400 line-clamp-1 mt-0.5">
                            {info.description}
                          </p>

                          {!isSelected && (
                            <button
                              type="button"
                              onClick={() => {
                                setPendingChangeType(typeKey);
                                setChangeError(null);
                              }}
                              className="mt-1 text-[10px] font-semibold text-emerald-700 dark:text-emerald-400 hover:underline flex items-center gap-1"
                            >
                              <span>Chuyển sang loại này →</span>
                            </button>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>

                {/* Footer Notice */}
                <div className="mt-2 pt-2 border-t border-slate-100 dark:border-slate-800 text-[9.5px] text-slate-400 leading-tight">
                  🔒 Tài khoản được cố định 1 loại duy nhất. Đổi loại cần xác nhận và lưu nhật ký kiểm toán.
                </div>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* Confirmation Modal for Account Type Change */}
      {pendingChangeType && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 animate-fadeIn">
          <div className="bg-white dark:bg-[#141C16] border border-[#E5EBE6] dark:border-[#243328] rounded-2xl max-w-md w-full p-5 shadow-2xl relative">
            <button
              type="button"
              onClick={() => {
                setPendingChangeType(null);
                setChangeError(null);
              }}
              className="absolute top-4 right-4 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
            >
              <X className="w-5 h-5" />
            </button>

            <div className="flex items-center gap-2.5 text-amber-600 dark:text-amber-400 mb-3">
              <AlertCircle className="w-5 h-5" />
              <h3 className="text-base font-bold text-slate-900 dark:text-slate-100">
                Xác nhận đổi loại tài khoản
              </h3>
            </div>

            <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed mb-3">
              Mỗi tài khoản GARI được gán <strong>duy nhất 1 loại tài khoản đang hoạt động</strong>. Hành động này sẽ được lưu vào hệ thống đối soát (Audit Log) trên máy chủ.
            </p>

            <div className="bg-slate-50 dark:bg-slate-900/60 p-3 rounded-xl border border-slate-200 dark:border-slate-800 mb-3 text-xs space-y-1.5">
              <div className="flex justify-between">
                <span className="text-slate-500">Loại tài khoản hiện tại:</span>
                <span className="font-bold text-slate-800 dark:text-slate-200">
                  {accountTypeDefinitions[currentCanonical].label}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Loại tài khoản mới:</span>
                <span className="font-bold text-emerald-600 dark:text-emerald-400">
                  {accountTypeDefinitions[pendingChangeType].label}
                </span>
              </div>
              <div className="flex justify-between text-[11px] text-slate-400 pt-1 border-t border-slate-200 dark:border-slate-800">
                <span>Trạng thái VIP / Gói cước:</span>
                <span className="font-semibold text-emerald-600">Được bảo toàn nguyên vẹn</span>
              </div>
            </div>

            <div className="mb-4">
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                Lý do thay đổi (tùy chọn):
              </label>
              <input
                type="text"
                value={changeReason}
                onChange={(e) => setChangeReason(e.target.value)}
                placeholder="VD: Mở rộng sang mô hình Hợp tác xã / Khuyến nông..."
                className="w-full text-xs px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-emerald-500"
              />
            </div>

            {changeError && (
              <div className="p-2.5 mb-3 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 rounded-lg text-xs text-red-600 dark:text-red-400">
                {changeError}
              </div>
            )}

            <div className="flex items-center justify-end gap-2 text-xs">
              <button
                type="button"
                onClick={() => {
                  setPendingChangeType(null);
                  setChangeError(null);
                }}
                disabled={isSubmittingChange}
                className="px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 font-semibold"
              >
                Hủy bỏ
              </button>
              <button
                type="button"
                onClick={handleConfirmAccountTypeChange}
                disabled={isSubmittingChange}
                className="px-4 py-2 rounded-lg bg-[#166534] hover:bg-[#15803D] text-white font-bold flex items-center gap-1.5 shadow-md disabled:opacity-50"
              >
                {isSubmittingChange ? (
                  <span>Đang xử lý...</span>
                ) : (
                  <>
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    <span>Xác nhận chuyển đổi</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};
