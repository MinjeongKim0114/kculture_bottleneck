"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { ApiError, getOverview } from "@/lib/api";
import type { OverviewResponse } from "@/types/api";
import LoadingState from "@/components/LoadingState";
import ErrorState from "@/components/ErrorState";
import WorldMap from "@/components/map/WorldMap";
import CountryDetailPanel from "@/components/map/CountryDetailPanel";

export default function OverviewPage() {
  const [data, setData] = useState<OverviewResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedCountry, setSelectedCountry] = useState<string | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    getOverview()
      .then(setData)
      .catch((err: unknown) => {
        setError(err instanceof ApiError ? err.message : "알 수 없는 오류가 발생했습니다.");
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <main
      style={{
        maxWidth: 1440,
        margin: "0 auto",
        padding: "24px 24px 40px",
        display: "flex",
        flexDirection: "column",
        minHeight: "100vh",
      }}
    >
      <header style={{ marginBottom: 16, display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 16 }}>
        <div>
          <p
            style={{
              fontSize: 11,
              fontWeight: 700,
              letterSpacing: "0.06em",
              color: "var(--accent-primary)",
              margin: "0 0 6px",
              textTransform: "uppercase",
            }}
          >
            Overview
          </p>
          <h1 style={{ fontSize: 22, margin: "0 0 6px" }}>
            한류 경험 · 인식 · 방한의향 — 23개국 관찰 패턴 탐색
          </h1>
          <p style={{ fontSize: 12.5, color: "var(--text-secondary)", margin: 0, maxWidth: 820 }}>
            지도에서 국가를 선택해 문화 경험·인식·방한의향 사이에 관찰되는 패턴을 탐색하세요.
          </p>
        </div>
        <Link
          href="/chat"
          style={{
            flexShrink: 0,
            border: "none",
            borderRadius: 999,
            background: "var(--accent-primary)",
            color: "#fff",
            padding: "10px 18px",
            fontSize: 13,
            fontWeight: 600,
            textDecoration: "none",
            whiteSpace: "nowrap",
          }}
        >
          AI Analyst에게 물어보기
        </Link>
      </header>

      {loading && <LoadingState />}
      {!loading && error && <ErrorState message={error} onRetry={load} />}

      {!loading && !error && data && (
        <div style={{ display: "flex", flexDirection: "column", gap: 16, flex: 1, minHeight: 0 }}>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "minmax(0, 2.1fr) minmax(280px, 1fr)",
              gap: 16,
              height: "min(72vh, 640px)",
              minHeight: 460,
            }}
            className="overview-main-grid"
          >
            <WorldMap
              countryGrid={data.country_grid}
              indicatorDistribution={data.indicator_distribution}
              selectedCountry={selectedCountry}
              onSelectCountry={setSelectedCountry}
            />
            <CountryDetailPanel country={selectedCountry} />
          </div>
        </div>
      )}
    </main>
  );
}
