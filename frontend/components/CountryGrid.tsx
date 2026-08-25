"use client";

import { useMemo, useState } from "react";
import type { CountryBottleneckProfile, CountryGridItem } from "@/types/api";

const SORT_OPTIONS = [
  { value: "name", label: "국가명" },
  { value: "culture_experience_rate_pct", label: "문화경험률" },
  { value: "visit_intention_positive_pct", label: "방한의향 있음률" },
  { value: "observed_gap_pct_point", label: "Direct Gap" },
] as const;

type SortKey = (typeof SORT_OPTIONS)[number]["value"];

const FLAG_LABELS: { key: keyof CountryBottleneckProfile; label: string }[] = [
  { key: "direct_gap_type_flag", label: "A · Direct Gap" },
  { key: "conditional_gap_type_flag", label: "B · Conditional Gap" },
  { key: "cognition_interest_barrier_flag", label: "C · 인지/관심" },
  { key: "image_barrier_flag", label: "D · 이미지" },
  { key: "economic_physical_access_barrier_flag", label: "E · 경제/물리적 접근성" },
  { key: "institutional_language_barrier_flag", label: "F · 제도/언어" },
  { key: "religious_cultural_env_barrier_flag", label: "G · 종교/문화환경" },
];

function fmt(value: number | null, digits = 1): string {
  return value === null ? "—" : value.toFixed(digits);
}

function CountryCard({
  item,
  profile,
  expanded,
  onToggle,
}: {
  item: CountryGridItem;
  profile: CountryBottleneckProfile | undefined;
  expanded: boolean;
  onToggle: () => void;
}) {
  return (
    <div
      className="card"
      style={{
        padding: "16px 18px",
        cursor: "pointer",
        borderColor: expanded ? "var(--accent-primary)" : undefined,
        gridColumn: expanded ? "1 / -1" : undefined,
      }}
      onClick={onToggle}
      role="button"
      tabIndex={0}
      aria-expanded={expanded}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onToggle();
        }
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <span style={{ fontWeight: 700, fontSize: 14 }}>{item.country}</span>
        <span className="tabular-nums" style={{ fontSize: 11, color: "var(--text-muted)" }}>
          Gap {fmt(item.observed_gap_pct_point)}
        </span>
      </div>

      <div style={{ marginTop: 10, display: "flex", flexDirection: "column", gap: 6 }}>
        <MiniBar label="문화경험률" value={item.culture_experience_rate_pct} color="var(--accent-blue)" />
        <MiniBar label="방한의향 있음률" value={item.visit_intention_positive_pct} color="var(--accent-orange)" />
      </div>

      <p
        style={{
          fontSize: 11,
          color: "var(--text-secondary)",
          margin: "10px 0 0",
          whiteSpace: "nowrap",
          overflow: "hidden",
          textOverflow: "ellipsis",
        }}
        title={item.top_visit_barrier ?? undefined}
      >
        주요 장벽(방문 비의향자 기준): {item.top_visit_barrier ?? "정보 없음"}{" "}
        {item.top_visit_barrier_rate_pct !== null && (
          <span className="tabular-nums">({fmt(item.top_visit_barrier_rate_pct)}%)</span>
        )}
      </p>

      {expanded && profile && (
        <div
          style={{
            marginTop: 16,
            paddingTop: 16,
            borderTop: "1px solid var(--gridline)",
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: 20,
          }}
          onClick={(e) => e.stopPropagation()}
        >
          <div>
            <h4 style={{ fontSize: 12, margin: "0 0 8px", color: "var(--text-secondary)" }}>
              해당 병목 유형 (판정 근거: 각 값이 23개국 중 상위3분위인지 여부)
            </h4>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {FLAG_LABELS.map(({ key, label }) => {
                const isFlagged = profile[key] === "Y";
                return (
                  <span
                    key={key}
                    style={{
                      fontSize: 11,
                      padding: "3px 8px",
                      borderRadius: 999,
                      background: isFlagged ? "var(--accent-primary-soft)" : "var(--card-bg-soft)",
                      color: isFlagged ? "var(--accent-primary)" : "var(--text-muted)",
                      border: `1px solid ${isFlagged ? "var(--accent-primary)" : "var(--gridline)"}`,
                      opacity: isFlagged ? 1 : 0.5,
                    }}
                  >
                    {label}
                  </span>
                );
              })}
            </div>
            {profile.small_sample_barrier_note === "Y" && (
              <p style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 8 }}>
                ⚠ 방문 비의향자 표본 30명 미만 — 장벽 수치를 국가 간 비교의 강한 근거로 사용하지 않습니다.
              </p>
            )}
          </div>
          <div>
            <h4 style={{ fontSize: 12, margin: "0 0 8px", color: "var(--text-secondary)" }}>
              국가별 주요 관찰 패턴
            </h4>
            <p style={{ fontSize: 12, margin: "0 0 10px", lineHeight: 1.5 }}>
              {profile.key_observed_pattern || "해당 없음"}
            </p>
            <p style={{ fontSize: 10, color: "var(--text-muted)", margin: 0, lineHeight: 1.4 }}>
              {profile.interpretation_caution}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

function MiniBar({ label, value, color }: { label: string; value: number | null; color: string }) {
  const pct = value ?? 0;
  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 10, color: "var(--text-muted)" }}>
        <span>{label}</span>
        <span className="tabular-nums">{fmt(value)}%</span>
      </div>
      <div style={{ height: 6, borderRadius: 4, background: "var(--card-bg-soft)", border: "1px solid var(--gridline)" }}>
        <div style={{ width: `${Math.min(pct, 100)}%`, height: "100%", background: color, borderRadius: 4 }} />
      </div>
    </div>
  );
}

