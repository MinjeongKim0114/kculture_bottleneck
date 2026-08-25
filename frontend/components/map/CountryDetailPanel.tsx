"use client";

import { useEffect, useState } from "react";
import { ApiError, getCountryDetail } from "@/lib/api";
import type { CountryBottleneckProfile, CountryDetailResponse } from "@/types/api";

const FLAG_LABELS: { key: keyof CountryBottleneckProfile; label: string }[] = [
  { key: "direct_gap_type_flag", label: "A · Direct Gap" },
  { key: "conditional_gap_type_flag", label: "B · Conditional Gap" },
  { key: "cognition_interest_barrier_flag", label: "C · 인지/관심" },
  { key: "image_barrier_flag", label: "D · 이미지" },
  { key: "economic_physical_access_barrier_flag", label: "E · 경제/물리적 접근성" },
  { key: "institutional_language_barrier_flag", label: "F · 제도/언어" },
  { key: "religious_cultural_env_barrier_flag", label: "G · 종교/문화환경" },
];

function TierTag({ tier }: { tier: string }) {
  return (
    <span
      style={{
        fontSize: 10,
        color: "var(--text-muted)",
        border: "1px solid var(--gridline)",
        borderRadius: 999,
        padding: "1px 7px",
        marginLeft: 6,
        whiteSpace: "nowrap",
      }}
    >
      {tier}
    </span>
  );
}

function IndicatorRow({ label, value, tier }: { label: string; value: number; tier?: string }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 12, padding: "5px 0" }}>
      <span style={{ color: "var(--text-secondary)" }}>{label}</span>
      <span>
        <span className="tabular-nums" style={{ fontWeight: 600 }}>
          {value.toFixed(1)}%
        </span>
        {tier && <TierTag tier={tier} />}
      </span>
    </div>
  );
}

function Placeholder() {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        height: "100%",
        textAlign: "center",
        padding: 24,
        color: "var(--text-muted)",
        gap: 8,
      }}
    >
      <span style={{ fontSize: 28 }}>🗺️</span>
      <p style={{ fontSize: 13, margin: 0 }}>
        지도에서 국가를 클릭하면
        <br />
        해당 국가의 상세 정보가 여기에 표시됩니다.
      </p>
    </div>
  );
}

