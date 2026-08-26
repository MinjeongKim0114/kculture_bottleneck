"use client";

import { useEffect, useRef, useState } from "react";
import { ApiError, getCountryDetail } from "@/lib/api";
import type { CountryDetailResponse } from "@/types/api";
import { BOTTLENECK_FLAG_LABELS } from "@/lib/labels";
import GapTierBadge from "@/components/GapTierBadge";

function GapCard({ label, valuePct, tier }: { label: string; valuePct: number; tier: string }) {
  return (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        gap: 12,
        background: "var(--card-bg-soft)",
        border: "1px solid var(--gridline)",
        borderRadius: "var(--radius-md)",
        padding: "14px 16px",
      }}
    >
      <div>
        <div style={{ fontSize: 12, color: "var(--text-secondary)", marginBottom: 4 }}>{label}</div>
        <div className="tabular-nums" style={{ fontSize: 24, fontWeight: 500, color: "var(--tone-gap-text)" }}>
          {valuePct.toFixed(1)}%p
        </div>
      </div>
      <GapTierBadge tier={tier} />
    </div>
  );
}

function MetricCard({ label, value, tier }: { label: string; value: number; tier?: string }) {
  return (
    <div title={tier ? `23개국 중 상대적 위치: ${tier}` : undefined}>
      <div style={{ fontSize: 12, color: "var(--text-secondary)", marginBottom: 4 }}>{label}</div>
      <div className="tabular-nums" style={{ fontSize: 20, fontWeight: 500 }}>
        {value.toFixed(1)}%
      </div>
    </div>
  );
}

