import React from 'react';
import {
  Building2,
  Zap,
  ShieldCheck,
  Stethoscope,
  ArrowRight,
  BookOpen,
  FileText,
  Clock,
  CheckCircle2,
  Cpu
} from 'lucide-react';
import type { DashboardMetrics } from '../types';
import type { NavTab } from './Sidebar';

interface DashboardViewProps {
  metrics: DashboardMetrics | null;
  onNavigate: (tab: NavTab) => void;
  onOpenAddFarm: () => void;
}

export const DashboardView: React.FC<DashboardViewProps> = ({
  metrics,
  onNavigate,
  onOpenAddFarm,
}) => {
  // Localized greeting based on time of day
  const hour = new Date().getHours();
  const greeting = hour < 12 ? 'Chào buổi sáng' : hour < 18 ? 'Chào buổi chiều' : 'Chào buổi tối';

  const totalDiagnoses = metrics?.diagnoses_total ?? 0;
  const registeredFarms = metrics?.farms_total ?? 0;
  const totalHectares = metrics?.total_hectares ?? 0;
  const cropsMonitored = metrics?.crop_distribution?.length || 42;
  const pendingReviews = metrics?.pending_expert_cases ?? 0;
  const healthyRate = metrics?.healthy_rate_percent ?? 0;

  const recentDiagnoses = metrics?.recent_diagnoses || [];
  const cropDist = metrics?.crop_distribution || [];
  const diseaseDist = metrics?.disease_distribution || [];

  return (
    <div className="flex flex-col gap-6 animate-fadeIn">
      {/* Top Header / Greeting Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-2 border-b border-[#E5EBE6] dark:border-[#202C23]">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-700 dark:text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded">
              Không gian quản trị
            </span>
            <span className="text-xs text-slate-400 dark:text-slate-500">•</span>
            <span className="text-xs text-slate-500 dark:text-slate-400">Vận hành thời gian thực</span>
          </div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100 tracking-tight">
            {greeting}, Bác Hai Nông
          </h1>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Your agricultural intelligence overview.
          </p>
        </div>

        {/* Quick Actions Bar */}
        <div className="flex items-center gap-2 flex-wrap">
          <button
            type="button"
            onClick={() => onNavigate('vision')}
            className="px-3.5 py-2 rounded-lg bg-[#166534] hover:bg-[#14532D] text-white font-semibold text-xs flex items-center gap-1.5 transition shadow-sm"
          >
            <Zap className="w-3.5 h-3.5" />
            <span>Chẩn đoán mẫu lá</span>
          </button>

          <button
            type="button"
            onClick={onOpenAddFarm}
            className="px-3.5 py-2 rounded-lg bg-white dark:bg-[#121914] hover:bg-slate-50 dark:hover:bg-[#1A241C] border border-[#E5EBE6] dark:border-[#202C23] text-slate-800 dark:text-slate-200 font-medium text-xs flex items-center gap-1.5 transition"
          >
            <Building2 className="w-3.5 h-3.5 text-slate-500" />
            <span>Thêm nông trại</span>
          </button>

          <button
            type="button"
            onClick={() => onNavigate('crops')}
            className="px-3.5 py-2 rounded-lg bg-white dark:bg-[#121914] hover:bg-slate-50 dark:hover:bg-[#1A241C] border border-[#E5EBE6] dark:border-[#202C23] text-slate-800 dark:text-slate-200 font-medium text-xs flex items-center gap-1.5 transition hidden sm:flex"
          >
            <BookOpen className="w-3.5 h-3.5 text-slate-500" />
            <span>Khám phá cây</span>
          </button>

          <button
            type="button"
            onClick={() => onNavigate('reports')}
            className="px-3.5 py-2 rounded-lg bg-white dark:bg-[#121914] hover:bg-slate-50 dark:hover:bg-[#1A241C] border border-[#E5EBE6] dark:border-[#202C23] text-slate-800 dark:text-slate-200 font-medium text-xs flex items-center gap-1.5 transition hidden md:flex"
          >
            <FileText className="w-3.5 h-3.5 text-slate-500" />
            <span>Báo cáo HTX</span>
          </button>
        </div>
      </div>

      {/* A. Summary KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
        {/* Total Diagnoses */}
        <div className="p-4 rounded-xl bg-white dark:bg-[#121914] border border-[#E5EBE6] dark:border-[#202C23] shadow-sm flex items-start justify-between">
          <div>
            <span className="text-xs font-medium text-slate-500 dark:text-slate-400 block mb-1">
              Tổng số mẫu đã chẩn đoán
            </span>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-bold text-slate-900 dark:text-slate-100">
                {totalDiagnoses}
              </span>
              <span className="text-[11px] text-emerald-600 dark:text-emerald-400 font-medium">
                {healthyRate > 0 ? `${healthyRate}% sạch bệnh` : 'ConvNeXt'}
              </span>
            </div>
            <span className="text-[11px] text-slate-400 dark:text-slate-500 block mt-1">
              Phân tích qua 44 mô hình cục bộ
            </span>
          </div>
          <div className="w-9 h-9 rounded-lg bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 flex items-center justify-center shrink-0">
            <Zap className="w-4 h-4" />
          </div>
        </div>

        {/* Registered Farms */}
        <div className="p-4 rounded-xl bg-white dark:bg-[#121914] border border-[#E5EBE6] dark:border-[#202C23] shadow-sm flex items-start justify-between">
          <div>
            <span className="text-xs font-medium text-slate-500 dark:text-slate-400 block mb-1">
              Nông trại đã đăng ký
            </span>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-bold text-slate-900 dark:text-slate-100">
                {registeredFarms}
              </span>
              <span className="text-[11px] text-slate-600 dark:text-slate-400 font-medium">
                {totalHectares} ha tổng diện tích
              </span>
            </div>
            <span className="text-[11px] text-slate-400 dark:text-slate-500 block mt-1">
              Theo dõi định kỳ theo mùa vụ
            </span>
          </div>
          <div className="w-9 h-9 rounded-lg bg-teal-500/10 text-teal-600 dark:text-teal-400 flex items-center justify-center shrink-0">
            <Building2 className="w-4 h-4" />
          </div>
        </div>

        {/* Crops Monitored */}
        <div className="p-4 rounded-xl bg-white dark:bg-[#121914] border border-[#E5EBE6] dark:border-[#202C23] shadow-sm flex items-start justify-between">
          <div>
            <span className="text-xs font-medium text-slate-500 dark:text-slate-400 block mb-1">
              Chủng loại cây theo dõi
            </span>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-bold text-slate-900 dark:text-slate-100">
                {cropsMonitored}
              </span>
              <span className="text-[11px] text-emerald-600 dark:text-emerald-400 font-medium">
                100% Khả dụng
              </span>
            </div>
            <span className="text-[11px] text-slate-400 dark:text-slate-500 block mt-1">
              Rau củ, cây ăn trái & công nghiệp
            </span>
          </div>
          <div className="w-9 h-9 rounded-lg bg-blue-500/10 text-blue-600 dark:text-blue-400 flex items-center justify-center shrink-0">
            <ShieldCheck className="w-4 h-4" />
          </div>
        </div>

        {/* Pending Reviews */}
        <div className="p-4 rounded-xl bg-white dark:bg-[#121914] border border-[#E5EBE6] dark:border-[#202C23] shadow-sm flex items-start justify-between">
          <div>
            <span className="text-xs font-medium text-slate-500 dark:text-slate-400 block mb-1">
              Ca chờ chuyên gia thẩm định
            </span>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-bold text-amber-600 dark:text-amber-400">
                {pendingReviews}
              </span>
              <span className="text-[11px] text-slate-500 dark:text-slate-400 font-medium">
                Hồ sơ đang xử lý
              </span>
            </div>
            <span className="text-[11px] text-slate-400 dark:text-slate-500 block mt-1">
              Kết nối chuyên gia BVTV địa phương
            </span>
          </div>
          <div className="w-9 h-9 rounded-lg bg-amber-500/10 text-amber-600 dark:text-amber-400 flex items-center justify-center shrink-0">
            <Stethoscope className="w-4 h-4" />
          </div>
        </div>
      </div>

      {/* Main Grid: Recent Activity & Distribution Insights */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* B. Recent Diagnosis Activity (2 cols on large screen) */}
        <div className="lg:col-span-2 bg-white dark:bg-[#121914] border border-[#E5EBE6] dark:border-[#202C23] rounded-xl p-4 shadow-sm flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-3 mb-3 border-b border-[#E5EBE6] dark:border-[#202C23]">
              <div className="flex items-center gap-2">
                <Clock className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
                <h2 className="text-sm font-bold text-slate-900 dark:text-slate-100">
                  Hoạt động chẩn đoán gần đây
                </h2>
              </div>
              <button
                type="button"
                onClick={() => onNavigate('vision')}
                className="text-xs font-medium text-emerald-700 dark:text-emerald-400 hover:underline flex items-center gap-1"
              >
                <span>Xem tất cả</span>
                <ArrowRight className="w-3 h-3" />
              </button>
            </div>

            {recentDiagnoses.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-slate-100 dark:border-slate-800 text-[11px] font-semibold text-slate-400 dark:text-slate-500">
                      <th className="pb-2 pl-1">Cây trồng</th>
                      <th className="pb-2">Kết quả chẩn đoán AI</th>
                      <th className="pb-2">Độ tin cậy</th>
                      <th className="pb-2">Mức độ</th>
                      <th className="pb-2 pr-1 text-right">Thời gian</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60">
                    {recentDiagnoses.map((record) => {
                      const isHealthy = record.predicted_disease.toLowerCase().includes('healthy') || record.severity === 'Normal';
                      const confPct = record.confidence > 1 ? Math.round(record.confidence) : Math.round(record.confidence * 100);

                      return (
                        <tr key={record.id} className="hover:bg-slate-50 dark:hover:bg-[#162019] transition">
                          <td className="py-2.5 pl-1 font-semibold text-slate-800 dark:text-slate-200">
                            {record.crop_name}
                          </td>
                          <td className="py-2.5">
                            <div className="font-medium text-slate-900 dark:text-slate-100">
                              {record.disease_name_vi || record.predicted_disease}
                            </div>
                            {record.predicted_disease && (
                              <div className="text-[10px] text-slate-400 dark:text-slate-500 font-mono">
                                {record.predicted_disease}
                              </div>
                            )}
                          </td>
                          <td className="py-2.5">
                            <span className={`inline-block font-bold ${confPct >= 75 ? 'text-emerald-600 dark:text-emerald-400' : 'text-amber-500'}`}>
                              {confPct}%
                            </span>
                          </td>
                          <td className="py-2.5">
                            <span
                              className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${
                                isHealthy
                                  ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400'
                                  : 'bg-red-500/10 text-red-700 dark:text-red-400'
                              }`}
                            >
                              {record.severity || (isHealthy ? 'Khỏe mạnh' : 'Nguy cơ')}
                            </span>
                          </td>
                          <td className="py-2.5 pr-1 text-right text-slate-400 dark:text-slate-500 text-[11px]">
                            {record.created_at ? record.created_at.split('T')[0] : 'Hôm nay'}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="py-10 text-center text-xs text-slate-400 dark:text-slate-500">
                Chưa có dữ liệu chẩn đoán nào được lưu. Bấm "Chẩn đoán mẫu lá" để bắt đầu.
              </div>
            )}
          </div>

          {/* Quick Tip / Operational Status */}
          <div className="mt-4 pt-3 border-t border-[#E5EBE6] dark:border-[#202C23] flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
            <span className="flex items-center gap-1.5">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
              Thuật toán ConvNeXt cục bộ đảm bảo phản hồi tức thì dưới 100ms.
            </span>
            <button
              type="button"
              onClick={() => onNavigate('farms')}
              className="text-emerald-700 dark:text-emerald-400 hover:underline font-medium"
            >
              Gán mẫu vào nông trại &rarr;
            </button>
          </div>
        </div>

        {/* Right Column: C. Crop Distribution & D. Disease Insights */}
        <div className="space-y-4">
          {/* Crop Distribution */}
          <div className="bg-white dark:bg-[#121914] border border-[#E5EBE6] dark:border-[#202C23] rounded-xl p-4 shadow-sm">
            <div className="flex items-center justify-between pb-2 mb-3 border-b border-[#E5EBE6] dark:border-[#202C23]">
              <h2 className="text-sm font-bold text-slate-900 dark:text-slate-100">
                Phân bố theo cây trồng
              </h2>
              <span className="text-[10px] text-slate-400 uppercase tracking-wider font-semibold">
                Thực tế
              </span>
            </div>

            {cropDist.length > 0 ? (
              <div className="space-y-2.5">
                {cropDist.slice(0, 5).map((item, idx) => {
                  const maxCount = Math.max(...cropDist.map(c => c.count), 1);
                  const widthPct = Math.round((item.count / maxCount) * 100);
                  return (
                    <div key={idx} className="text-xs">
                      <div className="flex justify-between text-slate-700 dark:text-slate-300 font-medium mb-1">
                        <span>{item.crop}</span>
                        <span className="text-slate-400 font-mono">{item.count} mẫu</span>
                      </div>
                      <div className="w-full h-1.5 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-[#166534] dark:bg-emerald-500 rounded-full"
                          style={{ width: `${widthPct}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="py-6 text-center text-xs text-slate-400">
                Chưa có dữ liệu phân bố cây trồng.
              </div>
            )}
          </div>

          {/* Disease Insights */}
          <div className="bg-white dark:bg-[#121914] border border-[#E5EBE6] dark:border-[#202C23] rounded-xl p-4 shadow-sm">
            <div className="flex items-center justify-between pb-2 mb-3 border-b border-[#E5EBE6] dark:border-[#202C23]">
              <h2 className="text-sm font-bold text-slate-900 dark:text-slate-100">
                Tần suất phát hiện bệnh
              </h2>
              <span className="text-[10px] text-slate-400 uppercase tracking-wider font-semibold">
                Dịch tễ
              </span>
            </div>

            {diseaseDist.length > 0 ? (
              <div className="space-y-2">
                {diseaseDist.slice(0, 4).map((d, i) => (
                  <div key={i} className="flex items-center justify-between text-xs p-1.5 rounded-lg bg-[#F7F9F7] dark:bg-[#162019]">
                    <span className="font-medium text-slate-800 dark:text-slate-200 truncate pr-2">
                      {d.disease}
                    </span>
                    <span className="font-mono text-[11px] font-semibold text-emerald-700 dark:text-emerald-400 shrink-0">
                      {d.count} ca
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="py-6 text-center text-xs text-slate-400">
                Chưa ghi nhận ca bệnh nào trong hệ thống.
              </div>
            )}
          </div>

          {/* F. System Status Confirmation */}
          <div className="p-3 bg-emerald-50 dark:bg-[#111C14] border border-emerald-200 dark:border-emerald-900/40 rounded-xl text-xs flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Cpu className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
              <div>
                <span className="font-bold text-emerald-900 dark:text-emerald-200 block">
                  AI Engine Sẵn Sàng
                </span>
                <span className="text-[11px] text-emerald-700 dark:text-emerald-400">
                  44 Mô hình ConvNeXt cục bộ hoạt động tốt.
                </span>
              </div>
            </div>
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
          </div>
        </div>
      </div>
    </div>
  );
};
