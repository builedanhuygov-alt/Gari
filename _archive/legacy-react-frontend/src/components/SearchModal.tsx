import React, { useState, useEffect, useRef } from 'react';
import {
  Search,
  Zap,
  Building2,
  BookOpen,
  FileText,
  AlertOctagon,
  Stethoscope,
  SlidersHorizontal,
  LayoutDashboard,
  ArrowRight,
  X
} from 'lucide-react';
import type { NavTab, ModelInfo } from '../types';

interface SearchModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectTab: (tab: NavTab) => void;
  models: ModelInfo[];
  onSelectCropForDiagnosis: (crop: string) => void;
}

export const SearchModal: React.FC<SearchModalProps> = ({
  isOpen,
  onClose,
  onSelectTab,
  models,
  onSelectCropForDiagnosis,
}) => {
  const [query, setQuery] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const navPages: { id: NavTab; title: string; category: string; icon: any }[] = [
    { id: 'overview', title: 'Tổng quan (Dashboard)', category: 'Phân hệ', icon: LayoutDashboard },
    { id: 'vision', title: 'Chẩn đoán AI (Gari Vision 44 Models)', category: 'Phân hệ', icon: Zap },
    { id: 'farms', title: 'Nông trại của tôi (My Farms)', category: 'Phân hệ', icon: Building2 },
    { id: 'crops', title: 'Thư viện cây trồng (Crop Library)', category: 'Phân hệ', icon: BookOpen },
    { id: 'diseases', title: 'Thư viện bệnh lý & IPM (Disease Library)', category: 'Phân hệ', icon: BookOpen },
    { id: 'predict', title: 'Giám sát dịch tễ & rủi ro (Risk Monitoring)', category: 'Phân hệ', icon: AlertOctagon },
    { id: 'expert', title: 'Mạng lưới chuyên gia (Expert Support)', category: 'Phân hệ', icon: Stethoscope },
    { id: 'reports', title: 'Báo cáo & HTX (Reports & Intelligence)', category: 'Phân hệ', icon: FileText },
    { id: 'settings', title: 'Cấu hình hệ thống (Settings)', category: 'Phân hệ', icon: SlidersHorizontal },
  ];

  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 50);
      setQuery('');
      setSelectedIndex(0);
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const filteredPages = navPages.filter(p =>
    p.title.toLowerCase().includes(query.toLowerCase())
  );

  const filteredCrops = models
    .filter(m => m.crop_name.toLowerCase().includes(query.toLowerCase()) || m.crop_id.toLowerCase().includes(query.toLowerCase()))
    .slice(0, 8);

  const totalResults = filteredPages.length + filteredCrops.length;

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      onClose();
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex(prev => (prev + 1) % (totalResults || 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex(prev => (prev - 1 + (totalResults || 1)) % (totalResults || 1));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (selectedIndex < filteredPages.length) {
        const page = filteredPages[selectedIndex];
        onSelectTab(page.id);
        onClose();
      } else {
        const cropIndex = selectedIndex - filteredPages.length;
        const crop = filteredCrops[cropIndex];
        if (crop) {
          onSelectCropForDiagnosis(crop.crop_id);
          onClose();
        }
      }
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-start justify-center pt-16 sm:pt-24 px-4 animate-fadeIn"
      onClick={onClose}
    >
      <div
        className="w-full max-w-xl bg-white dark:bg-[#121914] border border-[#E5EBE6] dark:border-[#202C23] rounded-2xl shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
        onKeyDown={handleKeyDown}
      >
        {/* Search Input Bar */}
        <div className="flex items-center px-4 py-3.5 border-b border-[#E5EBE6] dark:border-[#202C23]">
          <Search className="w-4 h-4 text-slate-400 mr-3 shrink-0" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setSelectedIndex(0);
            }}
            placeholder="Tìm trang, cây trồng, bệnh hại, chức năng... (Esc để thoát)"
            className="w-full bg-transparent text-sm text-slate-900 dark:text-slate-100 placeholder:text-slate-400 focus:outline-none"
          />
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded-md text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Results List */}
        <div className="max-h-96 overflow-y-auto p-2">
          {totalResults === 0 ? (
            <div className="py-12 text-center text-xs text-slate-400">
              Không tìm thấy kết quả nào phù hợp với "{query}".
            </div>
          ) : (
            <div className="flex flex-col gap-1">
              {filteredPages.length > 0 && (
                <div>
                  <div className="px-3 py-1.5 text-[10px] font-bold uppercase tracking-wider text-slate-400">
                    Trang & Phân hệ
                  </div>
                  {filteredPages.map((page, index) => {
                    const Icon = page.icon;
                    const isSelected = selectedIndex === index;
                    return (
                      <button
                        key={page.id}
                        type="button"
                        onClick={() => {
                          onSelectTab(page.id);
                          onClose();
                        }}
                        onMouseEnter={() => setSelectedIndex(index)}
                        className={`w-full flex items-center justify-between px-3 py-2 rounded-xl text-left text-xs transition ${
                          isSelected
                            ? 'bg-[#166534] text-white'
                            : 'text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-[#1A241C]'
                        }`}
                      >
                        <div className="flex items-center gap-2.5">
                          <Icon className={`w-4 h-4 ${isSelected ? 'text-white' : 'text-slate-400'}`} />
                          <span className="font-medium">{page.title}</span>
                        </div>
                        <span className={`text-[10px] ${isSelected ? 'text-emerald-100' : 'text-slate-400'}`}>
                          Chuyển đến &rarr;
                        </span>
                      </button>
                    );
                  })}
                </div>
              )}

              {filteredCrops.length > 0 && (
                <div className="mt-2">
                  <div className="px-3 py-1.5 text-[10px] font-bold uppercase tracking-wider text-slate-400">
                    Cây trồng & Mô hình AI (Gari Vision)
                  </div>
                  {filteredCrops.map((crop, index) => {
                    const globalIdx = filteredPages.length + index;
                    const isSelected = selectedIndex === globalIdx;
                    return (
                      <button
                        key={crop.crop_id}
                        type="button"
                        onClick={() => {
                          onSelectCropForDiagnosis(crop.crop_id);
                          onClose();
                        }}
                        onMouseEnter={() => setSelectedIndex(globalIdx)}
                        className={`w-full flex items-center justify-between px-3 py-2 rounded-xl text-left text-xs transition ${
                          isSelected
                            ? 'bg-[#166534] text-white'
                            : 'text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-[#1A241C]'
                        }`}
                      >
                        <div className="flex items-center gap-2.5">
                          <Zap className={`w-4 h-4 ${isSelected ? 'text-white' : 'text-emerald-500'}`} />
                          <div>
                            <span className="font-medium">{crop.crop_name}</span>
                            <span className={`ml-2 text-[10px] ${isSelected ? 'text-emerald-200' : 'text-slate-400'}`}>
                              ({crop.classes_count} lớp bệnh)
                            </span>
                          </div>
                        </div>
                        <div className="flex items-center gap-1.5">
                          <span className={`text-[10px] px-1.5 py-0.5 rounded ${
                            isSelected ? 'bg-white/20 text-white' : 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
                          }`}>
                            Quét ngay
                          </span>
                          <ArrowRight className="w-3 h-3 opacity-60" />
                        </div>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer shortcuts */}
        <div className="px-4 py-2 bg-slate-50 dark:bg-[#0E1410] border-t border-[#E5EBE6] dark:border-[#202C23] flex items-center justify-between text-[11px] text-slate-400">
          <div className="flex items-center gap-3">
            <span><kbd className="px-1.5 py-0.5 bg-slate-200 dark:bg-slate-800 rounded font-mono text-[10px]">↑↓</kbd> Di chuyển</span>
            <span><kbd className="px-1.5 py-0.5 bg-slate-200 dark:bg-slate-800 rounded font-mono text-[10px]">↵</kbd> Chọn</span>
            <span><kbd className="px-1.5 py-0.5 bg-slate-200 dark:bg-slate-800 rounded font-mono text-[10px]">esc</kbd> Đóng</span>
          </div>
          <span>GARI Command Palette</span>
        </div>
      </div>
    </div>
  );
};
