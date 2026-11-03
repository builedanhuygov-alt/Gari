import React, { useState } from 'react';
import {
  UserCheck,
  Building2,
  Briefcase,
  Leaf,
  CheckCircle2,
  ChevronRight,
  X,
  Sparkles
} from 'lucide-react';
import type { UserRole, UserProfile } from '../types';

interface OnboardingModalProps {
  isOpen: boolean;
  onClose: () => void;
  onComplete: (profile: UserProfile, farmData?: any) => void;
}

export const OnboardingModal: React.FC<OnboardingModalProps> = ({
  isOpen,
  onClose,
  onComplete,
}) => {
  const [step, setStep] = useState<number>(1);
  const [role, setRole] = useState<UserRole>('FARMER');
  const [name, setName] = useState<string>('Bác Hai Nông');
  const [province, setProvince] = useState<string>('Lâm Đồng');
  const [farmName, setFarmName] = useState<string>('Vườn Rau Đơn Dương');
  const [areaHectare, setAreaHectare] = useState<number>(2.5);
  const [selectedCrops, setSelectedCrops] = useState<string[]>(['Tomato', 'Potato']);

  if (!isOpen) return null;

  const popularCrops = [
    { id: 'Tomato', name: 'Cà chua' },
    { id: 'Potato', name: 'Khoai tây' },
    { id: 'Rice', name: 'Lúa nước' },
    { id: 'Tea', name: 'Chè' },
    { id: 'Maize', name: 'Ngô' },
    { id: 'Coffee', name: 'Cà phê' },
    { id: 'Grape', name: 'Nho' },
    { id: 'Banana', name: 'Chuối' },
  ];

  const toggleCrop = (cropId: string) => {
    if (selectedCrops.includes(cropId)) {
      setSelectedCrops(selectedCrops.filter(c => c !== cropId));
    } else {
      setSelectedCrops([...selectedCrops, cropId]);
    }
  };

  const handleFinish = (includeFarm: boolean = true) => {
    const profile: UserProfile = {
      name: name.trim() || 'Nông dân Gari',
      role: role,
      province: province,
      hasCompletedOnboarding: true,
    };

    const farmData = includeFarm ? {
      name: farmName.trim() || 'Nông trại mẫu',
      location: province,
      province: province,
      area_hectare: areaHectare || 1.0,
      primary_crop: selectedCrops[0] || 'Tomato',
      notes: 'Được đăng ký tự động qua quy trình khởi tạo Gari AI Lab.'
    } : undefined;

    onComplete(profile, farmData);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 animate-fadeIn">
      <div className="bg-white dark:bg-[#121914] border border-[#E5EBE6] dark:border-[#202C23] rounded-2xl w-full max-w-xl shadow-2xl overflow-hidden flex flex-col text-slate-900 dark:text-slate-100">
        {/* Modal Header */}
        <div className="p-4 sm:p-5 border-b border-[#E5EBE6] dark:border-[#202C23] flex items-center justify-between bg-slate-50 dark:bg-[#0E1410]">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-700 dark:text-emerald-400">
              <Sparkles className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">Khởi Tạo Trải Nghiệm Gari AI Lab</h3>
              <p className="text-[11px] text-slate-500 dark:text-slate-400">Bước {step} / 5: Thiết lập nền tảng nông nghiệp</p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6">
          {/* Step 1: Role Selection */}
          {step === 1 && (
            <div className="flex flex-col gap-4">
              <div>
                <h4 className="text-base font-bold text-white mb-1">Chọn vai trò hoạt động của bạn</h4>
                <p className="text-xs text-slate-400">
                  Gari AI Lab tự động điều chỉnh các phân hệ nghiệp vụ phù hợp với mô hình canh tác.
                </p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <button
                  type="button"
                  onClick={() => setRole('FARMER')}
                  className={`p-4 rounded-xl border text-left transition flex flex-col justify-between gap-3 ${
                    role === 'FARMER'
                      ? 'border-emerald-500 bg-emerald-500/10 text-white'
                      : 'border-slate-800 bg-slate-950/40 text-slate-300 hover:border-slate-700'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <UserCheck className="w-5 h-5 text-emerald-400" />
                    {role === 'FARMER' && <CheckCircle2 className="w-4 h-4 text-emerald-400" />}
                  </div>
                  <div>
                    <span className="font-bold text-xs block">Nông Hộ Cá Thể</span>
                    <span className="text-[11px] text-slate-400">Chẩn đoán bệnh lá, theo dõi nông trại cá nhân.</span>
                  </div>
                </button>

                <button
                  type="button"
                  onClick={() => setRole('COOPERATIVE')}
                  className={`p-4 rounded-xl border text-left transition flex flex-col justify-between gap-3 ${
                    role === 'COOPERATIVE'
                      ? 'border-teal-500 bg-teal-500/10 text-white'
                      : 'border-slate-800 bg-slate-950/40 text-slate-300 hover:border-slate-700'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <Building2 className="w-5 h-5 text-teal-400" />
                    {role === 'COOPERATIVE' && <CheckCircle2 className="w-4 h-4 text-teal-400" />}
                  </div>
                  <div>
                    <span className="font-bold text-xs block">Hợp Tác Xã Nông Nghiệp</span>
                    <span className="text-[11px] text-slate-400">Quản lý nhiều nông hộ, tổng hợp dịch tễ vùng.</span>
                  </div>
                </button>

                <button
                  type="button"
                  onClick={() => setRole('AGRONOMIST')}
                  className={`p-4 rounded-xl border text-left transition flex flex-col justify-between gap-3 ${
                    role === 'AGRONOMIST'
                      ? 'border-cyan-500 bg-cyan-500/10 text-white'
                      : 'border-slate-800 bg-slate-950/40 text-slate-300 hover:border-slate-700'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <Leaf className="w-5 h-5 text-cyan-400" />
                    {role === 'AGRONOMIST' && <CheckCircle2 className="w-4 h-4 text-cyan-400" />}
                  </div>
                  <div>
                    <span className="font-bold text-xs block">Chuyên Gia / Kỹ Sư BVTV</span>
                    <span className="text-[11px] text-slate-400">Thẩm định dịch hại, tư vấn kỹ thuật thực địa.</span>
                  </div>
                </button>

                <button
                  type="button"
                  onClick={() => setRole('ENTERPRISE')}
                  className={`p-4 rounded-xl border text-left transition flex flex-col justify-between gap-3 ${
                    role === 'ENTERPRISE'
                      ? 'border-indigo-500 bg-indigo-500/10 text-white'
                      : 'border-slate-800 bg-slate-950/40 text-slate-300 hover:border-slate-700'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <Briefcase className="w-5 h-5 text-indigo-400" />
                    {role === 'ENTERPRISE' && <CheckCircle2 className="w-4 h-4 text-indigo-400" />}
                  </div>
                  <div>
                    <span className="font-bold text-xs block">Doanh Nghiệp Nông Nghiệp</span>
                    <span className="text-[11px] text-slate-400">Theo dõi chuỗi cung ứng, xuất báo cáo chuẩn hóa.</span>
                  </div>
                </button>
              </div>
            </div>
          )}

          {/* Step 2: User Profile Setup */}
          {step === 2 && (
            <div className="flex flex-col gap-4">
              <div>
                <h4 className="text-base font-bold text-white mb-1">Thông tin cá nhân / Đại diện</h4>
                <p className="text-xs text-slate-400">Giúp định danh các báo cáo và khuyến cáo kỹ thuật.</p>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1.5">Họ và tên / Tên đại diện:</label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3.5 py-2.5 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-emerald-500"
                  placeholder="Ví dụ: Nguyễn Văn An"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1.5">Tỉnh / Thành phố vùng canh tác:</label>
                <select
                  value={province}
                  onChange={(e) => setProvince(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3.5 py-2.5 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-emerald-500"
                >
                  <option value="Lâm Đồng">Lâm Đồng (Đà Lạt / Đơn Dương)</option>
                  <option value="Hà Nội">Hà Nội (Ba Vì / Mê Linh)</option>
                  <option value="Sơn La">Sơn La (Mộc Châu / Mai Sơn)</option>
                  <option value="An Giang">An Giang (ĐBSCL)</option>
                  <option value="Đắk Lắk">Đắk Lắk (Buôn Ma Thuột)</option>
                  <option value="Đồng Nai">Đồng Nai</option>
                  <option value="Khác">Khu vực khác</option>
                </select>
              </div>
            </div>
          )}

          {/* Step 3: Register First Farm or Skip */}
          {step === 3 && (
            <div className="flex flex-col gap-4">
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="text-base font-bold text-white mb-1">Đăng ký nông trại đầu tiên</h4>
                  <p className="text-xs text-slate-400">Liên kết các chẩn đoán AI vào nhật ký canh tác của nông trại.</p>
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1.5">Tên trang trại / Khu vườn:</label>
                <input
                  type="text"
                  value={farmName}
                  onChange={(e) => setFarmName(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3.5 py-2.5 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-emerald-500"
                  placeholder="Ví dụ: Trang trại Ba Vì Organic"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1.5">Quy mô diện tích (Hecta):</label>
                <input
                  type="number"
                  step="0.1"
                  min="0.1"
                  value={areaHectare}
                  onChange={(e) => setAreaHectare(parseFloat(e.target.value) || 1.0)}
                  className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3.5 py-2.5 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-emerald-500"
                />
              </div>
            </div>
          )}

          {/* Step 4: Primary Crops of Interest */}
          {step === 4 && (
            <div className="flex flex-col gap-4">
              <div>
                <h4 className="text-base font-bold text-white mb-1">Cây trồng quan tâm chính</h4>
                <p className="text-xs text-slate-400">Chọn các loại cây để Gari ưu tiên nạp sẵn mô hình AI vào bộ nhớ RAM.</p>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
                {popularCrops.map((c) => {
                  const isSelected = selectedCrops.includes(c.id);
                  return (
                    <button
                      key={c.id}
                      type="button"
                      onClick={() => toggleCrop(c.id)}
                      className={`p-3 rounded-xl border text-center transition flex flex-col items-center justify-center gap-1.5 ${
                        isSelected
                          ? 'border-emerald-500 bg-emerald-500/15 text-white font-bold'
                          : 'border-slate-800 bg-slate-950/40 text-slate-400 hover:text-slate-200 hover:border-slate-700'
                      }`}
                    >
                      <Leaf className={`w-4 h-4 ${isSelected ? 'text-emerald-400' : 'text-slate-500'}`} />
                      <span className="text-xs">{c.name}</span>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {/* Step 5: Ready to launch */}
          {step === 5 && (
            <div className="py-6 flex flex-col items-center justify-center text-center gap-3">
              <div className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-emerald-500 to-teal-400 flex items-center justify-center shadow-lg shadow-emerald-500/20 text-slate-950">
                <CheckCircle2 className="w-8 h-8 font-bold" />
              </div>
              <h4 className="text-lg font-extrabold text-white">Sẵn Sàng Khám Phá Gari AI Lab!</h4>
              <p className="text-xs text-slate-400 max-w-md">
                Tất cả 44 mô hình học máy ConvNeXt cục bộ, không gian nông trại và kho tri thức dịch tễ đã sẵn sàng phục vụ bạn.
              </p>
            </div>
          )}
        </div>

        {/* Modal Footer Controls */}
        <div className="p-5 border-t border-slate-800 flex items-center justify-between bg-slate-950/50">
          <div>
            {step < 5 ? (
              <button
                type="button"
                onClick={() => handleFinish(false)}
                className="text-xs font-semibold text-slate-400 hover:text-slate-200 transition"
              >
                Bỏ qua bước này
              </button>
            ) : null}
          </div>

          <div className="flex gap-2.5">
            {step > 1 && step < 5 && (
              <button
                type="button"
                onClick={() => setStep(step - 1)}
                className="px-4 py-2 rounded-xl text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-300 transition"
              >
                Quay lại
              </button>
            )}

            {step < 5 ? (
              <button
                type="button"
                onClick={() => setStep(step + 1)}
                className="px-5 py-2.5 rounded-xl text-xs font-bold bg-emerald-500 hover:bg-emerald-400 text-slate-950 flex items-center gap-1.5 transition shadow-lg shadow-emerald-500/20"
              >
                <span>Tiếp tục</span>
                <ChevronRight className="w-3.5 h-3.5" />
              </button>
            ) : (
              <button
                type="button"
                onClick={() => handleFinish(true)}
                className="px-6 py-2.5 rounded-xl text-xs font-bold bg-gradient-to-r from-emerald-500 to-teal-400 hover:from-emerald-400 hover:to-teal-300 text-slate-950 transition shadow-lg shadow-emerald-500/20"
              >
                Bắt đầu làm việc ngay
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
