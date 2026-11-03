import React, { useState, useEffect } from 'react';
import {
  AlertOctagon,
  CloudRain,
  Thermometer,
  Wind,
  Info
} from 'lucide-react';
import type { RiskAlert } from '../types';

export const RiskView: React.FC = () => {
  const [alerts, setAlerts] = useState<RiskAlert[]>([]);
  const [weather, setWeather] = useState<any>(null);

  useEffect(() => {
    fetchRiskData();
  }, []);

  const fetchRiskData = async () => {
    try {
      const res = await fetch('/api/risk/monitoring');
      if (res.ok) {
        const data = await res.json();
        setAlerts(data.alerts || []);
        setWeather(data.observed_weather || null);
      }
    } catch (e) {
      console.warn('Could not fetch risk monitoring data:', e);
    }
  };

  return (
    <div className="flex flex-col gap-5 animate-fadeIn">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-2 border-b border-[#E5EBE6] dark:border-[#202C23]">
        <div>
          <h1 className="text-xl font-bold text-slate-900 dark:text-slate-100 tracking-tight">
            Giám Sát Rủi Ro & Dự Báo Dịch Bệnh
          </h1>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Mô hình dự báo dịch tễ học kết hợp số liệu quan trắc khí hậu thực địa và chuỗi thời gian.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold px-2.5 py-1 rounded-lg bg-amber-500/10 text-amber-700 dark:text-amber-400 border border-amber-500/20">
            {alerts.length} Cảnh báo đang kích hoạt
          </span>
        </div>
      </div>

      {/* Methodology Transparency Notice */}
      <div className="p-3.5 rounded-xl bg-white dark:bg-[#121914] border border-[#E5EBE6] dark:border-[#202C23] text-xs shadow-sm flex flex-col md:flex-row gap-3 items-start md:items-center justify-between">
        <div className="flex items-center gap-2 text-emerald-700 dark:text-emerald-400 font-semibold shrink-0">
          <Info className="w-4 h-4" />
          <span>Minh Bạch Phương Pháp:</span>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 w-full text-[11px]">
          <div className="p-2 rounded-lg bg-[#F7F9F7] dark:bg-[#162019] border border-[#E5EBE6] dark:border-[#202C23]">
            <span className="text-emerald-700 dark:text-emerald-400 font-bold block mb-0.5">[QUAN TRẮC THỰC ĐỊA]</span>
            <span className="text-slate-500 dark:text-slate-400">Số đo cảm biến nhiệt ẩm thời gian thực.</span>
          </div>
          <div className="p-2 rounded-lg bg-[#F7F9F7] dark:bg-[#162019] border border-[#E5EBE6] dark:border-[#202C23]">
            <span className="text-amber-700 dark:text-amber-400 font-bold block mb-0.5">[MÔ HÌNH DỊCH TỄ]</span>
            <span className="text-slate-500 dark:text-slate-400">Cảnh báo ngưỡng sinh học nấm/khuẩn hại lá.</span>
          </div>
          <div className="p-2 rounded-lg bg-[#F7F9F7] dark:bg-[#162019] border border-[#E5EBE6] dark:border-[#202C23]">
            <span className="text-teal-700 dark:text-teal-400 font-bold block mb-0.5">[HỌC MÁY AI]</span>
            <span className="text-slate-500 dark:text-slate-400">Phân tích chuỗi dữ liệu rủi ro mùa vụ.</span>
          </div>
        </div>
      </div>

      {/* Environmental Metrics Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
        <div className="p-4 rounded-xl bg-white dark:bg-[#121914] border border-[#E5EBE6] dark:border-[#202C23] shadow-sm flex items-center justify-between">
          <div>
            <span className="text-[11px] font-medium text-slate-500 dark:text-slate-400 block mb-0.5">Nhiệt độ quan trắc</span>
            <div className="text-2xl font-bold text-slate-900 dark:text-slate-100">
              {weather?.temperature_c ?? 24.5}°C
            </div>
            <span className="text-[10px] text-emerald-700 dark:text-emerald-400 font-medium block mt-1">
              Khoảng an toàn sinh thái
            </span>
          </div>
          <div className="w-10 h-10 rounded-lg bg-amber-500/10 text-amber-600 dark:text-amber-400 flex items-center justify-center">
            <Thermometer className="w-5 h-5" />
          </div>
        </div>

        <div className="p-4 rounded-xl bg-white dark:bg-[#121914] border border-[#E5EBE6] dark:border-[#202C23] shadow-sm flex items-center justify-between">
          <div>
            <span className="text-[11px] font-medium text-slate-500 dark:text-slate-400 block mb-0.5">Độ ẩm tương đối</span>
            <div className="text-2xl font-bold text-slate-900 dark:text-slate-100">
              {weather?.humidity_pct ?? 82}%
            </div>
            <span className="text-[10px] text-amber-600 dark:text-amber-400 font-medium block mt-1">
              Đạt ngưỡng nấm mốc phát triển (&gt;80%)
            </span>
          </div>
          <div className="w-10 h-10 rounded-lg bg-teal-500/10 text-teal-600 dark:text-teal-400 flex items-center justify-center">
            <CloudRain className="w-5 h-5" />
          </div>
        </div>

        <div className="p-4 rounded-xl bg-white dark:bg-[#121914] border border-[#E5EBE6] dark:border-[#202C23] shadow-sm flex items-center justify-between">
          <div>
            <span className="text-[11px] font-medium text-slate-500 dark:text-slate-400 block mb-0.5">Lượng mưa 24h</span>
            <div className="text-2xl font-bold text-slate-900 dark:text-slate-100">
              {weather?.rainfall_mm ?? 4.5} mm
            </div>
            <span className="text-[10px] text-slate-500 dark:text-slate-400 font-medium block mt-1">
              Mưa rải rác cục bộ
            </span>
          </div>
          <div className="w-10 h-10 rounded-lg bg-blue-500/10 text-blue-600 dark:text-blue-400 flex items-center justify-center">
            <CloudRain className="w-5 h-5" />
          </div>
        </div>

        <div className="p-4 rounded-xl bg-white dark:bg-[#121914] border border-[#E5EBE6] dark:border-[#202C23] shadow-sm flex items-center justify-between">
          <div>
            <span className="text-[11px] font-medium text-slate-500 dark:text-slate-400 block mb-0.5">Tốc độ gió</span>
            <div className="text-2xl font-bold text-slate-900 dark:text-slate-100">
              {weather?.wind_speed_kmh ?? 12.0} km/h
            </div>
            <span className="text-[10px] text-slate-500 dark:text-slate-400 font-medium block mt-1">
              Thông gió tán lá tốt
            </span>
          </div>
          <div className="w-10 h-10 rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 flex items-center justify-center">
            <Wind className="w-5 h-5" />
          </div>
        </div>
      </div>

      {/* Disease Risk Alerts List */}
      <div className="bg-white dark:bg-[#121914] border border-[#E5EBE6] dark:border-[#202C23] rounded-xl p-4 shadow-sm">
        <div className="flex items-center justify-between border-b border-[#E5EBE6] dark:border-[#202C23] pb-3 mb-3">
          <h3 className="font-bold text-xs text-slate-900 dark:text-slate-100 flex items-center gap-2">
            <AlertOctagon className="w-4 h-4 text-amber-600 dark:text-amber-400" />
            <span>Danh mục cảnh báo dịch bệnh theo vùng canh tác</span>
          </h3>
          <span className="text-[11px] text-slate-500 dark:text-slate-400">
            Dữ liệu quan trắc tự động
          </span>
        </div>

        <div className="space-y-3">
          {alerts.map((alert) => (
            <div
              key={alert.id}
              className="p-3.5 bg-[#F7F9F7] dark:bg-[#162019] border border-[#E5EBE6] dark:border-[#202C23] rounded-lg flex flex-col sm:flex-row justify-between gap-3"
            >
              <div className="flex flex-col gap-1 max-w-2xl">
                <div className="flex items-center gap-2 flex-wrap">
                  <span
                    className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded-full ${
                      alert.risk_level === 'High' || alert.risk_level === 'Critical'
                        ? 'bg-red-500/10 text-red-700 dark:text-red-400'
                        : 'bg-amber-500/10 text-amber-700 dark:text-amber-400'
                    }`}
                  >
                    Mức độ: {alert.risk_level}
                  </span>
                  <span className="text-xs font-bold text-slate-900 dark:text-slate-100">
                    {alert.crop} • {alert.disease_threat}
                  </span>
                  <span className="text-[10px] text-slate-500 dark:text-slate-400 bg-white dark:bg-slate-800 px-2 py-0.5 rounded border border-[#E5EBE6] dark:border-[#202C23]">
                    Vùng: {alert.region}
                  </span>
                  <span className="text-[10px] text-emerald-700 dark:text-emerald-400 font-mono bg-emerald-500/10 px-2 py-0.5 rounded">
                    Nguồn: {alert.source_type}
                  </span>
                </div>

                <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed mt-1">
                  {alert.recommendation}
                </p>
              </div>

              {alert.temperature_c !== undefined && alert.humidity_pct !== undefined && (
                <div className="text-right shrink-0 bg-white dark:bg-[#121914] p-2.5 rounded-lg border border-[#E5EBE6] dark:border-[#202C23] self-start text-[11px] text-slate-500 dark:text-slate-400 flex flex-col gap-0.5">
                  <span>Nhiệt độ vùng: <b className="text-slate-800 dark:text-slate-200">{alert.temperature_c}°C</b></span>
                  <span>Độ ẩm vùng: <b className="text-teal-600 dark:text-teal-400">{alert.humidity_pct}%</b></span>
                  {alert.rainfall_mm !== undefined && (
                    <span>Lượng mưa: <b className="text-blue-600 dark:text-blue-400">{alert.rainfall_mm} mm</b></span>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
