"use client";

import { useMemo, useState } from "react";
import { ComposableMap, Geographies, Geography } from "react-simple-maps";
import type {
  CountryBottleneckProfile,
  CountryGridItem,
  IndicatorDistribution,
} from "@/types/api";
import { COUNTRY_NAME_TO_GEO_ID, GEO_ID_TO_COUNTRY_NAME } from "@/lib/countryGeo";
import { normalize, sequentialBlue, SEQUENTIAL_BLUE_DARK, SEQUENTIAL_BLUE_LIGHT } from "@/lib/colorScale";

const GEO_URL = "/countries-50m.json";

export type MapIndicator =
  | "culture_experience_rate_pct"
  | "visit_intention_positive_pct"
  | "observed_gap_pct_point"
  | "bottleneck_type_count";

const INDICATOR_OPTIONS: { value: MapIndicator; label: string }[] = [
  { value: "culture_experience_rate_pct", label: "문화경험률" },
  { value: "visit_intention_positive_pct", label: "방한의향 있음률" },
  { value: "observed_gap_pct_point", label: "Direct Gap" },
  { value: "bottleneck_type_count", label: "병목 유형 수 (A~G)" },
];

const TYPE_FLAG_KEYS: (keyof CountryBottleneckProfile)[] = [
  "direct_gap_type_flag",
  "conditional_gap_type_flag",
  "cognition_interest_barrier_flag",
  "image_barrier_flag",
  "economic_physical_access_barrier_flag",
  "institutional_language_barrier_flag",
  "religious_cultural_env_barrier_flag",
];

function countTypeFlags(profile: CountryBottleneckProfile): number {
  return TYPE_FLAG_KEYS.reduce((n, key) => n + (profile[key] === "Y" ? 1 : 0), 0);
}

interface CountryValue {
  value: number;
  displayValue: string;
}

