import React, { useState, useEffect } from 'react';
import {
  Search,
  ChevronDown,
  ChevronUp
} from 'lucide-react';
import type { DiseaseKnowledge } from '../types';

interface KnowledgeViewProps {
  onSelectCropForDiagnosis: (crop: string) => void;
}

export const KnowledgeView: React.FC<KnowledgeViewProps> = ({
  onSelectCropForDiagnosis,
}) => {
  const [diseases, setDiseases] = useState<DiseaseKnowledge[]>([]);
  const [selectedCrop, setSelectedCrop] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(true);
  const [expandedCard, setExpandedCard] = useState<string | null>(null);

  const cropsList = [
    { id: 'all', name: 'Tất cả cây trồng' },
    { id: 'Tomato', name: 'Cà chua (13 bệnh)' },
    { id: 'Potato', name: 'Khoai tây (3 bệnh)' },
    { id: 'Rice', name: 'Lúa nước (4 bệnh)' },
    { id: 'Tea', name: 'Chè (6 bệnh)' },
    { id: 'Maize', name: 'Ngô (4 bệnh)' },
    { id: 'Coffee', name: 'Cà phê (4 bệnh)' },
    { id: 'Apple', name: 'Táo (4 bệnh)' },
    { id: 'Grape', name: 'Nho (5 bệnh)' },
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
      console.warn('Could not fetch knowledge diseases:', e);
    } finally {
      setLoading(false);
    }
  };

  const toggleExpand = (key: string) => {
    setExpandedCard(expandedCard === key ? null : key);
  };

  return (
    <div className="flex flex-col gap-6">
      {/* Top Banner */}
      <div className="p-5 rounded-2xl bg-gradient-to-r from-emerald-950/60 to-slate-900 border border-slate-800 flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-bold text-emerald-400 uppercase tracking-wider bg-emerald-500/10 px-2.5 py-0.5 rounded-full border border-emerald-500/20">
              Module 4 • Gari Knowledge
            </span>
            <span className="text-xs text-slate-400">Từ điển dịch tễ thực vật chuẩn hóa</span>
          </div>
          <h2 className="text-xl font-black text-white tracking-tight">
            Thư Viện Tri Thức Bệnh Cây & Quy Trình IPM
          </h2>
          <p className="text-xs text-slate-300 mt-0.5">
            Dữ liệu đối sánh từ Viện Bảo Vệ Thực Vật (NIPP), FAO và CGIAR cho 42 loại cây trồng.
          </p>
        </div>
      </div>

      {/* Search & Filter Toolbar */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 shadow-xl flex flex-col md:flex-row gap-3 items-center justify-between">
        <div className="relative w-full md:w-80">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Tìm theo tên bệnh, tên khoa học, triệu chứng..."
            className="w-full bg-slate-950 border border-slate-700 rounded-xl pl-9 pr-3.5 py-2 text-xs text-slate-100 focus:outline-none focus:ring-2 focus:ring-emerald-500"
          />
        </div>

        {/* Crop Pills */}
        <div className="flex items-center gap-1.5 overflow-x-auto w-full md:w-auto pb-1 md:pb-0 scrollbar-none">
          {cropsList.map((c) => (
            <button
              key={c.id}
              type="button"
              onClick={() => setSelectedCrop(c.id)}
              className={`px-3 py-1.5 rounded-xl text-xs font-semibold whitespace-nowrap transition ${
                selectedCrop === c.id
                  ? 'bg-emerald-500 text-slate-950 font-bold shadow-md shadow-emerald-500/20'
                  : 'bg-slate-800/80 text-slate-300 hover:bg-slate-700/80 border border-slate-700/60'
              }`}
            >
              {c.name}
            </button>
          ))}
        </div>
      </div>

      {/* Disease Cards Grid */}
      {loading ? (
        <div className="py-16 text-center text-xs text-slate-500">
          Đang nạp dữ liệu tri thức...
        </div>
      ) : diseases.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {diseases.map((d, index) => {
            const cardKey = `${d.crop_id}_${d.class_id}_${index}`;
            const isExpanded = expandedCard === cardKey;

            return (
              <div
                key={cardKey}
                className="bg-slate-900 border border-slate-800 hover:border-slate-700/80 rounded-2xl p-5 shadow-xl transition flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
                          {d.crop_name}
                        </span>
                        <span className="text-[10px] text-slate-500 font-mono">Phiên bản: {d.version}</span>
                      </div>
                      <h3 className="text-base font-extrabold text-white mt-1">
                        {d.disease_vi || d.disease_name}
                      </h3>
                      <p className="text-xs text-teal-300 italic font-serif">
                        {d.scientific_name}
                      </p>
                    </div>

                    <button
                      type="button"
                      onClick={() => onSelectCropForDiagnosis(d.crop_id)}
                      className="px-2.5 py-1 text-[11px] font-bold bg-slate-800 hover:bg-emerald-500/10 border border-slate-700 hover:border-emerald-500/30 text-emerald-400 rounded-lg transition shrink-0"
                    >
                      Quét AI &rarr;
                    </button>
                  </div>

                  <p className="text-xs text-slate-300 mt-2 line-clamp-2 leading-relaxed">
                    {d.symptoms}
                  </p>

                  {/* Expandable IPM & Verification Details */}
                  {isExpanded && (
                    <div className="mt-4 pt-3 border-t border-slate-800 flex flex-col gap-3 text-xs animate-fadeIn">
                      <div>
                        <span className="font-bold text-slate-200 block mb-1">Thời tiết & Ổ sinh thái thuận lợi:</span>
                        <p className="text-slate-400 leading-relaxed">{d.favorable_conditions}</p>
                      </div>

                      <div>
                        <span className="font-bold text-slate-200 block mb-1">Hướng dẫn kiểm tra thực địa:</span>
                        <ul className="list-disc pl-4 text-slate-400 space-y-0.5">
                          {d.field_verification.map((v, i) => (
                            <li key={i}>{v}</li>
                          ))}
                        </ul>
                      </div>

                      <div>
                        <span className="font-bold text-slate-200 block mb-1">Biện pháp phòng ngừa canh tác:</span>
                        <ul className="list-disc pl-4 text-slate-400 space-y-0.5">
                          {d.prevention.map((p, i) => (
                            <li key={i}>{p}</li>
                          ))}
                        </ul>
                      </div>

                      {d.chemical_advisory && (
                        <div className="p-2.5 bg-slate-950/80 border border-slate-800 rounded-lg text-[11px] text-slate-400">
                          <span className="font-bold text-amber-400 block mb-0.5">Khuyến cáo thuốc BVTV:</span>
                          <p>{d.chemical_advisory}</p>
                        </div>
                      )}

                      <div className="text-[10px] text-slate-500">
                        Nguồn tài liệu: <b>{d.references}</b>
                      </div>
                    </div>
                  )}
                </div>

                <div className="pt-3 border-t border-slate-800/80 flex items-center justify-between mt-3 text-xs">
                  <span className="text-[11px] text-slate-500">
                    Mã nhãn: <b className="text-slate-400 font-mono">{d.class_id}</b>
                  </span>

                  <button
                    type="button"
                    onClick={() => toggleExpand(cardKey)}
                    className="text-xs text-teal-400 hover:text-teal-300 font-semibold flex items-center gap-1"
                  >
                    <span>{isExpanded ? 'Thu gọn' : 'Xem quy trình IPM'}</span>
                    {isExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="py-16 text-center text-xs text-slate-500 bg-slate-900 border border-slate-800 rounded-2xl">
          Không tìm thấy bệnh cây phù hợp với từ khóa "{searchQuery}".
        </div>
      )}
    </div>
  );
};
