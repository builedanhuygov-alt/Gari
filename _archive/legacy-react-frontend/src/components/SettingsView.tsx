import React, { useState } from 'react';
import {
  UserCheck,
  Cpu,
  ExternalLink,
  Check,
  ShieldCheck
} from 'lucide-react';
import type { UserProfile } from '../types';

interface SettingsViewProps {
  profile: UserProfile;
  onUpdateProfile: (updated: UserProfile) => void;
  device: string;
  modelsCount: number;
}

export const SettingsView: React.FC<SettingsViewProps> = ({
  profile,
  onUpdateProfile,
  device,
  modelsCount,
}) => {
  const [name, setName] = useState<string>(profile.name);
  const [province, setProvince] = useState<string>(profile.province || 'Lâm Đồng');
  const [organization, setOrganization] = useState<string>(profile.organization || 'Hợp tác xã Nông nghiệp Sạch');
  const [saved, setSaved] = useState<boolean>(false);

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    onUpdateProfile({
      ...profile,
      name: name.trim(),
      province: province.trim(),
      organization: organization.trim(),
    });
    setSaved(true);
    setTimeout(() => setSaved(false), 2500);
  };

  return (
    <div className="flex flex-col gap-5 max-w-4xl mx-auto w-full animate-fadeIn">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-2 border-b border-[#E5EBE6] dark:border-[#202C23]">
        <div>
          <h1 className="text-xl font-bold text-slate-900 dark:text-slate-100 tracking-tight">
            Cài Đặt & Hồ Sơ Hệ Thống
          </h1>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Quản trị định danh tài khoản, tổ chức và thông số phần cứng của động cơ AI cục bộ.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold px-2.5 py-1 rounded-lg bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border border-emerald-500/20">
            Gari AI Lab v2.5
          </span>
        </div>
      </div>

      {/* User Profile Form */}
      <div className="bg-white dark:bg-[#121914] border border-[#E5EBE6] dark:border-[#202C23] rounded-xl p-5 shadow-sm">
        <h3 className="text-xs font-bold text-slate-900 dark:text-slate-100 pb-2 mb-4 border-b border-[#E5EBE6] dark:border-[#202C23] flex items-center gap-2">
          <UserCheck className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
          <span>Thông tin cá nhân & Đơn vị công tác</span>
        </h3>

        <form onSubmit={handleSave} className="flex flex-col gap-3.5 text-xs">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
            <div>
              <label className="block font-medium text-slate-700 dark:text-slate-300 mb-1">
                Họ và tên người dùng:
              </label>
              <input
                type="text"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full bg-[#F7F9F7] dark:bg-[#162019] border border-[#E5EBE6] dark:border-[#202C23] rounded-lg px-3 py-1.5 text-slate-900 dark:text-slate-100 text-xs focus:outline-none focus:ring-1 focus:ring-emerald-500"
              />
            </div>

            <div>
              <label className="block font-medium text-slate-700 dark:text-slate-300 mb-1">
                Tỉnh / Thành phố vùng canh tác:
              </label>
              <input
                type="text"
                value={province}
                onChange={(e) => setProvince(e.target.value)}
                className="w-full bg-[#F7F9F7] dark:bg-[#162019] border border-[#E5EBE6] dark:border-[#202C23] rounded-lg px-3 py-1.5 text-slate-900 dark:text-slate-100 text-xs focus:outline-none focus:ring-1 focus:ring-emerald-500"
              />
            </div>
          </div>

          <div>
            <label className="block font-medium text-slate-700 dark:text-slate-300 mb-1">
              Tên Hợp tác xã / Doanh nghiệp nông nghiệp:
            </label>
            <input
              type="text"
              value={organization}
              onChange={(e) => setOrganization(e.target.value)}
              className="w-full bg-[#F7F9F7] dark:bg-[#162019] border border-[#E5EBE6] dark:border-[#202C23] rounded-lg px-3 py-1.5 text-slate-900 dark:text-slate-100 text-xs focus:outline-none focus:ring-1 focus:ring-emerald-500"
            />
          </div>

          <div className="flex justify-end gap-2 pt-2 border-t border-[#E5EBE6] dark:border-[#202C23]">
            <button
              type="submit"
              className="px-4 py-1.5 rounded-lg bg-[#166534] hover:bg-[#14532D] text-white font-semibold text-xs flex items-center gap-1.5 transition shadow-sm"
            >
              {saved && <Check className="w-3.5 h-3.5" />}
              <span>{saved ? 'Đã lưu thay đổi' : 'Cập nhật hồ sơ'}</span>
            </button>
          </div>
        </form>
      </div>

      {/* Hardware & AI Inference Specifications */}
      <div className="bg-white dark:bg-[#121914] border border-[#E5EBE6] dark:border-[#202C23] rounded-xl p-5 shadow-sm">
        <h3 className="text-xs font-bold text-slate-900 dark:text-slate-100 pb-2 mb-4 border-b border-[#E5EBE6] dark:border-[#202C23] flex items-center gap-2">
          <Cpu className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
          <span>Thông số động cơ trí tuệ nhân tạo (Gari Vision)</span>
        </h3>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs mb-4">
          <div className="p-3 bg-[#F7F9F7] dark:bg-[#162019] border border-[#E5EBE6] dark:border-[#202C23] rounded-lg">
            <span className="text-[10px] text-slate-400 block mb-0.5">Thiết bị tăng tốc suy luận:</span>
            <span className="font-bold text-emerald-700 dark:text-emerald-400 text-sm uppercase">{device || 'CPU (PyTorch)'}</span>
            <span className="text-[10px] text-slate-500 block mt-0.5">Xử lý cục bộ, bảo mật dữ liệu tuyệt đối</span>
          </div>

          <div className="p-3 bg-[#F7F9F7] dark:bg-[#162019] border border-[#E5EBE6] dark:border-[#202C23] rounded-lg">
            <span className="text-[10px] text-slate-400 block mb-0.5">Trọng số mô hình đã nạp:</span>
            <span className="font-bold text-slate-900 dark:text-slate-100 text-sm">{modelsCount || 44} Mô hình ConvNeXt</span>
            <span className="text-[10px] text-slate-500 block mt-0.5">Định dạng safetensors & PyTorch weights</span>
          </div>
        </div>

        <div className="p-3 bg-[#F7F9F7] dark:bg-[#162019] border border-[#E5EBE6] dark:border-[#202C23] rounded-lg text-xs space-y-1.5 text-slate-600 dark:text-slate-400">
          <div className="flex items-center justify-between">
            <span>Cấu trúc mạng nơ-ron:</span>
            <b className="text-slate-800 dark:text-slate-200 font-mono">ConvNeXt-Small (timm framework)</b>
          </div>
          <div className="flex items-center justify-between">
            <span>Độ phân giải đầu vào:</span>
            <b className="text-slate-800 dark:text-slate-200 font-mono">224 × 224 RGB (ImageNet Normalization)</b>
          </div>
          <div className="flex items-center justify-between">
            <span>Độ trễ suy luận trung bình:</span>
            <b className="text-emerald-700 dark:text-emerald-400 font-mono">&lt; 90 ms / ảnh</b>
          </div>
          <div className="flex items-center justify-between">
            <span>Kiểm định tri thức:</span>
            <b className="text-teal-700 dark:text-teal-400">Viện BVTV (NIPP) & FAO IPM Protocol</b>
          </div>
        </div>

        <div className="mt-4 pt-3 border-t border-[#E5EBE6] dark:border-[#202C23] flex items-center justify-between text-xs text-slate-500">
          <span className="flex items-center gap-1.5">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
            Hệ thống tuân thủ bảo vệ chủ quyền dữ liệu nông nghiệp theo quy định chuyển đổi số quốc gia.
          </span>
          <a
            href="/docs"
            target="_blank"
            rel="noreferrer"
            className="text-emerald-700 dark:text-emerald-400 hover:underline flex items-center gap-1"
          >
            <span>Tài liệu Swagger API</span>
            <ExternalLink className="w-3 h-3" />
          </a>
        </div>
      </div>
    </div>
  );
};