export default function WorldMap({
  countryGrid,
  bottleneckProfiles,
  indicatorDistribution,
  selectedCountry,
  onSelectCountry,
}: {
  countryGrid: CountryGridItem[];
  bottleneckProfiles: CountryBottleneckProfile[];
  indicatorDistribution: IndicatorDistribution[];
  selectedCountry: string | null;
  onSelectCountry: (country: string) => void;
}) {
  const [indicator, setIndicator] = useState<MapIndicator>("culture_experience_rate_pct");
  const [hovered, setHovered] = useState<{ country: string; x: number; y: number } | null>(null);

  const { valuesByCountry, domainMin, domainMax } = useMemo(() => {
    const map = new Map<string, CountryValue>();
    let min = Infinity;
    let max = -Infinity;

    if (indicator === "bottleneck_type_count") {
      bottleneckProfiles.forEach((p) => {
        const count = countTypeFlags(p);
        map.set(p.country, { value: count, displayValue: `${count}개 유형` });
      });
      min = 0;
      max = 7;
    } else if (indicator === "observed_gap_pct_point") {
      countryGrid.forEach((item) => {
        if (item.observed_gap_pct_point === null) return;
        map.set(item.country, {
          value: item.observed_gap_pct_point,
          displayValue: `${item.observed_gap_pct_point.toFixed(1)}%p`,
        });
        min = Math.min(min, item.observed_gap_pct_point);
        max = Math.max(max, item.observed_gap_pct_point);
      });
    } else {
      const dist = indicatorDistribution.find((d) => d.indicator === indicator);
      min = dist?.min ?? 0;
      max = dist?.max ?? 100;
      countryGrid.forEach((item) => {
        const raw = item[indicator];
        if (raw === null || raw === undefined) return;
        map.set(item.country, { value: raw, displayValue: `${raw.toFixed(1)}%` });
      });
    }

    return { valuesByCountry: map, domainMin: min, domainMax: max };
  }, [indicator, countryGrid, bottleneckProfiles, indicatorDistribution]);

  const activeLabel = INDICATOR_OPTIONS.find((o) => o.value === indicator)?.label ?? "";

  return (
    <section
      className="card"
      style={{
        padding: "20px 20px 16px",
        display: "flex",
        flexDirection: "column",
        height: "100%",
        minHeight: 0,
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12, flexWrap: "wrap" }}>
        <div>
          <h2 style={{ fontSize: 16, margin: "0 0 4px" }}>23개국 지도 탐색</h2>
          <p style={{ fontSize: 12, color: "var(--text-secondary)", margin: 0 }}>
            국가를 클릭하면 오른쪽 패널에 상세 정보가 표시됩니다. 색은 상대적 크기를 나타낼 뿐, 좋고 나쁨을 뜻하지
            않습니다.
          </p>
        </div>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          {INDICATOR_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => setIndicator(opt.value)}
              style={{
                fontSize: 11,
                padding: "6px 10px",
                borderRadius: 999,
                border: `1px solid ${indicator === opt.value ? "var(--accent-primary)" : "var(--gridline)"}`,
                background: indicator === opt.value ? "var(--accent-primary-soft)" : "var(--card-bg)",
                color: indicator === opt.value ? "var(--accent-primary)" : "var(--text-secondary)",
                cursor: "pointer",
                fontWeight: indicator === opt.value ? 700 : 500,
                whiteSpace: "nowrap",
              }}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      <div
        style={{
          position: "relative",
          flex: 1,
          minHeight: 0,
          marginTop: 8,
          borderRadius: 12,
          background: "var(--card-bg-soft)",
          overflow: "hidden",
        }}
        onMouseMove={(e) => {
          if (!hovered) return;
          const rect = e.currentTarget.getBoundingClientRect();
          setHovered((h) => (h ? { ...h, x: e.clientX - rect.left, y: e.clientY - rect.top } : h));
        }}
      >
        <ComposableMap
          projection="geoEqualEarth"
          projectionConfig={{ scale: 165 }}
          style={{ width: "100%", height: "100%" }}
        >
          <Geographies geography={GEO_URL}>
            {({ geographies }) =>
              geographies.map((geo) => {
                const country = GEO_ID_TO_COUNTRY_NAME[geo.id as string];
                const entry = country ? valuesByCountry.get(country) : undefined;
                const inDataset = Boolean(country);
                const fill = entry
                  ? sequentialBlue(normalize(entry.value, domainMin, domainMax))
                  : inDataset
                    ? "var(--card-bg)"
                    : "#e7e5f2";
                const isSelected = country && country === selectedCountry;

                return (
                  <Geography
                    key={geo.rsmKey}
                    geography={geo}
                    onMouseEnter={(e) => {
                      if (!country) return;
                      const rect = e.currentTarget.ownerSVGElement?.parentElement?.getBoundingClientRect();
                      setHovered({
                        country,
                        x: rect ? e.clientX - rect.left : 0,
                        y: rect ? e.clientY - rect.top : 0,
                      });
                    }}
                    onMouseLeave={() => setHovered(null)}
                    onClick={() => country && onSelectCountry(country)}
                    style={{
                      default: {
                        fill,
                        stroke: isSelected ? "var(--accent-primary)" : "#ffffff",
                        strokeWidth: isSelected ? 1.6 : 0.5,
                        outline: "none",
                        cursor: country ? "pointer" : "default",
                      },
                      hover: {
                        fill: country ? "var(--accent-orange)" : fill,
                        stroke: "#ffffff",
                        strokeWidth: 0.5,
                        outline: "none",
                        cursor: country ? "pointer" : "default",
                      },
                      pressed: {
                        fill: "var(--accent-orange)",
                        stroke: "#ffffff",
                        strokeWidth: 0.5,
                        outline: "none",
                      },
                    }}
                  />
                );
              })
            }
          </Geographies>
        </ComposableMap>

        {hovered && valuesByCountry.get(hovered.country) && (
          <div
            style={{
              position: "absolute",
              left: hovered.x + 12,
              top: hovered.y + 12,
              pointerEvents: "none",
              background: "var(--card-bg)",
              border: "1px solid var(--border-hairline)",
              boxShadow: "0 4px 16px rgba(29,22,74,0.14)",
              borderRadius: 10,
              padding: "8px 12px",
              fontSize: 12,
              zIndex: 10,
              maxWidth: 200,
            }}
          >
            <div style={{ fontWeight: 700, marginBottom: 2 }}>{hovered.country}</div>
            <div style={{ color: "var(--text-secondary)" }}>
              {activeLabel}: <span className="tabular-nums">{valuesByCountry.get(hovered.country)!.displayValue}</span>
            </div>
          </div>
        )}
      </div>

      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: 10, fontSize: 11, color: "var(--text-muted)", flexWrap: "wrap", gap: 8 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span>{activeLabel}</span>
          <span className="tabular-nums">{domainMin.toFixed(indicator === "bottleneck_type_count" ? 0 : 1)}</span>
          <div
            style={{
              width: 120,
              height: 10,
              borderRadius: 6,
              background: `linear-gradient(to right, ${SEQUENTIAL_BLUE_LIGHT}, ${SEQUENTIAL_BLUE_DARK})`,
              border: "1px solid var(--gridline)",
            }}
          />
          <span className="tabular-nums">{domainMax.toFixed(indicator === "bottleneck_type_count" ? 0 : 1)}</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ width: 10, height: 10, borderRadius: 3, background: "#e7e5f2", display: "inline-block", border: "1px solid var(--gridline)" }} />
          <span>분석 대상 23개국 외 (데이터 없음)</span>
        </div>
      </div>
    </section>
  );
}