function BarrierBar({ label, ratePct }: { label: string; ratePct: number }) {
  return (
    <div style={{ padding: "6px 0" }}>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, marginBottom: 4 }}>
        <span style={{ color: "var(--text-secondary)" }}>{label}</span>
        <span className="tabular-nums" style={{ fontWeight: 500 }}>
          {ratePct.toFixed(1)}%
        </span>
      </div>
      <div style={{ height: 6, borderRadius: 4, background: "var(--card-bg-soft)", border: "1px solid var(--gridline)", overflow: "hidden" }}>
        <div style={{ width: `${ratePct}%`, height: "100%", background: "var(--accent-blue)", borderRadius: 4 }} />
      </div>
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
        지도에서 국가 위에 커서를 올리면
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
  const requestIdRef = useRef(0);

  useEffect(() => {
    if (!country) {
      setDetail(null);
      return;
    }
    const requestId = ++requestIdRef.current;
    // 지도 위에서 커서를 빠르게 옮기면 국가가 연달아 바뀔 수 있어, 짧게 디바운스하고
    // 응답이 늦게 와도 그 사이 다른 국가로 바뀌었으면(stale) 반영하지 않는다.
    const timer = setTimeout(() => {
      setLoading(true);
      setError(null);
      getCountryDetail(country)
        .then((res) => {
          if (requestIdRef.current === requestId) setDetail(res);
        })
        .catch((err: unknown) => {
          if (requestIdRef.current === requestId) {
            setError(err instanceof ApiError ? err.message : "국가 정보를 불러오지 못했습니다.");
          }
        })
        .finally(() => {
          if (requestIdRef.current === requestId) setLoading(false);
        });
    }, 150);

    return () => clearTimeout(timer);
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
          <h2 style={{ fontSize: 20, fontWeight: 500, margin: "0 0 2px" }}>{detail.profile.country}</h2>
          <p style={{ fontSize: 11, color: "var(--text-muted)", margin: "0 0 14px" }}>국가 선택 상세</p>

          {(detail.direct_gap || detail.conditional_gap) && (
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {detail.direct_gap && (
                <GapCard
                  label="한류 경험 대비 방한 의향 격차"
                  valuePct={detail.direct_gap.observed_gap_pct_point}
                  tier={detail.direct_gap.gap_tier}
                />
              )}
              {detail.conditional_gap && (
                <GapCard
                  label="문화경험자의 호감도 대비 방문의향 격차"
                  valuePct={detail.conditional_gap.observed_conditional_gap_pct_point}
                  tier={detail.conditional_gap.gap_tier}
                />
              )}
            </div>
          )}

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(2, 1fr)",
              gap: 12,
              marginTop: 18,
              paddingTop: 14,
              borderTop: "1px solid var(--gridline)",
            }}
            className="detail-metric-grid"
          >
            <MetricCard
              label="한류 경험"
              value={detail.profile.culture_experience_rate_pct}
              tier={detail.pattern_profile.culture_experience_rate_pct_tier}
            />
            <MetricCard
              label="방한의향"
              value={detail.profile.visit_intention_positive_pct}
              tier={detail.pattern_profile.visit_intention_positive_pct_tier}
            />
            <MetricCard
              label="경험 후 호감도"
              value={detail.profile.culture_to_korea_positive_pct}
              tier={detail.pattern_profile.culture_to_korea_positive_pct_tier}
            />
            <MetricCard
              label="경험 후 방문의향"
              value={detail.profile.culture_to_visit_positive_pct}
              tier={detail.pattern_profile.culture_to_visit_positive_pct_tier}
            />
          </div>

          {detail.top_barriers.length > 0 && (
            <div style={{ borderTop: "1px solid var(--gridline)", paddingTop: 12, marginTop: 16 }}>
              <h3 style={{ fontSize: 12, margin: "0 0 6px", color: "var(--text-muted)" }}>
                주요 장벽 Top{detail.top_barriers.length} (방문 비의향자 기준)
              </h3>
              {detail.top_barriers.map((b) => (
                <BarrierBar key={b.barrier} label={b.barrier.replace(/_/g, " ")} ratePct={b.rate_pct} />
              ))}
            </div>
          )}

          {detail.bottleneck_profile && (
            <div style={{ borderTop: "1px solid var(--gridline)", paddingTop: 12, marginTop: 16 }}>
              <h3 style={{ fontSize: 12, margin: "0 0 6px", color: "var(--text-muted)" }}>병목 프로파일</h3>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 5, marginBottom: 8 }}>
                {BOTTLENECK_FLAG_LABELS.map(({ key, label }) => {
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
                        whiteSpace: "nowrap",
                      }}
                    >
                      {label}
                    </span>
                  );
                })}
              </div>
              <p style={{ fontSize: 12, margin: 0, lineHeight: 1.5 }}>
                {detail.bottleneck_profile.key_observed_pattern || "해당 없음"}
              </p>
            </div>
          )}

          <details className="caveat" style={{ marginTop: 16, paddingTop: 12, borderTop: "1px solid var(--gridline)" }}>
            <summary>계산 기준 및 해석 주의사항</summary>
            <div style={{ fontSize: 11, color: "var(--text-muted)", lineHeight: 1.6, marginTop: 8 }}>
              <p style={{ margin: "0 0 6px" }}>
                핵심 지표의 상대적 위치(23개국 중 상·중·하위)는 항목에 마우스를 올리면 볼 수 있으며, 절대적인
                좋음/나쁨을 뜻하지 않습니다.
              </p>
              <p style={{ margin: "0 0 6px" }}>
                Direct Gap과 Conditional Gap은 서로 다른 기준 응답자 집단에서 계산된 별개 관찰값으로, 직접
                비교할 수 없습니다.
              </p>
              {detail.barrier_pattern && (
                <p style={{ margin: "0 0 6px" }}>
                  주요 장벽 표본 n={detail.barrier_pattern.sample_n}
                  {detail.barrier_pattern.small_sample_flag === "Y" && " · 소표본 주의(30명 미만)"}
                </p>
              )}
              {detail.bottleneck_profile?.interpretation_caution && (
                <p style={{ margin: 0 }}>{detail.bottleneck_profile.interpretation_caution}</p>
              )}
            </div>
          </details>
        </div>
      )}
    </section>
  );
}