export default function CountryGrid({
  countryGrid,
  bottleneckProfiles,
}: {
  countryGrid: CountryGridItem[];
  bottleneckProfiles: CountryBottleneckProfile[];
}) {
  const [sortKey, setSortKey] = useState<SortKey>("name");
  const [expandedCountry, setExpandedCountry] = useState<string | null>(null);

  const profileByCountry = useMemo(() => {
    const map = new Map<string, CountryBottleneckProfile>();
    bottleneckProfiles.forEach((p) => map.set(p.country, p));
    return map;
  }, [bottleneckProfiles]);

  const sorted = useMemo(() => {
    const items = [...countryGrid];
    if (sortKey === "name") {
      items.sort((a, b) => a.country.localeCompare(b.country, "ko"));
    } else {
      items.sort((a, b) => (b[sortKey] ?? -Infinity) - (a[sortKey] ?? -Infinity));
    }
    return items;
  }, [countryGrid, sortKey]);

  return (
    <section className="card" style={{ padding: "24px 28px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", flexWrap: "wrap", gap: 12 }}>
        <div>
          <h2 style={{ fontSize: 16, margin: "0 0 4px" }}>국가 그리드 (23개국)</h2>
          <p style={{ fontSize: 13, color: "var(--text-secondary)", margin: 0 }}>
            카드를 클릭하면 해당 국가의 병목 유형과 주요 관찰 패턴을 펼쳐볼 수 있습니다. 순위가 아니라 정렬 기준을
            선택할 수 있습니다.
          </p>
        </div>
        <label style={{ fontSize: 12, color: "var(--text-secondary)", display: "flex", alignItems: "center", gap: 6 }}>
          정렬 기준
          <select
            value={sortKey}
            onChange={(e) => setSortKey(e.target.value as SortKey)}
            style={{
              fontSize: 12,
              padding: "6px 10px",
              borderRadius: 8,
              border: "1px solid var(--gridline)",
              background: "var(--card-bg)",
              color: "var(--text-primary)",
            }}
          >
            {SORT_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div
        style={{
          marginTop: 20,
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))",
          gap: 14,
        }}
      >
        {sorted.map((item) => (
          <CountryCard
            key={item.country}
            item={item}
            profile={profileByCountry.get(item.country)}
            expanded={expandedCountry === item.country}
            onToggle={() =>
              setExpandedCountry((current) => (current === item.country ? null : item.country))
            }
          />
        ))}
      </div>
    </section>
  );
}
