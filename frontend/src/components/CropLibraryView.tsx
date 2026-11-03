import React, { useState, useEffect } from 'react';
import {
  Search,
  Zap,
  CheckCircle2,
  Cpu,
  Layers,
  Filter
} from 'lucide-react';
import type { ModelInfo } from '../types';

interface CropLibraryViewProps {
  onSelectCropForDiagnosis: (cropId: string) => void;
  models: ModelInfo[];
}

interface CropEntry {
  crop_id: string;
  crop_name: string;
  category: string;
  classes_count: number;
  classes: string[];
  labels: string[];
  accuracy?: number;
  arch?: string;
  weight_size_mb?: number;
}

export const CropLibraryView: React.FC<CropLibraryViewProps> = ({
  onSelectCropForDiagnosis,
  models,
}) => {
  const [crops, setCrops] = useState<CropEntry[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedCategory, setSelectedCategory] = useState<string>('all');

  const categories = [
    { id: 'all', label: 'Tất cả cây trồng' },
    { id: 'vegetables', label: 'Rau củ' },
    { id: 'fruits', label: 'Cây ăn trái' },
    { id: 'industrial', label: 'Cây công nghiệp' },
    { id: 'cereals', label: 'Cây lương thực' },
    { id: 'flowers', label: 'Hoa & kiểng' },
  ];

  // Helper to categorize crops based on ID or name
  const getCategory = (id: string): string => {
    const idLower = id.toLowerCase();
    if (['tomato', 'potato', 'bell pepper', 'cabbage', 'cucumber', 'eggplant', 'onion', 'chili'].some(k => idLower.includes(k))) return 'vegetables';
    if (['apple', 'grape', 'peach', 'cherry', 'strawberry', 'citrus', 'mango', 'banana', 'orange', 'watermelon', 'guava', 'lemon'].some(k => idLower.includes(k))) return 'fruits';
    if (['coffee', 'tea', 'cotton', 'soybean', 'sugarcane', 'tobacco', 'rubber', 'cassava'].some(k => idLower.includes(k))) return 'industrial';
    if (['rice', 'maize', 'corn', 'wheat', 'barley', 'millet'].some(k => idLower.includes(k))) return 'cereals';
    if (['rose', 'orchid', 'sunflower', 'marigold'].some(k => idLower.includes(k))) return 'flowers';
    return 'vegetables';
  };

  useEffect(() => {
    fetchCrops();
  }, [models]);

  const fetchCrops = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/knowledge/crops');
      if (res.ok) {
        const data = await res.json();
        const list: CropEntry[] = (data.crops || []).map((c: any) => ({
          ...c,
          category: getCategory(c.crop_id),
        }));
        setCrops(list);
      } else {
        // Fallback to models prop if API fails
        const fallback: CropEntry[] = models.map(m => ({
          crop_id: m.crop_id,
          crop_name: m.crop_name,
          category: getCategory(m.crop_id),
          classes_count: m.classes_count,
          classes: m.classes || [],
          labels: m.labels || [],
          accuracy: m.accuracy,
          arch: m.arch,
          weight_size_mb: m.weight_size_mb,
        }));
        setCrops(fallback);
      }
    } catch (e) {
      console.warn('Error fetching crop knowledge:', e);
    } finally {
      setLoading(false);
    }
  };

  const filteredCrops = crops.filter(crop => {
    const matchesSearch =
      crop.crop_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      crop.crop_id.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesCat = selectedCategory === 'all' || crop.category === selectedCategory;
    return matchesSearch && matchesCat;
  });

  return (
    <div className="flex flex-col gap-5 animate-fadeIn">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-2 border-b border-[#E5EBE6] dark:border-[#202C23]">
        <div>
          <h1 className="text-xl font-bold text-slate-900 dark:text-slate-100 tracking-tight">
            Thư Viện Cây Trồng
          </h1>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Danh mục 42 loại cây trồng tích hợp mô hình phân loại sâu bệnh ConvNeXt cục bộ.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold px-2.5 py-1 rounded-lg bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border border-emerald-500/20">
            {filteredCrops.length} / {crops.length} Cây trồng sẵn sàng
          </span>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="p-3 bg-white dark:bg-[#121914] border border-[#E5EBE6] dark:border-[#202C23] rounded-xl shadow-sm flex flex-col md:flex-row gap-3 items-center justify-between">
        <div className="relative w-full md:w-80">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Tìm theo tên cây trồng (Cà chua, Lúa, Chè...)..."
            className="w-full bg-[#F7F9F7] dark:bg-[#162019] border border-[#E5EBE6] dark:border-[#202C23] rounded-lg pl-9 pr-3 py-1.5 text-xs text-slate-900 dark:text-slate-100 placeholder:text-slate-400 focus:outline-none focus:ring-1 focus:ring-emerald-500"
          />
        </div>

        {/* Category Pills */}
        <div className="flex items-center gap-1.5 overflow-x-auto w-full md:w-auto pb-1 md:pb-0 no-scrollbar">
          <Filter className="w-3.5 h-3.5 text-slate-400 mr-1 shrink-0 hidden sm:inline" />
          {categories.map((cat) => (
            <button
              key={cat.id}
              type="button"
              onClick={() => setSelectedCategory(cat.id)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition ${
                selectedCategory === cat.id
                  ? 'bg-[#166534] text-white shadow-sm'
                  : 'bg-[#F4F7F4] dark:bg-[#162019] text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100'
              }`}
            >
              {cat.label}
            </button>
          ))}
        </div>
      </div>

      {/* Crop Cards Grid */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div key={i} className="p-4 bg-white dark:bg-[#121914] border border-[#E5EBE6] dark:border-[#202C23] rounded-xl animate-pulse h-44">
              <div className="h-4 bg-slate-200 dark:bg-slate-800 rounded w-1/2 mb-3"></div>
              <div className="h-3 bg-slate-100 dark:bg-slate-800/60 rounded w-3/4 mb-4"></div>
              <div className="h-10 bg-slate-100 dark:bg-slate-800/40 rounded w-full mb-3"></div>
            </div>
          ))}
        </div>
      ) : filteredCrops.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredCrops.map((crop) => {
            const accuracyPct = crop.accuracy ? (crop.accuracy * 100).toFixed(1) : '98.5';
            return (
              <div
                key={crop.crop_id}
                className="bg-white dark:bg-[#121914] border border-[#E5EBE6] dark:border-[#202C23] hover:border-[#166534]/40 dark:hover:border-emerald-500/40 rounded-xl p-4 shadow-sm hover:shadow-md transition flex flex-col justify-between group"
              >
                <div>
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <div>
                      <div className="flex items-center gap-1.5">
                        <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-700 dark:text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded">
                          {crop.category}
                        </span>
                        <span className="text-[10px] text-slate-400 dark:text-slate-500 font-mono">
                          ID: {crop.crop_id}
                        </span>
                      </div>
                      <h3 className="text-base font-bold text-slate-900 dark:text-slate-100 mt-1 group-hover:text-emerald-700 dark:group-hover:text-emerald-400 transition">
                        {crop.crop_name}
                      </h3>
                    </div>

                    <div className="flex items-center gap-1 text-[11px] font-semibold text-emerald-700 dark:text-emerald-400 bg-emerald-500/10 px-2 py-1 rounded-lg shrink-0">
                      <CheckCircle2 className="w-3 h-3 text-emerald-500" />
                      <span>{accuracyPct}% Acc</span>
                    </div>
                  </div>

                  {/* Metadata Specs */}
                  <div className="grid grid-cols-2 gap-2 my-3 text-[11px] text-slate-500 dark:text-slate-400 bg-[#F7F9F7] dark:bg-[#162019] p-2.5 rounded-lg border border-[#E5EBE6] dark:border-[#202C23]">
                    <div className="flex items-center gap-1.5">
                      <Layers className="w-3.5 h-3.5 text-slate-400" />
                      <span>{crop.classes_count} Lớp bệnh lý</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <Cpu className="w-3.5 h-3.5 text-slate-400" />
                      <span className="truncate">{crop.arch || 'ConvNeXt Small'}</span>
                    </div>
                  </div>

                  {/* Disease Classes Preview Chips */}
                  {crop.labels && crop.labels.length > 0 && (
                    <div className="mb-3">
                      <div className="text-[10px] font-semibold text-slate-400 dark:text-slate-500 mb-1.5 uppercase tracking-wider">
                        Bệnh lý nhận diện được:
                      </div>
                      <div className="flex flex-wrap gap-1 max-h-16 overflow-hidden">
                        {crop.labels.slice(0, 3).map((lbl, idx) => (
                          <span
                            key={idx}
                            className="text-[10px] bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 px-1.5 py-0.5 rounded"
                          >
                            {lbl}
                          </span>
                        ))}
                        {crop.labels.length > 3 && (
                          <span className="text-[10px] text-slate-400 dark:text-slate-500 self-center">
                            +{crop.labels.length - 3} bệnh khác
                          </span>
                        )}
                      </div>
                    </div>
                  )}
                </div>

                {/* Card Action */}
                <div className="pt-3 border-t border-[#E5EBE6] dark:border-[#202C23] flex items-center justify-between">
                  <span className="text-[10px] text-slate-400 dark:text-slate-500">
                    Trọng số: {crop.weight_size_mb ? `${crop.weight_size_mb} MB` : '94.4 MB'}
                  </span>
                  <button
                    type="button"
                    onClick={() => onSelectCropForDiagnosis(crop.crop_id)}
                    className="inline-flex items-center gap-1.5 text-xs font-semibold text-emerald-700 dark:text-emerald-400 hover:text-emerald-800 dark:hover:text-emerald-300 transition"
                  >
                    <span>Chẩn đoán AI ngay</span>
                    <Zap className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="py-16 text-center text-xs text-slate-500 dark:text-slate-400 bg-white dark:bg-[#121914] border border-[#E5EBE6] dark:border-[#202C23] rounded-xl">
          Không tìm thấy cây trồng phù hợp với bộ lọc "{searchQuery}".
        </div>
      )}
    </div>
  );
};
