import type { ConditionalGapRecord, DirectGapRecord } from "@/types/api";

const AXIS_MAX = 100;
const ROW_HEIGHT = 26;

interface DumbbellRow {
  country: string;
  a: number;
  b: number;
  gap: number;
}

// Country label column width reserved separately from the plot for legibility.
const LABEL_WIDTH = 56;

function DumbbellRows({ rows, maxHeight = 420 }: { rows: DumbbellRow[]; maxHeight?: number }) {
  const sorted = [...rows].sort((x, y) => x.country.localeCompare(y.country, "ko"));
  return (
    <div className="scroll-panel" style={{ maxHeight }}>
      {sorted.map((row) => {
        const pa = (row.a / AXIS_MAX) * 100;
        const pb = (row.b / AXIS_MAX) * 100;
        const lo = Math.min(pa, pb);
        const hi = Math.max(pa, pb);
        return (
          <div key={row.country} style={{ display: "flex", alignItems: "center", height: ROW_HEIGHT, gap: 8 }}>
            <div
              style={{
                width: LABEL_WIDTH,
                fontSize: 11,
                color: "var(--text-secondary)",
                flexShrink: 0,
                whiteSpace: "nowrap",
                overflow: "hidden",
                textOverflow: "ellipsis",
              }}
              title={row.country}
            >
              {row.country}
            </div>
            <div style={{ position: "relative", flex: 1, minWidth: 0, height: 20 }}>
              <div
                style={{
                  position: "absolute",
                  left: 0,
                  right: 0,
                  top: "50%",
                  height: 1,
                  background: "var(--gridline)",
                }}
              />
              <div
                style={{
                  position: "absolute",
                  left: `${lo}%`,
                  width: `${hi - lo}%`,
                  top: "50%",
                  height: 2,
                  marginTop: -1,
                  background: "var(--baseline)",
                }}
              />
              <div
                style={{
                  position: "absolute",
                  left: `${pa}%`,
                  top: "50%",
                  width: 9,
                  height: 9,
                  marginLeft: -4.5,
                  marginTop: -4.5,
                  borderRadius: "50%",
                  background: "var(--accent-blue)",
                  border: "1.5px solid #fff",
                  boxShadow: "0 0 0 1px var(--gridline)",
                }}
              />
              <div
                style={{
                  position: "absolute",
                  left: `${pb}%`,
                  top: "50%",
                  width: 9,
                  height: 9,
                  marginLeft: -4.5,
                  marginTop: -4.5,
                  borderRadius: "50%",
                  background: "var(--accent-orange)",
                  border: "1.5px solid #fff",
                  boxShadow: "0 0 0 1px var(--gridline)",
                }}
              />
            </div>
            <div
              className="tabular-nums"
              style={{ fontSize: 11, color: "var(--text-muted)", flexShrink: 0, width: 52, textAlign: "right" }}
            >
              {row.gap.toFixed(1)}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default function GapSection({
  directGap,
  conditionalGap,
  compact = false,
}: {
  directGap: DirectGapRecord[];
  conditionalGap: ConditionalGapRecord[];
  compact?: boolean;
}) {
  const directRows: DumbbellRow[] = directGap.map((r) => ({
    country: r.country,
    a: r.culture_experience_rate_pct,
    b: r.visit_intention_positive_pct,
    gap: r.observed_gap_pct_point,
  }));
  const conditionalRows: DumbbellRow[] = conditionalGap.map((r) => ({
    country: r.country,
    a: r.culture_to_korea_positive_pct,
    b: r.culture_to_visit_positive_pct,
    gap: r.observed_conditional_gap_pct_point,
  }));

  return (
    <section className="card" style={{ padding: compact ? "16px 18px" : "24px 28px", height: "100%" }}>
      <h2 style={{ fontSize: compact ? 14 : 16, margin: "0 0 4px" }}>Direct Gap · Conditional Gap</h2>
      {!compact && (
        <p style={{ fontSize: 13, color: "var(--text-secondary)", margin: "0 0 4px" }}>
          두 Gap은 서로 다른 BASE에서 계산된 별개의 관찰값입니다. 하나의 지표로 합치지 않고 항상 구분해 표시합니다.
        </p>
      )}
      {compact && (
        <p style={{ fontSize: 11, color: "var(--text-muted)", margin: "0 0 8px" }}>
          서로 다른 BASE의 별개 관찰값 · 하나로 합치지 않음
        </p>
      )}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: compact ? 16 : 24,
          marginTop: compact ? 4 : 16,
        }}
      >
        <div>
          <h3 style={{ fontSize: compact ? 11 : 13, margin: "0 0 4px", color: "var(--text-secondary)" }}>
            Direct Gap {!compact && "(E1A-1 ↔ B5B-1)"}
          </h3>
          {!compact && (
            <p style={{ fontSize: 11, color: "var(--text-muted)", margin: "0 0 10px" }}>
              BASE: 전체 응답자(n=16,360, 동일 모집단) · comparability: direct_within_survey
            </p>
          )}
          <DumbbellRows rows={directRows} maxHeight={compact ? 150 : 420} />
          {!compact && (
            <div style={{ display: "flex", gap: 16, fontSize: 11, color: "var(--text-secondary)", marginTop: 10 }}>
              <span>
                <svg width="10" height="10" style={{ verticalAlign: "middle", marginRight: 4 }}>
                  <circle cx="5" cy="5" r="5" fill="var(--accent-blue)" />
                </svg>
                문화경험률
              </span>
              <span>
                <svg width="10" height="10" style={{ verticalAlign: "middle", marginRight: 4 }}>
                  <circle cx="5" cy="5" r="5" fill="var(--accent-orange)" />
                </svg>
                방한의향 있음률
              </span>
            </div>
          )}
        </div>
        <div>
          <h3 style={{ fontSize: compact ? 11 : 13, margin: "0 0 4px", color: "var(--text-secondary)" }}>
            Conditional Gap {!compact && "(E4-1 ↔ E4-3)"}
          </h3>
          {!compact && (
            <p style={{ fontSize: 11, color: "var(--text-muted)", margin: "0 0 10px" }}>
              BASE: 문화경험자(전체의 하위집합) · comparability: conditional
            </p>
          )}
          <DumbbellRows rows={conditionalRows} maxHeight={compact ? 150 : 420} />
          {!compact && (
            <div style={{ display: "flex", gap: 16, fontSize: 11, color: "var(--text-secondary)", marginTop: 10 }}>
              <span>
                <svg width="10" height="10" style={{ verticalAlign: "middle", marginRight: 4 }}>
                  <circle cx="5" cy="5" r="5" fill="var(--accent-blue)" />
                </svg>
                문화경험→호감도 긍정률
              </span>
              <span>
                <svg width="10" height="10" style={{ verticalAlign: "middle", marginRight: 4 }}>
                  <circle cx="5" cy="5" r="5" fill="var(--accent-orange)" />
                </svg>
                문화경험→방문의향 긍정률
              </span>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
