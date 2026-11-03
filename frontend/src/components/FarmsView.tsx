import { useState } from 'react';
import {
  Building2,
  Plus,
  MapPin,
  Trash2,
  Zap,
  X,
  Layers,
  Droplet
} from 'lucide-react';
import type { Farm } from '../types';

interface FarmsViewProps {
  farms: Farm[];
  onAddFarm: (farmData: any) => Promise<void>;
  onDeleteFarm: (farmId: number) => Promise<void>;
  onSelectFarmForDiagnosis: (farmId: number, crop: string) => void;
}

export const FarmsView: React.FC<FarmsViewProps> = ({
  farms,
  onAddFarm,
  onDeleteFarm,
  onSelectFarmForDiagnosis,
}) => {
  const [showAddModal, setShowAddModal] = useState<boolean>(false);
  const [name, setName] = useState<string>('');
  const [province, setProvince] = useState<string>('Lâm Đồng');
  const [location, setLocation] = useState<string>('');
  const [areaHectare, setAreaHectare] = useState<number>(2.5);
  const [primaryCrop, setPrimaryCrop] = useState<string>('Tomato');
  const [variety, _setVariety] = useState<string>('');
  const [soilType, setSoilType] = useState<string>('Đất đỏ bazan');
  const [irrigationType, _setIrrigationType] = useState<string>('Tưới nhỏ giọt');
  const [notes, setNotes] = useState<string>('');
  const [saving, setSaving] = useState<boolean>(false);

  const totalHectares = farms.reduce((acc, f) => acc + (f.area_hectare || 0), 0);
  const totalDiagnosesCount = farms.reduce((acc, f) => acc + (f.total_diagnoses || (f.diagnoses ? f.diagnoses.length : 0)), 0);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    setSaving(true);
    try {
      await onAddFarm({
        name: name.trim(),
        location: location.trim() || province,
        province: province,
        area_hectare: areaHectare || 1.0,
        primary_crop: primaryCrop,
        variety: variety.trim(),
        soil_type: soilType,
        irrigation_type: irrigationType,
        notes: notes.trim(),
      });
      setShowAddModal(false);
      setName('');
      setLocation('');
      setNotes('');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex flex-col gap-5 animate-fadeIn">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-2 border-b border-[#E5EBE6] dark:border-[#202C23]">
        <div>
          <h1 className="text-xl font-bold text-slate-900 dark:text-slate-100 tracking-tight">
            Nông Trại Của Tôi
          </h1>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Quản trị hồ sơ lô đất, quy mô diện tích canh tác và nhật ký chẩn đoán sâu bệnh theo mùa vụ.
          </p>
        </div>

        <button
          type="button"
          onClick={() => setShowAddModal(true)}
          className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-[#166534] hover:bg-[#14532D] text-white font-semibold text-xs transition shadow-sm self-start sm:self-auto"
        >
          <Plus className="w-3.5 h-3.5" />
          <span>Thêm nông trại</span>
        </button>
      </div>

      {/* Summary KPI Strip */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3.5">
        <div className="p-3.5 rounded-xl bg-white dark:bg-[#121914] border border-[#E5EBE6] dark:border-[#202C23] shadow-sm flex items-center justify-between">
          <div>
            <span className="text-[11px] text-slate-500 dark:text-slate-400 font-medium">Trang trại quản lý</span>
            <div className="text-xl font-bold text-slate-900 dark:text-slate-100 mt-0.5">{farms.length} cơ sở</div>
          </div>
          <Building2 className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
        </div>

        <div className="p-3.5 rounded-xl bg-white dark:bg-[#121914] border border-[#E5EBE6] dark:border-[#202C23] shadow-sm flex items-center justify-between">
          <div>
            <span className="text-[11px] text-slate-500 dark:text-slate-400 font-medium">Tổng diện tích</span>
            <div className="text-xl font-bold text-slate-900 dark:text-slate-100 mt-0.5">{totalHectares.toFixed(1)} ha</div>
          </div>
          <Layers className="w-5 h-5 text-teal-600 dark:text-teal-400" />
        </div>

        <div className="p-3.5 rounded-xl bg-white dark:bg-[#121914] border border-[#E5EBE6] dark:border-[#202C23] shadow-sm flex items-center justify-between">
          <div>
            <span className="text-[11px] text-slate-500 dark:text-slate-400 font-medium">Mẫu lá đã quét AI</span>
            <div className="text-xl font-bold text-emerald-700 dark:text-emerald-400 mt-0.5">{totalDiagnosesCount} mẫu</div>
          </div>
          <Zap className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
        </div>
      </div>

      {/* Farms Grid or Empty State */}
      {farms.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {farms.map((farm) => {
            const totalDiag = farm.total_diagnoses || (farm.diagnoses ? farm.diagnoses.length : 0);
            return (
              <div
                key={farm.id}
                className="bg-white dark:bg-[#121914] border border-[#E5EBE6] dark:border-[#202C23] hover:border-[#166534]/40 dark:hover:border-emerald-500/40 rounded-xl p-4 shadow-sm hover:shadow-md transition flex flex-col justify-between group"
              >
                <div>
                  <div className="flex items-start justify-between gap-3 mb-2.5">
                    <div className="flex items-center gap-2.5">
                      <div className="w-9 h-9 rounded-lg bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 flex items-center justify-center font-bold">
                        <Building2 className="w-4 h-4" />
                      </div>
                      <div>
                        <h3 className="font-bold text-sm text-slate-900 dark:text-slate-100 group-hover:text-emerald-700 dark:group-hover:text-emerald-400 transition leading-tight">
                          {farm.name}
                        </h3>
                        <div className="text-[11px] text-slate-500 dark:text-slate-400 flex items-center gap-1 mt-0.5">
                          <MapPin className="w-3 h-3 text-emerald-600 dark:text-emerald-400" />
                          <span>{farm.location || farm.province}</span>
                        </div>
                      </div>
                    </div>

                    <button
                      type="button"
                      onClick={() => onDeleteFarm(farm.id)}
                      className="p-1 text-slate-400 hover:text-red-500 rounded transition"
                      title="Xóa nông trại này"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>

                  {/* Farm Attributes */}
                  <div className="grid grid-cols-2 gap-2 my-3 text-[11px] bg-[#F7F9F7] dark:bg-[#162019] p-2.5 rounded-lg border border-[#E5EBE6] dark:border-[#202C23]">
                    <div>
                      <span className="text-slate-400 block text-[10px]">Cây trồng chính:</span>
                      <span className="font-semibold text-slate-800 dark:text-slate-200">{farm.primary_crop}</span>
                    </div>
                    <div>
                      <span className="text-slate-400 block text-[10px]">Quy mô:</span>
                      <span className="font-semibold text-emerald-700 dark:text-emerald-400">{farm.area_hectare} ha</span>
                    </div>
                    <div>
                      <span className="text-slate-400 block text-[10px]">Thổ nhưỡng:</span>
                      <span className="font-medium text-slate-700 dark:text-slate-300 truncate block">{farm.soil_type || 'Đất phù sa'}</span>
                    </div>
                    <div>
                      <span className="text-slate-400 block text-[10px]">Tưới tiêu:</span>
                      <span className="font-medium text-slate-700 dark:text-slate-300 truncate block flex items-center gap-1">
                        <Droplet className="w-2.5 h-2.5 text-teal-500" />
                        {farm.irrigation_type || 'Tưới nhỏ giọt'}
                      </span>
                    </div>
                  </div>

                  {farm.notes && (
                    <p className="text-[11px] text-slate-500 dark:text-slate-400 italic line-clamp-2 mb-2">
                      "{farm.notes}"
                    </p>
                  )}
                </div>

                {/* Footer Link to AI Diagnosis */}
                <div className="pt-3 border-t border-[#E5EBE6] dark:border-[#202C23] flex items-center justify-between text-xs">
                  <span className="text-slate-400 text-[11px]">
                    Lịch sử: <b className="text-slate-700 dark:text-slate-300">{totalDiag}</b> mẫu đã quét
                  </span>

                  <button
                    type="button"
                    onClick={() => onSelectFarmForDiagnosis(farm.id, farm.primary_crop)}
                    className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-700 dark:text-emerald-400 hover:text-emerald-800 dark:hover:text-emerald-300 transition"
                  >
                    <span>Quét AI ngay</span>
                    <Zap className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="py-16 text-center text-xs text-slate-500 dark:text-slate-400 bg-white dark:bg-[#121914] border border-[#E5EBE6] dark:border-[#202C23] rounded-xl flex flex-col items-center">
          <Building2 className="w-8 h-8 text-slate-400 mb-2" />
          <p className="font-semibold text-slate-800 dark:text-slate-200">Chưa có nông trại nào được đăng ký</p>
          <p className="text-[11px] text-slate-400 max-w-sm mt-1">
            Bấm "Thêm nông trại" để ghi nhận thông tin thổ nhưỡng, diện tích và liên kết chẩn đoán sâu bệnh.
          </p>
          <button
            type="button"
            onClick={() => setShowAddModal(true)}
            className="mt-3 px-3 py-1.5 rounded-lg bg-[#166534] text-white text-xs font-semibold"
          >
            + Thêm trang trại đầu tiên
          </button>
        </div>
      )}

      {/* Add Farm Dialog */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 animate-fadeIn">
          <div className="bg-white dark:bg-[#121914] border border-[#E5EBE6] dark:border-[#202C23] rounded-xl w-full max-w-lg shadow-2xl p-5">
            <div className="flex items-center justify-between border-b border-[#E5EBE6] dark:border-[#202C23] pb-3 mb-4">
              <h3 className="font-bold text-sm text-slate-900 dark:text-slate-100 flex items-center gap-2">
                <Building2 className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
                <span>Đăng ký hồ sơ nông trại mới</span>
              </h3>
              <button
                type="button"
                onClick={() => setShowAddModal(false)}
                className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 p-1"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleSubmit} className="flex flex-col gap-3 text-xs">
              <div>
                <label className="block font-medium text-slate-700 dark:text-slate-300 mb-1">
                  Tên nông trại / Cơ sở canh tác:
                </label>
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Ví dụ: Trang Trại Chè Cầu Đất"
                  className="w-full bg-[#F7F9F7] dark:bg-[#162019] border border-[#E5EBE6] dark:border-[#202C23] rounded-lg px-3 py-1.5 text-slate-900 dark:text-slate-100 text-xs focus:outline-none focus:ring-1 focus:ring-emerald-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-medium text-slate-700 dark:text-slate-300 mb-1">
                    Tỉnh / Thành phố:
                  </label>
                  <select
                    value={province}
                    onChange={(e) => setProvince(e.target.value)}
                    className="w-full bg-[#F7F9F7] dark:bg-[#162019] border border-[#E5EBE6] dark:border-[#202C23] rounded-lg px-2.5 py-1.5 text-slate-900 dark:text-slate-100 text-xs focus:outline-none focus:ring-1 focus:ring-emerald-500"
                  >
                    <option value="Lâm Đồng">Lâm Đồng</option>
                    <option value="Hà Nội">Hà Nội</option>
                    <option value="Sơn La">Sơn La</option>
                    <option value="An Giang">An Giang</option>
                    <option value="Đắk Lắk">Đắk Lắk</option>
                    <option value="Đồng Nai">Đồng Nai</option>
                    <option value="Gia Lai">Gia Lai</option>
                  </select>
                </div>

                <div>
                  <label className="block font-medium text-slate-700 dark:text-slate-300 mb-1">
                    Quy mô diện tích (ha):
                  </label>
                  <input
                    type="number"
                    step="0.1"
                    min="0.1"
                    required
                    value={areaHectare}
                    onChange={(e) => setAreaHectare(parseFloat(e.target.value) || 1.0)}
                    className="w-full bg-[#F7F9F7] dark:bg-[#162019] border border-[#E5EBE6] dark:border-[#202C23] rounded-lg px-3 py-1.5 text-slate-900 dark:text-slate-100 text-xs focus:outline-none focus:ring-1 focus:ring-emerald-500"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-medium text-slate-700 dark:text-slate-300 mb-1">
                    Cây trồng chủ lực:
                  </label>
                  <input
                    type="text"
                    required
                    value={primaryCrop}
                    onChange={(e) => setPrimaryCrop(e.target.value)}
                    placeholder="Ví dụ: Tomato, Rice, Tea..."
                    className="w-full bg-[#F7F9F7] dark:bg-[#162019] border border-[#E5EBE6] dark:border-[#202C23] rounded-lg px-3 py-1.5 text-slate-900 dark:text-slate-100 text-xs focus:outline-none focus:ring-1 focus:ring-emerald-500"
                  />
                </div>

                <div>
                  <label className="block font-medium text-slate-700 dark:text-slate-300 mb-1">
                    Thổ nhưỡng đất:
                  </label>
                  <input
                    type="text"
                    value={soilType}
                    onChange={(e) => setSoilType(e.target.value)}
                    placeholder="Ví dụ: Đất đỏ bazan, phù sa..."
                    className="w-full bg-[#F7F9F7] dark:bg-[#162019] border border-[#E5EBE6] dark:border-[#202C23] rounded-lg px-3 py-1.5 text-slate-900 dark:text-slate-100 text-xs focus:outline-none focus:ring-1 focus:ring-emerald-500"
                  />
                </div>
              </div>

              <div>
                <label className="block font-medium text-slate-700 dark:text-slate-300 mb-1">
                  Ghi chú hoặc địa chỉ cụ thể:
                </label>
                <textarea
                  rows={2}
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="Thông tin thêm về địa hình, giống cây trồng..."
                  className="w-full bg-[#F7F9F7] dark:bg-[#162019] border border-[#E5EBE6] dark:border-[#202C23] rounded-lg px-3 py-1.5 text-slate-900 dark:text-slate-100 text-xs focus:outline-none focus:ring-1 focus:ring-emerald-500"
                />
              </div>

              <div className="pt-3 border-t border-[#E5EBE6] dark:border-[#202C23] flex items-center justify-end gap-2 mt-2">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="px-3 py-1.5 rounded-lg border border-[#E5EBE6] dark:border-[#202C23] text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-[#1A241C]"
                >
                  Hủy bỏ
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  className="px-4 py-1.5 rounded-lg bg-[#166534] hover:bg-[#14532D] text-white font-semibold shadow-sm"
                >
                  {saving ? 'Đang lưu...' : 'Lưu hồ sơ'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
