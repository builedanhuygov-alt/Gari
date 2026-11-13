import React, { useState, useRef } from 'react';
import {
  Upload,
  RefreshCw,
  Zap,
  AlertTriangle,
  FileText,
  ShieldCheck,
  Stethoscope,
  BookOpen,
  Image as ImageIcon,
  Trash2
} from 'lucide-react';
import type { Farm, ModelInfo, PredictionResponse } from '../types';

interface VisionViewProps {
  models: ModelInfo[];
  farms: Farm[];
  initialCropId?: string;
  onOpenExpertCase: (prediction: PredictionResponse) => void;
  onRefreshStats?: () => void;
}

export const VisionView: React.FC<VisionViewProps> = ({
  models,
  farms,
  initialCropId,
  onOpenExpertCase,
  onRefreshStats,
}) => {
  const [selectedCrop, setSelectedCrop] = useState<string>(initialCropId || 'auto');
  const [selectedFarmId, setSelectedFarmId] = useState<string>('');
  const [fieldNotes, setFieldNotes] = useState<string>('');
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [prediction, setPrediction] = useState<PredictionResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dragActive, setDragActive] = useState<boolean>(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      processFile(e.target.files[0]);
    }
  };

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      processFile(e.dataTransfer.files[0]);
    }
  };

  const processFile = (file: File) => {
    const validTypes = ['image/jpeg', 'image/png', 'image/webp', 'image/jpg'];
    if (!validTypes.includes(file.type)) {
      setError('Định dạng tệp không được hỗ trợ. Vui lòng tải lên ảnh JPG, PNG hoặc WEBP.');
      return;
    }
    if (file.size > 15 * 1024 * 1024) {
      setError('Dung lượng tệp vượt quá 15MB. Vui lòng chọn ảnh nhỏ hơn.');
      return;
    }

    setError(null);
    setImageFile(file);
    const reader = new FileReader();
    reader.onload = (e) => {
      setImagePreview(e.target?.result as string);
    };
    reader.readAsDataURL(file);
    setPrediction(null);
  };

  const handleRunDiagnosis = async () => {
    if (!imageFile) {
      setError('Vui lòng chọn hoặc kéo thả một ảnh lá cây trước.');
      return;
    }

    setLoading(true);
    setError(null);
    setPrediction(null);

    const formData = new FormData();
    formData.append('image', imageFile);
    formData.append('crop', selectedCrop || 'auto');
    if (selectedFarmId) {
      formData.append('farm_id', selectedFarmId);
    }
    if (fieldNotes) {
      formData.append('notes', fieldNotes);
    }
    formData.append('save_history', 'true');

    try {
      const token = localStorage.getItem('gari_token') || sessionStorage.getItem('gari_token');
      const headers: Record<string, string> = {};
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }

      const res = await fetch('/api/predict', {
        method: 'POST',
        headers,
        credentials: 'include',
        body: formData,
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || data.message || 'Chẩn đoán thất bại.');
      }

      setPrediction(data);
      if (onRefreshStats) onRefreshStats();
    } catch (err: any) {
      setError(err.message || 'Lỗi kết nối máy chủ chẩn đoán.');
    } finally {
      setLoading(false);
    }
  };

  const handleDownloadReport = () => {
    if (!prediction) return;
    const blob = new Blob([JSON.stringify(prediction, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `gari-ai-lab-report-${prediction.crop || 'crop'}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleReset = () => {
    setImageFile(null);
    setImagePreview(null);
    setPrediction(null);
    setError(null);
    setFieldNotes('');
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const selectedModelInfo = models.find(m => m.crop_id.toLowerCase() === selectedCrop.toLowerCase());
  const isConfidenceUncertain = prediction && prediction.confidence < 0.75;

  return (
    <div className="flex flex-col gap-5 animate-fadeIn">
      {/* Header bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-2 border-b border-[#E5EBE6] dark:border-[#202C23]">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-700 dark:text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded">
              Không gian chẩn đoán
            </span>
            <span className="text-xs text-slate-400 dark:text-slate-500">•</span>
            <span className="text-xs text-slate-500 dark:text-slate-400">Gari Vision Engine</span>
          </div>
          <h1 className="text-xl font-bold text-slate-900 dark:text-slate-100 tracking-tight">
            Chẩn Đoán Sâu Bệnh Lá Cây Trồng
          </h1>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Mạng nơ-ron tích chập ConvNeXt cục bộ nhận diện 42 cây trồng với độ chính xác cao.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold px-2.5 py-1 rounded-lg bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border border-emerald-500/20">
            {models.length} Mô hình cục bộ sẵn sàng
          </span>
        </div>
      </div>

      {/* Main Split Layout: Left Upload Zone | Right Controls & Diagnosis Results */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        {/* LEFT COLUMN: Upload Zone (5 cols) */}
        <div className="lg:col-span-5 flex flex-col gap-4">
          <div className="bg-white dark:bg-[#121914] border border-[#E5EBE6] dark:border-[#202C23] rounded-xl p-4 shadow-sm">
            <div className="flex items-center justify-between pb-3 mb-3 border-b border-[#E5EBE6] dark:border-[#202C23]">
              <span className="text-xs font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                <ImageIcon className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
                <span>Ảnh chụp mẫu lá</span>
              </span>
              {imagePreview && (
                <button
                  type="button"
                  onClick={handleReset}
                  className="text-[11px] text-red-600 dark:text-red-400 hover:underline flex items-center gap-1"
                >
                  <Trash2 className="w-3 h-3" />
                  <span>Xóa ảnh</span>
                </button>
              )}
            </div>

            {/* Drag & Drop Upload Zone */}
            <div
              onDragEnter={handleDrag}
              onDragLeave={handleDrag}
              onDragOver={handleDrag}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              className={`relative border-2 border-dashed rounded-xl p-5 text-center cursor-pointer transition flex flex-col items-center justify-center min-h-[260px] ${
                dragActive
                  ? 'border-emerald-500 bg-emerald-50/50 dark:bg-emerald-950/20'
                  : 'border-[#E5EBE6] dark:border-[#253229] hover:border-emerald-500/60 bg-[#F7F9F7] dark:bg-[#162019]'
              }`}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept="image/jpeg,image/png,image/webp"
                onChange={handleFileChange}
                className="hidden"
              />

              {imagePreview ? (
                <div className="relative w-full flex flex-col items-center">
                  <img
                    src={imagePreview}
                    alt="Leaf Preview"
                    className="max-h-60 rounded-lg object-contain shadow-sm border border-[#E5EBE6] dark:border-[#202C23]"
                  />
                  <div className="mt-3 text-xs text-slate-700 dark:text-slate-300 font-medium">
                    {imageFile?.name} ({(imageFile!.size / 1024).toFixed(1)} KB)
                  </div>
                  <span className="text-[11px] text-emerald-700 dark:text-emerald-400 mt-0.5">
                    Nhấp hoặc kéo thả để thay đổi ảnh
                  </span>
                </div>
              ) : (
                <div className="flex flex-col items-center gap-2.5">
                  <div className="w-12 h-12 rounded-xl bg-white dark:bg-[#121914] border border-[#E5EBE6] dark:border-[#202C23] flex items-center justify-center text-emerald-600 dark:text-emerald-400 shadow-sm">
                    <Upload className="w-5 h-5" />
                  </div>
                  <div>
                    <p className="text-xs font-bold text-slate-900 dark:text-slate-100">
                      Kéo thả ảnh mẫu lá vào đây
                    </p>
                    <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">
                      hoặc nhấp chuột để chọn tệp từ máy
                    </p>
                  </div>
                  <button
                    type="button"
                    className="mt-1 px-3 py-1.5 rounded-lg bg-white dark:bg-[#121914] border border-[#E5EBE6] dark:border-[#202C23] text-xs font-medium text-slate-700 dark:text-slate-300 shadow-sm hover:bg-slate-50 dark:hover:bg-[#1A241C]"
                  >
                    Duyệt tệp ảnh
                  </button>
                  <p className="text-[10px] text-slate-400 dark:text-slate-500 mt-2">
                    Định dạng: JPG, PNG, WEBP • Tối đa 15MB • Kích thước tối ưu 224×224 px
                  </p>
                </div>
              )}
            </div>

            {/* Error Message */}
            {error && (
              <div className="mt-3 p-3 bg-red-50 dark:bg-red-950/20 border border-red-200 dark:border-red-900/40 rounded-lg text-xs text-red-700 dark:text-red-300 flex items-start gap-2">
                <AlertTriangle className="w-4 h-4 text-red-500 shrink-0 mt-0.5" />
                <div>
                  <span className="font-bold">Lỗi chẩn đoán: </span>
                  <span>{error}</span>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* RIGHT COLUMN: Settings & Diagnostic Results (7 cols) */}
        <div className="lg:col-span-7 flex flex-col gap-4">
          {/* Controls Box (Crop, Farm, Notes, Analyze Button) */}
          <div className="bg-white dark:bg-[#121914] border border-[#E5EBE6] dark:border-[#202C23] rounded-xl p-4 shadow-sm">
            <h3 className="text-xs font-bold text-slate-900 dark:text-slate-100 pb-2 mb-3 border-b border-[#E5EBE6] dark:border-[#202C23] flex items-center justify-between">
              <span>Thiết lập chẩn đoán</span>
              {selectedModelInfo && (
                <span className="text-[10px] text-emerald-600 dark:text-emerald-400 font-normal">
                  {selectedModelInfo.arch} • {selectedModelInfo.classes_count} lớp bệnh
                </span>
              )}
            </h3>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-3">
              {/* Crop Selector */}
              <div>
                <label className="block text-[11px] font-semibold text-slate-700 dark:text-slate-300 mb-1">
                  Loại cây trồng (Crop)
                </label>
                <select
                  value={selectedCrop}
                  onChange={(e) => setSelectedCrop(e.target.value)}
                  className="w-full bg-[#F7F9F7] dark:bg-[#162019] border border-[#E5EBE6] dark:border-[#202C23] rounded-lg px-2.5 py-1.5 text-xs text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-1 focus:ring-emerald-500 cursor-pointer"
                >
                  <option value="auto">✨ Tự động nhận diện cây trồng</option>
                  {models.map((m) => (
                    <option key={m.crop_id} value={m.crop_id}>
                      {m.crop_name} ({m.classes_count} bệnh)
                    </option>
                  ))}
                </select>
              </div>

              {/* Farm Selector */}
              <div>
                <label className="block text-[11px] font-semibold text-slate-700 dark:text-slate-300 mb-1">
                  Liên kết nông trại
                </label>
                <select
                  value={selectedFarmId}
                  onChange={(e) => setSelectedFarmId(e.target.value)}
                  className="w-full bg-[#F7F9F7] dark:bg-[#162019] border border-[#E5EBE6] dark:border-[#202C23] rounded-lg px-2.5 py-1.5 text-xs text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-1 focus:ring-emerald-500 cursor-pointer"
                >
                  <option value="">Không liên kết (Khám tự do)</option>
                  {farms.map((f) => (
                    <option key={f.id} value={f.id}>
                      {f.name} ({f.province})
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Field Notes Input */}
            <div className="mb-4">
              <label className="block text-[11px] font-semibold text-slate-700 dark:text-slate-300 mb-1">
                Ghi chú thực địa (Tùy chọn)
              </label>
              <input
                type="text"
                value={fieldNotes}
                onChange={(e) => setFieldNotes(e.target.value)}
                placeholder="Ví dụ: Xuất hiện ở tầng lá gốc, độ ẩm cao sau mưa..."
                className="w-full bg-[#F7F9F7] dark:bg-[#162019] border border-[#E5EBE6] dark:border-[#202C23] rounded-lg px-2.5 py-1.5 text-xs text-slate-900 dark:text-slate-100 placeholder:text-slate-400 focus:outline-none focus:ring-1 focus:ring-emerald-500"
              />
            </div>

            {/* Analyze Button */}
            <button
              type="button"
              onClick={handleRunDiagnosis}
              disabled={loading || !imageFile}
              className={`w-full py-2.5 px-4 rounded-lg font-semibold text-xs flex items-center justify-center gap-2 transition shadow-sm ${
                loading || !imageFile
                  ? 'bg-slate-100 dark:bg-slate-800 text-slate-400 cursor-not-allowed border border-slate-200 dark:border-slate-700'
                  : 'bg-[#166534] hover:bg-[#14532D] text-white shadow-emerald-500/20'
              }`}
            >
              {loading ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin text-emerald-400" />
                  <span>Đang chạy suy luận ConvNeXt cục bộ...</span>
                </>
              ) : (
                <>
                  <Zap className="w-4 h-4" />
                  <span>Chẩn Đoán AI Ngay</span>
                </>
              )}
            </button>
          </div>

          {/* Results Area */}
          <div className="bg-white dark:bg-[#121914] border border-[#E5EBE6] dark:border-[#202C23] rounded-xl p-4 shadow-sm min-h-[300px] flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between pb-3 mb-3 border-b border-[#E5EBE6] dark:border-[#202C23]">
                <h3 className="text-xs font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                  <ShieldCheck className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
                  <span>Kết quả phân tích mô hình</span>
                </h3>
                {prediction && (
                  <span className="text-[11px] text-slate-500 dark:text-slate-400">
                    Suy luận: <b className="text-emerald-700 dark:text-emerald-400">{prediction.inference_time_ms} ms</b>
                  </span>
                )}
              </div>

              {/* Empty / Upload State */}
              {!prediction && !loading && (
                <div className="py-12 flex flex-col items-center justify-center text-center text-slate-400">
                  <div className="w-12 h-12 rounded-xl bg-slate-50 dark:bg-[#162019] border border-[#E5EBE6] dark:border-[#202C23] flex items-center justify-center mb-3 text-slate-400">
                    <Zap className="w-5 h-5 text-slate-400" />
                  </div>
                  <p className="text-xs font-bold text-slate-700 dark:text-slate-300">Chưa có kết quả chẩn đoán</p>
                  <p className="text-[11px] text-slate-400 max-w-xs mt-1">
                    Tải ảnh lá ở cột bên trái và bấm "Chẩn Đoán AI Ngay" để nhận phân tích tức thì.
                  </p>
                </div>
              )}

              {/* Loading State */}
              {loading && (
                <div className="py-12 flex flex-col items-center justify-center text-center text-slate-400">
                  <RefreshCw className="w-8 h-8 text-emerald-600 dark:text-emerald-400 animate-spin mb-3" />
                  <p className="text-xs font-bold text-slate-700 dark:text-slate-300">Đang phân tích mẫu lá...</p>
                  <p className="text-[11px] text-slate-400 mt-1">Tính toán qua mạng nơ-ron tích chập trên CPU/GPU</p>
                </div>
              )}

              {/* Success Result State */}
              {prediction && (
                <div className="flex flex-col gap-4 animate-fadeIn">
                  {/* Low Confidence Warning (< 75%) */}
                  {isConfidenceUncertain && (
                    <div className="p-3 rounded-lg bg-amber-50 dark:bg-amber-950/20 border border-amber-300 dark:border-amber-800/40 text-amber-800 dark:text-amber-300 flex items-start gap-2.5">
                      <AlertTriangle className="w-4 h-4 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
                      <div className="text-xs leading-relaxed">
                        <span className="font-bold block text-amber-900 dark:text-amber-200">
                          Độ tin cậy ở mức trung bình ({(prediction.confidence * 100).toFixed(1)}% &lt; 75%)
                        </span>
                        <span className="text-[11px]">
                          Triệu chứng có thể chưa rõ hoặc ảnh thiếu nét. Khuyến nghị kiểm tra thêm tại ruộng hoặc gửi ca thẩm định chuyên gia trước khi can thiệp hóa học.
                        </span>
                      </div>
                    </div>
                  )}

                  {/* Top Prediction Highlight */}
                  <div className="p-4 rounded-xl bg-[#F7F9F7] dark:bg-[#162019] border border-[#E5EBE6] dark:border-[#202C23]">
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                        Chẩn đoán kết luận
                      </span>
                      <span
                        className={`text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wider ${
                          prediction.severity === 'HEALTHY'
                            ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400'
                            : prediction.severity === 'HIGH'
                            ? 'bg-red-500/10 text-red-700 dark:text-red-400'
                            : 'bg-amber-500/10 text-amber-700 dark:text-amber-400'
                        }`}
                      >
                        Mức độ: {prediction.severity}
                      </span>
                    </div>

                    <div className="flex items-baseline justify-between">
                      <div>
                        <h4 className="text-xl font-bold text-slate-900 dark:text-slate-100">
                          {prediction.disease_name_vi || prediction.predicted_disease}
                        </h4>
                        <div className="text-xs text-slate-500 dark:text-slate-400 font-mono mt-0.5">
                          {prediction.prediction} • Cây: <b className="text-slate-700 dark:text-slate-300">{prediction.crop_name || prediction.crop}</b>
                        </div>
                      </div>
                      <span className="text-2xl font-black text-emerald-700 dark:text-emerald-400">
                        {(prediction.confidence * 100).toFixed(1)}%
                      </span>
                    </div>

                    {/* Progress Bar */}
                    <div className="w-full h-2 bg-slate-200 dark:bg-slate-800 rounded-full overflow-hidden mt-3">
                      <div
                        className={`h-full rounded-full transition-all duration-500 ${
                          isConfidenceUncertain ? 'bg-amber-500' : 'bg-[#166534] dark:bg-emerald-500'
                        }`}
                        style={{ width: `${Math.min(100, Math.max(5, prediction.confidence * 100))}%` }}
                      />
                    </div>
                  </div>

                  {/* Top-3 Softmax Predictions */}
                  <div>
                    <div className="text-[10px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-2">
                      Top 3 Khả năng xác suất (Softmax Distribution)
                    </div>
                    <div className="space-y-1.5">
                      {prediction.top_predictions.slice(0, 3).map((item, idx) => {
                        const pct = item.confidence_percent || (item.confidence * 100);
                        return (
                          <div
                            key={idx}
                            className="p-2.5 rounded-lg bg-[#F7F9F7] dark:bg-[#162019] border border-[#E5EBE6] dark:border-[#202C23] flex items-center justify-between text-xs"
                          >
                            <div className="flex items-center gap-2">
                              <span className="w-4 h-4 rounded-full bg-slate-200 dark:bg-slate-800 flex items-center justify-center text-[10px] font-bold text-slate-600 dark:text-slate-400">
                                #{idx + 1}
                              </span>
                              <span className="font-medium text-slate-800 dark:text-slate-200">{item.label || item.disease}</span>
                              <span className="text-[10px] text-slate-400 font-mono hidden sm:inline">({item.class_id})</span>
                            </div>
                            <span className="font-mono font-semibold text-emerald-700 dark:text-emerald-400">{pct.toFixed(2)}%</span>
                          </div>
                        );
                      })}
                    </div>
                  </div>

                  {/* Agricultural IPM Knowledge & Verification */}
                  {prediction.disease_knowledge && (
                    <div className="p-3.5 bg-[#F7F9F7] dark:bg-[#162019] border border-[#E5EBE6] dark:border-[#202C23] rounded-xl flex flex-col gap-2.5 text-xs">
                      <div className="flex items-center justify-between border-b border-[#E5EBE6] dark:border-[#202C23] pb-2">
                        <span className="font-bold text-slate-900 dark:text-slate-100 flex items-center gap-1.5">
                          <BookOpen className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
                          <span>Khuyến cáo IPM & Kiểm tra thực địa</span>
                        </span>
                        <span className="text-[10px] text-emerald-600 dark:text-emerald-400 italic font-serif">
                          {prediction.disease_knowledge.scientific_name}
                        </span>
                      </div>

                      {prediction.disease_knowledge.symptoms && (
                        <div>
                          <span className="font-semibold text-slate-800 dark:text-slate-200 block mb-0.5">Triệu chứng:</span>
                          <p className="text-slate-600 dark:text-slate-400 leading-relaxed">{prediction.disease_knowledge.symptoms}</p>
                        </div>
                      )}

                      {prediction.disease_knowledge.field_verification && prediction.disease_knowledge.field_verification.length > 0 && (
                        <div>
                          <span className="font-semibold text-slate-800 dark:text-slate-200 block mb-0.5">Các bước kiểm tra tại ruộng:</span>
                          <ul className="list-disc pl-4 text-slate-600 dark:text-slate-400 space-y-0.5">
                            {prediction.disease_knowledge.field_verification.map((v, i) => (
                              <li key={i}>{v}</li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {prediction.disease_knowledge.prevention && prediction.disease_knowledge.prevention.length > 0 && (
                        <div>
                          <span className="font-semibold text-slate-800 dark:text-slate-200 block mb-0.5">Biện pháp phòng trừ:</span>
                          <ul className="list-disc pl-4 text-slate-600 dark:text-slate-400 space-y-0.5">
                            {prediction.disease_knowledge.prevention.map((p, i) => (
                              <li key={i}>{p}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Model Metadata specs */}
                  <div className="p-2.5 bg-[#F7F9F7] dark:bg-[#162019] border border-[#E5EBE6] dark:border-[#202C23] rounded-lg grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px] text-slate-500 dark:text-slate-400">
                    <div>
                      <span className="block text-[10px] text-slate-400">Mô hình:</span>
                      <span className="font-medium text-slate-800 dark:text-slate-200 truncate block">{prediction.model?.name}</span>
                    </div>
                    <div>
                      <span className="block text-[10px] text-slate-400">Kiến trúc:</span>
                      <span className="font-mono text-slate-800 dark:text-slate-200 truncate block">{prediction.model?.arch}</span>
                    </div>
                    <div>
                      <span className="block text-[10px] text-slate-400">Thiết bị:</span>
                      <span className="font-bold text-emerald-700 dark:text-emerald-400 uppercase">{prediction.model?.device}</span>
                    </div>
                    <div>
                      <span className="block text-[10px] text-slate-400">Thời gian:</span>
                      <span className="font-medium text-slate-800 dark:text-slate-200">{prediction.timestamp?.split('T')[1]?.slice(0, 5) || 'Vừa xong'}</span>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Bottom Actions after diagnosis */}
            {prediction && (
              <div className="mt-4 pt-3 border-t border-[#E5EBE6] dark:border-[#202C23] flex items-center justify-between flex-wrap gap-2 text-xs">
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={handleDownloadReport}
                    className="flex items-center gap-1.5 px-3 py-1.5 bg-white dark:bg-[#121914] hover:bg-slate-50 dark:hover:bg-[#1A241C] border border-[#E5EBE6] dark:border-[#202C23] rounded-lg font-semibold text-slate-700 dark:text-slate-300 transition"
                  >
                    <FileText className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
                    <span>Xuất JSON</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => onOpenExpertCase(prediction)}
                    className="flex items-center gap-1.5 px-3 py-1.5 bg-amber-50 dark:bg-amber-950/20 hover:bg-amber-100 border border-amber-300 dark:border-amber-800/40 rounded-lg font-semibold text-amber-700 dark:text-amber-400 transition"
                  >
                    <Stethoscope className="w-3.5 h-3.5" />
                    <span>Gửi chuyên gia</span>
                  </button>
                </div>

                <button
                  type="button"
                  onClick={handleReset}
                  className="px-3 py-1.5 bg-white dark:bg-[#121914] hover:bg-slate-50 dark:hover:bg-[#1A241C] border border-[#E5EBE6] dark:border-[#202C23] rounded-lg font-medium text-slate-600 dark:text-slate-400 transition"
                >
                  Quét mẫu mới
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
