import React, { useState, useEffect } from 'react';
import {
  Search,
  Filter,
  Zap,
  ChevronDown,
  ChevronUp,
  CheckCircle,
  AlertTriangle,
  BookOpen,
  Info
} from 'lucide-react';
import type { DiseaseKnowledge } from '../types';

interface DiseaseLibraryViewProps {
  onSelectCropForDiagnosis: (cropId: string) => void;
}

export const DiseaseLibraryView: React.FC<DiseaseLibraryViewProps> = ({
  onSelectCropForDiagnosis,
}) => {
  const [diseases, setDiseases] = useState<DiseaseKnowledge[]>([]);
  const [selectedCrop, setSelectedCrop] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(true);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const availableCrops = [
    { id: 'all', name: 'Tất cả cây trồng' },
    { id: 'Tomato', name: 'Cà chua (Tomato)' },
    { id: 'Potato', name: 'Khoai tây (Potato)' },
    { id: 'Rice', name: 'Lúa nước (Rice)' },
    { id: 'Tea', name: 'Chè (Tea)' },
    { id: 'Maize', name: 'Ngô (Maize)' },
    { id: 'Coffee', name: 'Cà phê (Coffee)' },
    { id: 'Apple', name: 'Táo (Apple)' },
    { id: 'Grape', name: 'Nho (Grape)' },
    { id: 'Bell Pepper', name: 'Ớt chuông (Bell Pepper)' },
    { id: 'Cassava', name: 'Sắn (Cassava)' },
    { id: 'Citrus', name: 'Cây có múi (Citrus)' },
  ];

  useEffect(() => {
    fetchDiseases();
  }, [selectedCrop, searchQuery]);

  const fetchDiseases = async () => {
    setLoading(true);
    try {
      let url = '/api/knowledge/diseases?';
      if (selectedCrop && selectedCrop !== 'all') {
        url += `crop=${encodeURIComponent(selectedCrop)}&`;
      }
      if (searchQuery.trim()) {
        url += `q=${encodeURIComponent(searchQuery.trim())}&`;
      }
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        setDiseases(data.diseases || []);
      }
    } catch (e) {
      console.warn('Error fetching disease library:', e);
    } finally {
      setLoading(false);
    }
  };

  const toggleExpand = (id: string) => {
    setExpandedId(expandedId === id ? null : id);
  };

  return (
    <div className="flex flex-col gap-5 animate-fadeIn">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-2 border-b border-[#E5EBE6] dark:border-[#202C23]">
        <div>
          <h1 className="text-xl font-bold text-slate-900 dark:text-slate-100 tracking-tight">
            Thư Viện Bệnh Lý & Quy Trình IPM
          </h1>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Từ điển dịch tễ thực vật chuẩn hóa, nhận diện triệu chứng, kiểm định thực địa và biện pháp quản lý dịch hại tổng hợp (IPM).
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold px-2.5 py-1 rounded-lg bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border border-emerald-500/20">
            {diseases.length} Bệnh lý được chuẩn hóa
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
            placeholder="Tìm theo tên bệnh, tên khoa học, triệu chứng..."
            className="w-full bg-[#F7F9F7] dark:bg-[#162019] border border-[#E5EBE6] dark:border-[#202C23] rounded-lg pl-9 pr-3 py-1.5 text-xs text-slate-900 dark:text-slate-100 placeholder:text-slate-400 focus:outline-none focus:ring-1 focus:ring-emerald-500"
          />
        </div>

        {/* Crop Pills */}
        <div className="flex items-center gap-1.5 overflow-x-auto w-full md:w-auto pb-1 md:pb-0 no-scrollbar">
          <Filter className="w-3.5 h-3.5 text-slate-400 mr-1 shrink-0 hidden sm:inline" />
          {availableCrops.map((c) => (
            <button
              key={c.id}
              type="button"
              onClick={() => setSelectedCrop(c.id)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition ${
                selectedCrop === c.id
                  ? 'bg-[#166534] text-white shadow-sm'
                  : 'bg-[#F4F7F4] dark:bg-[#162019] text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100'
              }`}
            >
              {c.name}
            </button>
          ))}
        </div>
      </div>

      {/* Disease Cards Grid */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="p-5 bg-white dark:bg-[#121914] border border-[#E5EBE6] dark:border-[#202C23] rounded-xl animate-pulse h-48">
              <div className="h-4 bg-slate-200 dark:bg-slate-800 rounded w-1/3 mb-2"></div>
              <div className="h-5 bg-slate-200 dark:bg-slate-800 rounded w-3/5 mb-3"></div>
              <div className="h-12 bg-slate-100 dark:bg-slate-800/60 rounded w-full mb-3"></div>
            </div>
          ))}
        </div>
      ) : diseases.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {diseases.map((d, index) => {
            const cardId = `${d.crop_id}_${d.class_id}_${index}`;
            const isExpanded = expandedId === cardId;

            return (
              <div
                key={cardId}
                className="bg-white dark:bg-[#121914] border border-[#E5EBE6] dark:border-[#202C23] hover:border-[#166534]/40 dark:hover:border-emerald-500/40 rounded-xl p-5 shadow-sm transition flex flex-col justify-between"
              >
                <div>
                  {/* Card Header */}
                  <div className="flex items-start justify-between gap-3 mb-2">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-700 dark:text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded">
                          {d.crop_name}
                        </span>
                        {d.is_verified && (
                          <span className="inline-flex items-center gap-1 text-[10px] text-teal-600 dark:text-teal-400">
                            <CheckCircle className="w-3 h-3" /> Chuẩn hóa NIPP
                          </span>
                        )}
                      </div>
                      <h3 className="text-base font-bold text-slate-900 dark:text-slate-100 mt-1">
                        {d.disease_vi || d.disease_name}
                      </h3>
                      {d.scientific_name && (
                        <p className="text-xs text-emerald-600 dark:text-emerald-400 italic font-serif mt-0.5">
                          {d.scientific_name}
                        </p>
                      )}
                    </div>

                    <button
                      type="button"
                      onClick={() => onSelectCropForDiagnosis(d.crop_id)}
                      className="px-2.5 py-1 text-xs font-semibold text-emerald-700 dark:text-emerald-400 hover:text-emerald-800 dark:hover:text-emerald-300 bg-emerald-500/10 hover:bg-emerald-500/20 rounded-lg transition shrink-0 flex items-center gap-1"
                    >
                      <Zap className="w-3 h-3" />
                      <span>Quét AI</span>
                    </button>
                  </div>

                  {/* Symptom Summary */}
                  <p className="text-xs text-slate-600 dark:text-slate-300 mt-2 line-clamp-3 leading-relaxed">
                    {d.symptoms}
                  </p>

                  {/* Expanded IPM Details */}
                  {isExpanded && (
                    <div className="mt-4 pt-4 border-t border-[#E5EBE6] dark:border-[#202C23] flex flex-col gap-3 text-xs animate-fadeIn">
                      {d.favorable_conditions && (
                        <div className="bg-[#F7F9F7] dark:bg-[#162019] p-3 rounded-lg border border-[#E5EBE6] dark:border-[#202C23]">
                          <span className="font-semibold text-slate-900 dark:text-slate-100 block mb-1">
                            Điều kiện phát sinh & Thời tiết thuận lợi:
                          </span>
                          <p className="text-slate-600 dark:text-slate-400 leading-relaxed">
                            {d.favorable_conditions}
                          </p>
                        </div>
                      )}

                      {d.field_verification && d.field_verification.length > 0 && (
                        <div>
                          <span className="font-semibold text-slate-900 dark:text-slate-100 block mb-1">
                            Hướng dẫn kiểm định tại thực địa:
                          </span>
                          <ul className="list-disc pl-4 text-slate-600 dark:text-slate-400 space-y-1">
                            {d.field_verification.map((v, i) => (
                              <li key={i}>{v}</li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {d.prevention && d.prevention.length > 0 && (
                        <div>
                          <span className="font-semibold text-slate-900 dark:text-slate-100 block mb-1">
                            Quy trình phòng trừ canh tác (IPM):
                          </span>
                          <ul className="list-disc pl-4 text-slate-600 dark:text-slate-400 space-y-1">
                            {d.prevention.map((p, i) => (
                              <li key={i}>{p}</li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {d.chemical_advisory && (
                        <div className="p-3 bg-amber-50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-800/40 rounded-lg text-slate-700 dark:text-slate-300">
                          <span className="font-semibold text-amber-700 dark:text-amber-400 block mb-1 flex items-center gap-1.5">
                            <AlertTriangle className="w-3.5 h-3.5 text-amber-500" />
                            Khuyến cáo hoạt chất BVTV có kiểm soát:
                          </span>
                          <p className="text-[11px] leading-relaxed">{d.chemical_advisory}</p>
                        </div>
                      )}

                      {d.references && (
                        <div className="text-[11px] text-slate-400 dark:text-slate-500 flex items-center gap-1">
                          <BookOpen className="w-3 h-3 text-slate-400" />
                          <span>Tài liệu tham khảo: <b>{d.references}</b></span>
                        </div>
                      )}
                    </div>
                  )}
                </div>

                {/* Footer Controls */}
                <div className="pt-3 border-t border-[#E5EBE6] dark:border-[#202C23] flex items-center justify-between mt-4 text-xs">
                  <div className="flex items-center gap-1 text-[11px] text-slate-400 dark:text-slate-500 font-mono">
                    <Info className="w-3 h-3" />
                    <span>Lớp: {d.class_id}</span>
                  </div>

                  <button
                    type="button"
                    onClick={() => toggleExpand(cardId)}
                    className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-700 dark:text-emerald-400 hover:text-emerald-800 dark:hover:text-emerald-300"
                  >
                    <span>{isExpanded ? 'Thu gọn' : 'Xem phác đồ IPM đầy đủ'}</span>
                    {isExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="py-16 text-center text-xs text-slate-500 dark:text-slate-400 bg-white dark:bg-[#121914] border border-[#E5EBE6] dark:border-[#202C23] rounded-xl">
          Không tìm thấy bệnh cây phù hợp với từ khóa "{searchQuery}".
        </div>
      )}
    </div>
  );
};