export default function CountryDetailPanel({ country }: { country: string | null }) {
  const [detail, setDetail] = useState<CountryDetailResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!country) {
      setDetail(null);
      return;
    }
    setLoading(true);
    setError(null);
    getCountryDetail(country)
      .then(setDetail)
      .catch((err: unknown) => {
        setError(err instanceof ApiError ? err.message : "국가 정보를 불러오지 못했습니다.");
      })
      .finally(() => setLoading(false));
  }, [country]);

  return (
    <section
      className="card scroll-panel"
      style={{ padding: country ? "20px 22px" : 0, height: "100%", minHeight: 0 }}
    >
      {!country && <Placeholder />}

      {country && loading && (
        <div style={{ fontSize: 13, color: "var(--text-muted)", padding: 24, textAlign: "center" }}>
          {country} 정보를 불러오는 중…
        </div>
      )}

      {country && !loading && error && (
        <div style={{ fontSize: 13, color: "var(--text-secondary)", padding: 24, textAlign: "center" }}>{error}</div>
      )}

      {country && !loading && !error && detail && (
        <div>
          <h2 style={{ fontSize: 18, margin: "0 0 2px" }}>{detail.profile.country}</h2>
          <p style={{ fontSize: 11, color: "var(--text-muted)", margin: "0 0 14px" }}>
            국가 선택 상세 · Country Explorer는 다음 단계에서 전체 화면으로 제공됩니다.
          </p>

          <div style={{ borderTop: "1px solid var(--gridline)", paddingTop: 10 }}>
            <h3 style={{ fontSize: 12, margin: "0 0 4px", color: "var(--text-muted)" }}>Layer 1~3 핵심 지표</h3>
            <IndicatorRow
              label="문화경험률 (E1A-1)"
              value={detail.profile.culture_experience_rate_pct}
              tier={detail.pattern_profile.culture_experience_rate_pct_tier}
            />
            <IndicatorRow
              label="방한의향 있음률 (B5B-1)"
              value={detail.profile.visit_intention_positive_pct}
              tier={detail.pattern_profile.visit_intention_positive_pct_tier}
            />
            <IndicatorRow
              label="문화경험→호감도 (E4-1)"
              value={detail.profile.culture_to_korea_positive_pct}
              tier={detail.pattern_profile.culture_to_korea_positive_pct_tier}
            />
            <IndicatorRow
              label="문화경험→방문의향 (E4-3)"
              value={detail.profile.culture_to_visit_positive_pct}
              tier={detail.pattern_profile.culture_to_visit_positive_pct_tier}
            />
            <p style={{ fontSize: 10, color: "var(--text-muted)", margin: "4px 0 0" }}>
              tercile은 23개국 중 상대적 위치이며 절대적 좋음/나쁨이 아닙니다.
            </p>
          </div>

          {(detail.direct_gap || detail.conditional_gap) && (
            <div style={{ borderTop: "1px solid var(--gridline)", paddingTop: 10, marginTop: 12 }}>
              <h3 style={{ fontSize: 12, margin: "0 0 4px", color: "var(--text-muted)" }}>
                Gap (서로 다른 BASE의 별개 관찰값)
              </h3>
              {detail.direct_gap && (
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, padding: "4px 0" }}>
                  <span style={{ color: "var(--text-secondary)" }}>Direct Gap</span>
                  <span className="tabular-nums" style={{ fontWeight: 600 }}>
                    {detail.direct_gap.observed_gap_pct_point.toFixed(1)}%p
                    <TierTag tier={detail.direct_gap.gap_tier} />
                  </span>
                </div>
              )}
              {detail.conditional_gap && (
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, padding: "4px 0" }}>
                  <span style={{ color: "var(--text-secondary)" }}>Conditional Gap</span>
                  <span className="tabular-nums" style={{ fontWeight: 600 }}>
                    {detail.conditional_gap.observed_conditional_gap_pct_point.toFixed(1)}%p
                    <TierTag tier={detail.conditional_gap.gap_tier} />
                  </span>
                </div>
              )}
            </div>
          )}

          {detail.top_barriers.length > 0 && (
            <div style={{ borderTop: "1px solid var(--gridline)", paddingTop: 10, marginTop: 12 }}>
              <h3 style={{ fontSize: 12, margin: "0 0 4px", color: "var(--text-muted)" }}>
                주요 장벽 Top{detail.top_barriers.length} (방문 비의향자 기준)
              </h3>
              {detail.top_barriers.map((b) => (
                <div key={b.barrier} style={{ display: "flex", justifyContent: "space-between", fontSize: 12, padding: "3px 0" }}>
                  <span style={{ color: "var(--text-secondary)" }}>{b.barrier.replace(/_/g, " ")}</span>
                  <span className="tabular-nums">{b.rate_pct.toFixed(1)}%</span>
                </div>
              ))}
              {detail.barrier_pattern && (
                <p style={{ fontSize: 10, color: "var(--text-muted)", margin: "4px 0 0" }}>
                  표본 n={detail.barrier_pattern.sample_n}
                  {detail.barrier_pattern.small_sample_flag === "Y" && " · 소표본 주의(30명 미만)"}
                </p>
              )}
            </div>
          )}

          {detail.bottleneck_profile && (
            <div style={{ borderTop: "1px solid var(--gridline)", paddingTop: 10, marginTop: 12 }}>
              <h3 style={{ fontSize: 12, margin: "0 0 6px", color: "var(--text-muted)" }}>병목 프로파일</h3>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 5, marginBottom: 8 }}>
                {FLAG_LABELS.map(({ key, label }) => {
                  const isFlagged = detail.bottleneck_profile![key] === "Y";
                  return (
                    <span
                      key={key}
                      style={{
                        fontSize: 10,
                        padding: "2px 7px",
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
              <p style={{ fontSize: 12, margin: "0 0 8px", lineHeight: 1.5 }}>
                {detail.bottleneck_profile.key_observed_pattern || "해당 없음"}
              </p>
              <p style={{ fontSize: 10, color: "var(--text-muted)", margin: 0, lineHeight: 1.4 }}>
                {detail.bottleneck_profile.interpretation_caution}
              </p>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
