import React from 'react';
import { Home } from 'lucide-react';

interface DevelopmentNoticeViewProps {
  icon: string;
  title: string;
  description: string;
  onGoHome: () => void;
}

export const DevelopmentNoticeView: React.FC<DevelopmentNoticeViewProps> = ({
  icon,
  title,
  description,
  onGoHome,
}) => {
  return (
    <div className="min-h-[60vh] flex items-center justify-center p-6">
      <div className="bg-slate-900 border border-slate-800 rounded-3xl p-10 max-w-lg w-full text-center shadow-xl">
        <div className="w-20 h-20 rounded-2xl bg-emerald-500/10 text-emerald-400 flex items-center justify-center text-4xl mx-auto mb-6">
          {icon}
        </div>
        <h1 className="text-2xl font-bold text-white mb-3 tracking-tight">
          {title}
        </h1>
        <p className="text-slate-400 text-sm leading-relaxed mb-8">
          {description}
        </p>
        <button
          type="button"
          onClick={onGoHome}
          className="inline-flex items-center justify-center gap-2 px-6 py-3 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-medium text-sm transition-all shadow-lg shadow-emerald-900/30 cursor-pointer"
        >
          <Home className="w-4 h-4" />
          <span>Quay về Trang chủ</span>
        </button>
      </div>
    </div>
  );
};
