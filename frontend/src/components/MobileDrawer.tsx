import React from 'react';
import {
  X,
  LayoutDashboard,
  Zap,
  Building2,
  BookOpen,
  AlertOctagon,
  Stethoscope,
  FileText,
  SlidersHorizontal,
  Leaf
} from 'lucide-react';
import type { NavTab } from '../types';

interface MobileDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  activeTab: NavTab;
  onSelectTab: (tab: NavTab) => void;
  farmsCount: number;
  pendingExpertCount: number;
}

export const MobileDrawer: React.FC<MobileDrawerProps> = ({
  isOpen,
  onClose,
  activeTab,
  onSelectTab,
  farmsCount,
  pendingExpertCount,
}) => {
  if (!isOpen) return null;

  const navItems: {
    id: NavTab;
    label: string;
    sublabel: string;
    icon: any;
    badge?: string | number;
  }[] = [
    { id: 'overview', label: 'Tổng quan', sublabel: 'Operational dashboard', icon: LayoutDashboard },
    { id: 'vision', label: 'Chẩn đoán AI', sublabel: 'Gari Vision 44 Models', icon: Zap, badge: 'Core' },
    { id: 'farms', label: 'Nông trại của tôi', sublabel: 'Farm workspace', icon: Building2, badge: farmsCount > 0 ? farmsCount : undefined },
    { id: 'crops', label: 'Thư viện cây trồng', sublabel: 'Crop directory & models', icon: BookOpen },
    { id: 'diseases', label: 'Thư viện bệnh lý', sublabel: 'IPM knowledge database', icon: BookOpen },
    { id: 'predict', label: 'Giám sát rủi ro', sublabel: 'Risk & weather monitoring', icon: AlertOctagon },
    { id: 'expert', label: 'Hỗ trợ chuyên gia', sublabel: 'Agronomist network', icon: Stethoscope, badge: pendingExpertCount > 0 ? pendingExpertCount : undefined },
    { id: 'reports', label: 'Báo cáo & HTX', sublabel: 'Cooperative intelligence', icon: FileText },
    { id: 'settings', label: 'Cài đặt & Hồ sơ', sublabel: 'System configuration', icon: SlidersHorizontal },
  ];

  return (
    <div className="fixed inset-0 z-50 lg:hidden flex">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/60 backdrop-blur-sm transition-opacity"
        onClick={onClose}
      />

      {/* Drawer content */}
      <div className="relative w-72 max-w-[85vw] bg-white dark:bg-[#121914] border-r border-[#E5EBE6] dark:border-[#202C23] h-full shadow-2xl flex flex-col justify-between z-10 animate-fadeIn">
        <div>
          {/* Header */}
          <div className="p-4 border-b border-[#E5EBE6] dark:border-[#202C23] flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-[#166534] flex items-center justify-center text-white font-bold">
                <Leaf className="w-4 h-4 text-emerald-400" />
              </div>
              <div>
                <span className="font-extrabold text-sm tracking-tight text-slate-900 dark:text-slate-100">
                  GARI AI LAB
                </span>
                <span className="block text-[10px] text-slate-500 dark:text-slate-400">
                  AgriTech Intelligence
                </span>
              </div>
            </div>
            <button
              type="button"
              onClick={onClose}
              className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Navigation Items */}
          <nav className="p-2 space-y-1 overflow-y-auto max-h-[calc(100vh-140px)]">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => {
                    onSelectTab(item.id);
                    onClose();
                  }}
                  className={`w-full flex items-center justify-between px-3 py-2.5 rounded-xl text-left transition ${
                    isActive
                      ? 'bg-[#166534] text-white font-semibold'
                      : 'text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-[#1A241C]'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <Icon className={`w-4 h-4 ${isActive ? 'text-white' : 'text-slate-400'}`} />
                    <div>
                      <div className="text-xs font-medium">{item.label}</div>
                      <div className={`text-[10px] ${isActive ? 'text-emerald-200' : 'text-slate-500'}`}>
                        {item.sublabel}
                      </div>
                    </div>
                  </div>
                  {item.badge && (
                    <span
                      className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                        isActive ? 'bg-white/20 text-white' : 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
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

        {/* Footer */}
        <div className="p-4 border-t border-[#E5EBE6] dark:border-[#202C23] bg-slate-50 dark:bg-[#0E1410] text-[11px] text-slate-500">
          <div className="flex items-center justify-between font-semibold text-slate-700 dark:text-slate-300">
            <span>GARI SaaS v2.5</span>
            <span className="text-[10px] text-emerald-600 dark:text-emerald-400">44 Models Online</span>
          </div>
        </div>
      </div>
    </div>
  );
};
