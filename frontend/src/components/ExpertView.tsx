import React, { useState, useEffect } from 'react';
import {
  Stethoscope,
  Plus,
  CheckCircle2,
  X,
  Clock,
  AlertCircle
} from 'lucide-react';
import type { ExpertCase, Farm } from '../types';

interface ExpertViewProps {
  farms: Farm[];
  initialCaseData?: any;
  onClearInitialCaseData?: () => void;
}

export const ExpertView: React.FC<ExpertViewProps> = ({
  farms,
  initialCaseData,
  onClearInitialCaseData,
}) => {
  const [cases, setCases] = useState<ExpertCase[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [showModal, setShowModal] = useState<boolean>(false);

  // Form states
  const [farmerName, setFarmerName] = useState<string>('Nguyễn Văn An');
  const [phone, setPhone] = useState<string>('0912 345 678');
  const [farmId, setFarmId] = useState<string>('');
  const [cropName, setCropName] = useState<string>('Cà chua');
  const [suspectedDisease, setSuspectedDisease] = useState<string>('');
  const [symptoms, setSymptoms] = useState<string>('');
  const [fieldConditions, setFieldConditions] = useState<string>('');
  const [submitting, setSubmitting] = useState<boolean>(false);

  useEffect(() => {
    fetchCases();
  }, []);

  useEffect(() => {
    if (initialCaseData) {
      setCropName(initialCaseData.crop_name || initialCaseData.crop || 'Cà chua');
      setSuspectedDisease(initialCaseData.predicted_disease || initialCaseData.prediction || '');
      setSymptoms(`Chẩn đoán AI ban đầu: ${initialCaseData.predicted_disease || initialCaseData.prediction} (Độ tin cậy: ${(initialCaseData.confidence * 100).toFixed(1)}%). Cần ý kiến chuyên môn thực địa.`);
      setShowModal(true);
    }
  }, [initialCaseData]);

  const fetchCases = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/expert/cases');
      if (res.ok) {
        const data = await res.json();
        setCases(data.cases || []);
      }
    } catch (e) {
      console.warn('Could not fetch expert cases:', e);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!symptoms.trim()) return;
    setSubmitting(true);

    const selectedFarm = farms.find(f => f.id === parseInt(farmId, 10));

    try {
      const res = await fetch('/api/expert/cases', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          farmer_name: farmerName.trim(),
          phone: phone.trim(),
          farm_id: selectedFarm ? selectedFarm.id : null,
          farm_name: selectedFarm ? selectedFarm.name : 'Vườn cá nhân',
          crop_name: cropName.trim(),
          suspected_disease: suspectedDisease.trim(),
          symptoms_description: symptoms.trim(),
          field_conditions: fieldConditions.trim(),
        }),
      });

      if (res.ok) {
        setShowModal(false);
        setSymptoms('');
        setFieldConditions('');
        if (onClearInitialCaseData) onClearInitialCaseData();
        fetchCases();
      }
    } catch (err) {
      console.error('Error submitting expert case:', err);
    } finally {
      setSubmitting(false);
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'Submitted':
        return <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300">Đã tiếp nhận</span>;
      case 'Under review':
        return <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-700 dark:text-amber-400">Đang thẩm định</span>;
      case 'More information required':
        return <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-700 dark:text-blue-400">Cần thêm mẫu ảnh</span>;
      case 'Resolved':
        return <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-700 dark:text-emerald-400">Đã có kết luận</span>;
      default:
        return <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300">{status}</span>;
    }
  };

  return (
    <div className="flex flex-col gap-5 animate-fadeIn">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-2 border-b border-[#E5EBE6] dark:border-[#202C23]">
        <div>
          <h1 className="text-xl font-bold text-slate-900 dark:text-slate-100 tracking-tight">
            Thẩm Định Chuyên Gia Bảo Vệ Thực Vật
          </h1>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Kết nối các trường hợp tổn thương khó nhận biết tới mạng lưới kỹ sư BVTV và cơ quan chuyên môn.
          </p>
        </div>

        <button
          type="button"
          onClick={() => setShowModal(true)}
          className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-[#166534] hover:bg-[#14532D] text-white font-semibold text-xs transition shadow-sm self-start sm:self-auto"
        >
          <Plus className="w-3.5 h-3.5" />
          <span>Gửi ca khám mới</span>
        </button>
      </div>

      {/* Advisory Note */}
      <div className="p-3 rounded-xl bg-white dark:bg-[#121914] border border-[#E5EBE6] dark:border-[#202C23] text-xs text-slate-600 dark:text-slate-400 flex items-center justify-between">
        <span className="flex items-center gap-1.5">
          <Clock className="w-3.5 h-3.5 text-amber-500" />
          Thời gian phản hồi thông thường: 2 - 4 giờ làm việc. Ưu tiên các ca bùng phát diện rộng.
        </span>
        <span className="text-[11px] font-semibold text-emerald-700 dark:text-emerald-400">
          {cases.length} Hồ sơ đang lưu
        </span>
      </div>

      {/* Cases List */}
      <div className="space-y-3">
        {loading ? (
          <div className="py-12 text-center text-xs text-slate-400">Đang nạp danh sách ca thẩm định...</div>
        ) : cases.length > 0 ? (
          cases.map((c) => (
            <div
              key={c.id}
              className="p-4 bg-white dark:bg-[#121914] border border-[#E5EBE6] dark:border-[#202C23] rounded-xl shadow-sm flex flex-col gap-2.5"
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs font-bold text-slate-900 dark:text-slate-100">Hồ sơ #{c.id}</span>
                    {getStatusBadge(c.status)}
                    <span className="text-[10px] text-slate-400">
                      {new Date(c.created_at).toLocaleDateString('vi-VN')}
                    </span>
                  </div>
                  <h4 className="text-sm font-bold text-slate-900 dark:text-slate-100">
                    {c.crop_name} • {c.suspected_disease || 'Triệu chứng tổn thương chưa rõ'}
                  </h4>
                  <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">
                    Người gửi: <b>{c.farmer_name}</b> ({c.phone || 'Chưa có SĐT'}) • Trang trại: <b>{c.farm_name || 'Vườn cá nhân'}</b>
                  </p>
                </div>

                {c.assigned_expert && (
                  <div className="text-right shrink-0 bg-[#F7F9F7] dark:bg-[#162019] p-2 rounded-lg border border-[#E5EBE6] dark:border-[#202C23]">
                    <span className="text-[9px] text-slate-400 block uppercase font-medium">Chuyên gia phụ trách</span>
                    <span className="text-xs font-semibold text-emerald-700 dark:text-emerald-400">{c.assigned_expert}</span>
                  </div>
                )}
              </div>

              <div className="p-2.5 bg-[#F7F9F7] dark:bg-[#162019] border border-[#E5EBE6] dark:border-[#202C23] rounded-lg text-xs text-slate-700 dark:text-slate-300">
                <span className="font-semibold text-slate-800 dark:text-slate-200 block mb-0.5">Mô tả triệu chứng thực tế:</span>
                <p className="leading-relaxed text-[11px] text-slate-600 dark:text-slate-400">{c.symptoms_description}</p>
                {c.field_conditions && (
                  <p className="mt-1 text-[10px] text-slate-500">
                    <b>Điều kiện thực địa:</b> {c.field_conditions}
                  </p>
                )}
              </div>

              {c.expert_notes && (
                <div className="p-2.5 bg-emerald-50 dark:bg-emerald-950/20 border border-emerald-200 dark:border-emerald-900/40 rounded-lg text-xs text-emerald-900 dark:text-emerald-200">
                  <span className="font-bold block mb-0.5 flex items-center gap-1.5 text-emerald-800 dark:text-emerald-300">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                    <span>Ý kiến chuyên môn từ kỹ sư:</span>
                  </span>
                  <p className="leading-relaxed text-[11px]">{c.expert_notes}</p>
                </div>
              )}
            </div>
          ))
        ) : (
          <div className="py-16 text-center text-xs text-slate-400 bg-white dark:bg-[#121914] border border-[#E5EBE6] dark:border-[#202C23] rounded-xl flex flex-col items-center">
            <AlertCircle className="w-8 h-8 text-slate-400 mb-2" />
            <p className="font-semibold text-slate-800 dark:text-slate-200">Chưa có ca thẩm định nào</p>
            <p className="text-[11px] text-slate-400 mt-0.5">Nhấp "Gửi ca khám mới" để kết nối kỹ sư BVTV.</p>
          </div>
        )}
      </div>

      {/* Case Submission Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 animate-fadeIn">
          <div className="bg-white dark:bg-[#121914] border border-[#E5EBE6] dark:border-[#202C23] rounded-xl w-full max-w-lg shadow-2xl p-5">
            <div className="flex items-center justify-between border-b border-[#E5EBE6] dark:border-[#202C23] pb-3 mb-4">
              <h3 className="font-bold text-sm text-slate-900 dark:text-slate-100 flex items-center gap-2">
                <Stethoscope className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
                <span>Gửi mẫu bệnh đến chuyên gia BVTV</span>
              </h3>
              <button
                type="button"
                onClick={() => setShowModal(false)}
                className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 p-1"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleSubmit} className="flex flex-col gap-3 text-xs">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-medium text-slate-700 dark:text-slate-300 mb-1">Họ tên người gửi:</label>
                  <input
                    type="text"
                    required
                    value={farmerName}
                    onChange={(e) => setFarmerName(e.target.value)}
                    className="w-full bg-[#F7F9F7] dark:bg-[#162019] border border-[#E5EBE6] dark:border-[#202C23] rounded-lg px-2.5 py-1.5 text-slate-900 dark:text-slate-100 text-xs focus:outline-none focus:ring-1 focus:ring-emerald-500"
                  />
                </div>

                <div>
                  <label className="block font-medium text-slate-700 dark:text-slate-300 mb-1">Số điện thoại liên hệ:</label>
                  <input
                    type="tel"
                    required
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    className="w-full bg-[#F7F9F7] dark:bg-[#162019] border border-[#E5EBE6] dark:border-[#202C23] rounded-lg px-2.5 py-1.5 text-slate-900 dark:text-slate-100 text-xs focus:outline-none focus:ring-1 focus:ring-emerald-500"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-medium text-slate-700 dark:text-slate-300 mb-1">Cây trồng:</label>
                  <input
                    type="text"
                    required
                    value={cropName}
                    onChange={(e) => setCropName(e.target.value)}
                    className="w-full bg-[#F7F9F7] dark:bg-[#162019] border border-[#E5EBE6] dark:border-[#202C23] rounded-lg px-2.5 py-1.5 text-slate-900 dark:text-slate-100 text-xs focus:outline-none focus:ring-1 focus:ring-emerald-500"
                  />
                </div>

                <div>
                  <label className="block font-medium text-slate-700 dark:text-slate-300 mb-1">Liên kết nông trại:</label>
                  <select
                    value={farmId}
                    onChange={(e) => setFarmId(e.target.value)}
                    className="w-full bg-[#F7F9F7] dark:bg-[#162019] border border-[#E5EBE6] dark:border-[#202C23] rounded-lg px-2.5 py-1.5 text-slate-900 dark:text-slate-100 text-xs focus:outline-none focus:ring-1 focus:ring-emerald-500"
                  >
                    <option value="">Vườn cá nhân / Khác</option>
                    {farms.map((f) => (
                      <option key={f.id} value={f.id}>
                        {f.name} ({f.province})
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div>
                <label className="block font-medium text-slate-700 dark:text-slate-300 mb-1">Bệnh nghi ngờ / Phỏng đoán ban đầu:</label>
                <input
                  type="text"
                  value={suspectedDisease}
                  onChange={(e) => setSuspectedDisease(e.target.value)}
                  placeholder="Ví dụ: Đốm vi khuẩn, thán thư..."
                  className="w-full bg-[#F7F9F7] dark:bg-[#162019] border border-[#E5EBE6] dark:border-[#202C23] rounded-lg px-2.5 py-1.5 text-slate-900 dark:text-slate-100 text-xs focus:outline-none focus:ring-1 focus:ring-emerald-500"
                />
              </div>

              <div>
                <label className="block font-medium text-slate-700 dark:text-slate-300 mb-1">Mô tả triệu chứng chi tiết:</label>
                <textarea
                  rows={3}
                  required
                  value={symptoms}
                  onChange={(e) => setSymptoms(e.target.value)}
                  placeholder="Mô tả màu sắc đốm lá, mức độ lan rộng..."
                  className="w-full bg-[#F7F9F7] dark:bg-[#162019] border border-[#E5EBE6] dark:border-[#202C23] rounded-lg px-2.5 py-1.5 text-slate-900 dark:text-slate-100 text-xs focus:outline-none focus:ring-1 focus:ring-emerald-500"
                />
              </div>

              <div>
                <label className="block font-medium text-slate-700 dark:text-slate-300 mb-1">Điều kiện thời tiết & chăm sóc:</label>
                <input
                  type="text"
                  value={fieldConditions}
                  onChange={(e) => setFieldConditions(e.target.value)}
                  placeholder="Ví dụ: Vừa qua đợt mưa rào 3 ngày, bón phân đạm cao..."
                  className="w-full bg-[#F7F9F7] dark:bg-[#162019] border border-[#E5EBE6] dark:border-[#202C23] rounded-lg px-2.5 py-1.5 text-slate-900 dark:text-slate-100 text-xs focus:outline-none focus:ring-1 focus:ring-emerald-500"
                />
              </div>

              <div className="pt-3 border-t border-[#E5EBE6] dark:border-[#202C23] flex items-center justify-end gap-2 mt-2">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="px-3 py-1.5 rounded-lg border border-[#E5EBE6] dark:border-[#202C23] text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-[#1A241C]"
                >
                  Hủy bỏ
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-4 py-1.5 rounded-lg bg-[#166534] hover:bg-[#14532D] text-white font-semibold shadow-sm"
                >
                  {submitting ? 'Đang gửi...' : 'Gửi hồ sơ'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
