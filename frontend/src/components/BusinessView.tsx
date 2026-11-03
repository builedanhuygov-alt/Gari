import React, { useState } from 'react';
import {
  Building2,
  FileText,
  Download,
  Users,
  ShieldCheck,
  CheckCircle2
} from 'lucide-react';
import type { Farm } from '../types';

interface BusinessViewProps {
  farms: Farm[];
}

export const BusinessView: React.FC<BusinessViewProps> = ({ farms }) => {
  const [exporting, setExporting] = useState<boolean>(false);

  const handleExportCSV = () => {
    setExporting(true);
    try {
      const headers = ['ID', 'Tên nông trại', 'Tỉnh thành', 'Cây trồng', 'Diện tích (ha)', 'Loại đất', 'Hệ thống tưới', 'Trạng thái'];
      const rows = farms.map(f => [
        f.id,
        `"${f.name}"`,
        `"${f.province}"`,
        `"${f.primary_crop}"`,
        f.area_hectare,
        `"${f.soil_type || ''}"`,
        `"${f.irrigation_type || ''}"`,
        `"${f.status || 'active'}"`
      ]);

      const csvContent = 'data:text/csv;charset=utf-8,\uFEFF' + [headers.join(','), ...rows.map(e => e.join(','))].join('\n');
      const encodedUri = encodeURI(csvContent);
      const link = document.createElement('a');
      link.setAttribute('href', encodedUri);
      link.setAttribute('download', `gari-cooperative-farms-${new Date().toISOString().slice(0, 10)}.csv`);
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    } finally {
      setExporting(false);
    }
  };

  const totalHectares = farms.reduce((acc, f) => acc + (f.area_hectare || 0), 0);

  return (
    <div className="flex flex-col gap-5 animate-fadeIn">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-2 border-b border-[#E5EBE6] dark:border-[#202C23]">
        <div>
          <h1 className="text-xl font-bold text-slate-900 dark:text-slate-100 tracking-tight">
            Báo Cáo & Quản Trị Hợp Tác Xã
          </h1>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Dữ liệu tổng hợp liên vùng phục vụ giám sát mã số vùng trồng xuất khẩu và truy xuất nguồn gốc.
          </p>
        </div>

        <button
          type="button"
          onClick={handleExportCSV}
          disabled={exporting || farms.length === 0}
          className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-[#166534] hover:bg-[#14532D] text-white font-semibold text-xs transition shadow-sm self-start sm:self-auto disabled:opacity-50"
        >
          <Download className="w-3.5 h-3.5" />
          <span>{exporting ? 'Đang xuất...' : 'Xuất dữ liệu CSV'}</span>
        </button>
      </div>

      {/* Aggregate Metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3.5">
        <div className="p-4 rounded-xl bg-white dark:bg-[#121914] border border-[#E5EBE6] dark:border-[#202C23] shadow-sm flex items-center justify-between">
          <div>
            <span className="text-[11px] font-medium text-slate-500 dark:text-slate-400 block mb-0.5">Hộ nông dân liên kết</span>
            <div className="text-2xl font-bold text-slate-900 dark:text-slate-100">{farms.length * 5 || 20} hộ</div>
            <span className="text-[10px] text-teal-600 dark:text-teal-400 block mt-1">4 Hợp tác xã nòng cốt</span>
          </div>
          <div className="w-10 h-10 rounded-lg bg-teal-500/10 text-teal-600 dark:text-teal-400 flex items-center justify-center">
            <Users className="w-5 h-5" />
          </div>
        </div>

        <div className="p-4 rounded-xl bg-white dark:bg-[#121914] border border-[#E5EBE6] dark:border-[#202C23] shadow-sm flex items-center justify-between">
          <div>
            <span className="text-[11px] font-medium text-slate-500 dark:text-slate-400 block mb-0.5">Diện tích quy hoạch</span>
            <div className="text-2xl font-bold text-slate-900 dark:text-slate-100">{totalHectares.toFixed(1)} ha</div>
            <span className="text-[10px] text-emerald-600 dark:text-emerald-400 block mt-1">Chuẩn VietGAP/GlobalGAP</span>
          </div>
          <div className="w-10 h-10 rounded-lg bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 flex items-center justify-center">
            <Building2 className="w-5 h-5" />
          </div>
        </div>

        <div className="p-4 rounded-xl bg-white dark:bg-[#121914] border border-[#E5EBE6] dark:border-[#202C23] shadow-sm flex items-center justify-between">
          <div>
            <span className="text-[11px] font-medium text-slate-500 dark:text-slate-400 block mb-0.5">Mã vùng trồng cấp phép</span>
            <div className="text-2xl font-bold text-emerald-700 dark:text-emerald-400">12 mã</div>
            <span className="text-[10px] text-slate-400 block mt-1">Cục Bảo vệ Thực vật cấp</span>
          </div>
          <div className="w-10 h-10 rounded-lg bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 flex items-center justify-center">
            <ShieldCheck className="w-5 h-5" />
          </div>
        </div>
      </div>

      {/* Farms Table */}
      <div className="bg-white dark:bg-[#121914] border border-[#E5EBE6] dark:border-[#202C23] rounded-xl p-4 shadow-sm">
        <div className="flex items-center justify-between border-b border-[#E5EBE6] dark:border-[#202C23] pb-3 mb-3">
          <h3 className="font-bold text-xs text-slate-900 dark:text-slate-100 flex items-center gap-2">
            <FileText className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
            <span>Danh mục nông trại & vùng canh tác thành viên</span>
          </h3>
          <span className="text-[11px] text-slate-500 dark:text-slate-400">
            {farms.length} Bản ghi
          </span>
        </div>

        {farms.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-[#E5EBE6] dark:border-[#202C23] text-[11px] text-slate-400 font-semibold">
                  <th className="pb-2">Tên cơ sở</th>
                  <th className="pb-2">Địa bàn</th>
                  <th className="pb-2">Cây trồng</th>
                  <th className="pb-2">Diện tích (ha)</th>
                  <th className="pb-2">Phương thức tưới</th>
                  <th className="pb-2 text-right">Trạng thái</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E5EBE6] dark:divide-[#202C23]">
                {farms.map((f) => (
                  <tr key={f.id} className="hover:bg-slate-50 dark:hover:bg-[#162019] transition">
                    <td className="py-2.5 font-semibold text-slate-800 dark:text-slate-200">{f.name}</td>
                    <td className="py-2.5 text-slate-600 dark:text-slate-400">{f.province}</td>
                    <td className="py-2.5 text-slate-800 dark:text-slate-200">{f.primary_crop}</td>
                    <td className="py-2.5 font-mono text-emerald-700 dark:text-emerald-400 font-semibold">{f.area_hectare} ha</td>
                    <td className="py-2.5 text-slate-500 dark:text-slate-400">{f.irrigation_type || 'Tưới nhỏ giọt'}</td>
                    <td className="py-2.5 text-right">
                      <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-700 dark:text-emerald-400">
                        Hoạt động
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="py-12 text-center text-xs text-slate-400">
            Chưa có nông trại nào trong hệ thống báo cáo.
          </div>
        )}
      </div>

      {/* SaaS Tier Options Roadmap */}
      <div className="p-4 rounded-xl bg-white dark:bg-[#121914] border border-[#E5EBE6] dark:border-[#202C23] shadow-sm">
        <div className="flex items-center justify-between mb-3">
          <div>
            <h4 className="font-bold text-sm text-slate-900 dark:text-slate-100">
              Gói Dịch Vụ Doanh Nghiệp & Hợp Tác Xã
            </h4>
            <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">
              Tùy chọn triển khai hệ thống máy chủ biên (Edge AI) và trạm thời tiết IoT chuyên dụng.
            </p>
          </div>
          <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 uppercase">
            SaaS Roadmap
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
          <div className="p-3 bg-[#F7F9F7] dark:bg-[#162019] rounded-lg border border-[#E5EBE6] dark:border-[#202C23]">
            <span className="font-bold text-slate-900 dark:text-slate-100 block mb-1">Gói Nông Hộ</span>
            <span className="text-emerald-700 dark:text-emerald-400 font-bold block mb-2">Miễn phí vĩnh viễn</span>
            <ul className="space-y-1 text-[11px] text-slate-500 dark:text-slate-400">
              <li className="flex items-center gap-1.5"><CheckCircle2 className="w-3 h-3 text-emerald-500" /> Quét AI 44 cây trồng</li>
              <li className="flex items-center gap-1.5"><CheckCircle2 className="w-3 h-3 text-emerald-500" /> Quản lý 5 nông trại</li>
            </ul>
          </div>

          <div className="p-3 bg-[#F7F9F7] dark:bg-[#162019] rounded-lg border border-emerald-500/30">
            <span className="font-bold text-slate-900 dark:text-slate-100 block mb-1">Hợp Tác Xã</span>
            <span className="text-emerald-700 dark:text-emerald-400 font-bold block mb-2">500.000 đ / tháng</span>
            <ul className="space-y-1 text-[11px] text-slate-500 dark:text-slate-400">
              <li className="flex items-center gap-1.5"><CheckCircle2 className="w-3 h-3 text-emerald-500" /> Không giới hạn hộ nông dân</li>
              <li className="flex items-center gap-1.5"><CheckCircle2 className="w-3 h-3 text-emerald-500" /> Xuất báo cáo cấp mã vùng</li>
            </ul>
          </div>

          <div className="p-3 bg-[#F7F9F7] dark:bg-[#162019] rounded-lg border border-[#E5EBE6] dark:border-[#202C23]">
            <span className="font-bold text-slate-900 dark:text-slate-100 block mb-1">Doanh Nghiệp / Viện</span>
            <span className="text-emerald-700 dark:text-emerald-400 font-bold block mb-2">Liên hệ giải pháp</span>
            <ul className="space-y-1 text-[11px] text-slate-500 dark:text-slate-400">
              <li className="flex items-center gap-1.5"><CheckCircle2 className="w-3 h-3 text-emerald-500" /> Máy chủ AI offline tại thực địa</li>
              <li className="flex items-center gap-1.5"><CheckCircle2 className="w-3 h-3 text-emerald-500" /> Tích hợp API REST & Webhook</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
};
