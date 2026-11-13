import { GARI_FEATURES } from '../features';
import React from 'react';
import {
  LayoutDashboard,
  Zap,
  Building2,
  BookOpen,
  Library,
  AlertOctagon,
  Stethoscope,
  FileText,
  SlidersHorizontal,
  Users,
  ChevronLeft,
  ChevronRight,
  Leaf
} from 'lucide-react';
import type { NavTab } from '../types';

interface SidebarProps {
  activeTab: NavTab;
  onSelectTab: (tab: NavTab) => void;
  farmsCount: number;
  pendingExpertCount: number;
  isCollapsed: boolean;
  onToggleCollapse: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  activeTab,
  onSelectTab,
  farmsCount,
  pendingExpertCount,
  isCollapsed,
  onToggleCollapse,
}) => {
  const navItems: {
    id: NavTab;
    label: string;
    sublabel: string;
    icon: any;
    badge?: string | number;
    badgeStyle?: string;
  }[] = [
    {
      id: 'overview',
      label: 'Tổng quan',
      sublabel: 'Dashboard hoạt động',
      icon: LayoutDashboard,
    },
    {
      id: 'vision',
      label: 'Chẩn đoán AI',
      sublabel: 'Gari Vision 44 Models',
      icon: Zap,
      badge: 'Core',
      badgeStyle: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20',
    },
    {
      id: 'farms',
      label: 'Nông trại của tôi',
      sublabel: 'Không gian nông hộ & HTX',
      icon: Building2,
      badge: farmsCount > 0 ? farmsCount : undefined,
      badgeStyle: 'bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300',
    },
    {
      id: 'crops',
      label: 'Thư viện cây trồng',
      sublabel: '42 loài & phân loại mô hình',
      icon: BookOpen,
      badge: '42 loài',
      badgeStyle: 'bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300',
    },
    {
      id: 'diseases',
      label: 'Thư viện bệnh lý',
      sublabel: 'Từ điển dịch tễ & IPM',
      icon: Library,
    },
    {
      id: 'predict',
      label: 'Giám sát rủi ro',
      sublabel: 'Cảnh báo thời tiết & dịch',
      icon: AlertOctagon,
    },
    {
      id: 'expert',
      label: 'Hỗ trợ chuyên gia',
      sublabel: 'Mạng lưới tư vấn BVTV',
      icon: Stethoscope,
      badge: pendingExpertCount > 0 ? pendingExpertCount : undefined,
      badgeStyle: 'bg-amber-500/15 text-amber-600 dark:text-amber-400',
    },
    {
      id: 'reports',
      label: 'Báo cáo & HTX',
      sublabel: 'Phân tích tổng hợp & CSV',
      icon: FileText,
    },
    {
      id: 'community',
      label: 'Cộng đồng & Tri thức',
      sublabel: 'Diễn đàn & Cẩm nang BVTV',
      icon: Users,
    },
    {
      id: 'settings',
      label: 'Cài đặt & Hồ sơ',
      sublabel: 'Thiết bị & tài khoản',
      icon: SlidersHorizontal,
    },
  ];

  return (
    <aside
      className={`border-r border-[#E5EBE6] dark:border-[#202C23] bg-[#F7F9F7] dark:bg-[#0E1410] flex flex-col justify-between shrink-0 transition-all duration-200 hidden lg:flex ${
        isCollapsed ? 'w-16 p-2' : 'w-60 p-3'
      }`}
    >
      <div>
        {/* Brand & Collapse Toggle */}
        <div className={`flex items-center pb-3 mb-2 border-b border-[#E5EBE6] dark:border-[#202C23] ${
          isCollapsed ? 'justify-center' : 'justify-between px-2'
        }`}>
          {!isCollapsed && (
            <div className="flex items-center gap-2.5">
              <div className="w-7 h-7 rounded-lg bg-[#166534] flex items-center justify-center text-white shadow-sm">
                <Leaf className="w-4 h-4 text-emerald-400" />
              </div>
              <div>
                <span className="font-extrabold text-sm tracking-tight text-slate-900 dark:text-slate-100">
                  GARI AI LAB
                </span>
                <span className="block text-[9px] font-medium uppercase tracking-wider text-emerald-700 dark:text-emerald-400">
                  AgriTech Intelligence
                </span>
              </div>
            </div>
          )}

          {isCollapsed && (
            <div className="w-8 h-8 rounded-lg bg-[#166534] flex items-center justify-center text-white shadow-sm mb-1">
              <Leaf className="w-4 h-4 text-emerald-400" />
            </div>
          )}

          <button
            type="button"
            onClick={onToggleCollapse}
            className={`p-1 rounded-md text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 hover:bg-slate-200 dark:hover:bg-[#1A241C] transition ${
              isCollapsed ? 'mt-2' : ''
            }`}
            title={isCollapsed ? 'Mở rộng sidebar' : 'Thu gọn sidebar'}
            aria-label={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            {isCollapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
          </button>
        </div>

        {/* Section title */}
        {!isCollapsed && (
          <div className="px-2 py-1 text-[10px] font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500">
            Không gian làm việc
          </div>
        )}

        {/* Nav Items List */}
        <nav className="space-y-0.5 mt-1">
          {navItems.filter(item => (item.id !== 'farms' || GARI_FEATURES.farms) && (item.id !== 'community' || GARI_FEATURES.community)).map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;

            return (
              <button
                key={item.id}
                type="button"
                onClick={() => onSelectTab(item.id)}
                title={isCollapsed ? item.label : undefined}
                className={`w-full flex items-center rounded-lg text-left transition group relative ${
                  isCollapsed ? 'justify-center p-2.5' : 'justify-between px-2.5 py-2'
                } ${
                  isActive
                    ? 'bg-[#166534] text-white shadow-sm font-semibold'
                    : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100 hover:bg-slate-200/60 dark:hover:bg-[#162018]'
                }`}
              >
                <div className={`flex items-center gap-2.5 min-w-0 ${isCollapsed ? 'justify-center' : ''}`}>
                  <Icon
                    className={`w-4 h-4 shrink-0 transition ${
                      isActive ? 'text-white' : 'text-slate-500 dark:text-slate-400 group-hover:text-slate-800 dark:group-hover:text-slate-200'
                    }`}
                  />
                  {!isCollapsed && (
                    <div className="truncate">
                      <div className="text-xs leading-none truncate">
                        {item.label}
                      </div>
                      <div className={`text-[10px] leading-tight truncate mt-0.5 ${
                        isActive ? 'text-emerald-100' : 'text-slate-400 dark:text-slate-500'
                      }`}>
                        {item.sublabel}
                      </div>
                    </div>
                  )}
                </div>

                {!isCollapsed && item.badge !== undefined && (
                  <span
                    className={`text-[10px] font-bold px-1.5 py-0.5 rounded ml-1 shrink-0 ${
                      isActive ? 'bg-white/20 text-white' : (item.badgeStyle || 'bg-slate-200 dark:bg-slate-800 text-slate-600 dark:text-slate-400')
                    }`}
                  >
                    {item.badge}
                  </span>
                )}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Sidebar Footer */}
      {!isCollapsed ? (
        <div className="p-2.5 rounded-xl bg-white dark:bg-[#141C16] border border-[#E5EBE6] dark:border-[#202C23] text-[11px]">
          <div className="flex items-center justify-between font-semibold text-slate-700 dark:text-slate-300">
            <span>GARI SaaS v2.5</span>
            <span className="text-[9px] px-1.5 py-0.2 rounded bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 font-bold">
              PROD
            </span>
          </div>
          <p className="text-[10px] text-slate-400 dark:text-slate-500 mt-1 leading-relaxed">
            44 Mô hình ConvNeXt cục bộ bảo mật dữ liệu tuyệt đối.
          </p>
        </div>
      ) : (
        <div className="flex justify-center py-2 text-[10px] text-emerald-600 dark:text-emerald-400 font-bold">
          v2.5
        </div>
      )}
    </aside>
  );
};
export type { NavTab };
