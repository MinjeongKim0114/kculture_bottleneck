import type { IndicatorDistribution } from "@/types/api";

const INDICATOR_LABELS: Record<string, string> = {
  culture_experience_rate_pct: "문화경험률 (E1A-1)",
  hallyu_perception_positive_pct: "한류실태 인식긍정률 (1-35, 별도 패널)",
  culture_to_korea_positive_pct: "문화경험→호감도 긍정률 (E4-1)",
  visit_intention_positive_pct: "방한의향 있음률 (B5B-1)",
  culture_to_visit_positive_pct: "문화경험→방문의향 긍정률 (E4-3)",
};

const AXIS_MAX = 100;
const CHART_WIDTH = 560;
const LEFT_PAD = 8;
const RIGHT_PAD = 8;
const PLOT_WIDTH = CHART_WIDTH - LEFT_PAD - RIGHT_PAD;

function xFor(value: number): number {
  return LEFT_PAD + (value / AXIS_MAX) * PLOT_WIDTH;
}

function Row({ row }: { row: IndicatorDistribution }) {
  const label = INDICATOR_LABELS[row.indicator] ?? row.indicator;
  const isSeparatePanel = row.comparability === "conditional" && row.indicator === "hallyu_perception_positive_pct";

  return (
    <div style={{ marginBottom: 22 }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "baseline",
          marginBottom: 6,
          gap: 8,
          flexWrap: "wrap",
        }}
      >
        <span style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)" }}>
          {label}
        </span>
        <span style={{ fontSize: 11, color: "var(--text-muted)" }}>
          BASE: {row.base_type}
          {isSeparatePanel ? " · 별도 패널" : ""} · n={row.n_countries}개국
        </span>
      </div>
      <svg
        viewBox={`0 0 ${CHART_WIDTH} 40`}
        width="100%"
        height={40}
        role="img"
        aria-label={`${label} 분포: 최소 ${row.min}, 1분위 ${row.q1}, 중앙값 ${row.median}, 3분위 ${row.q3}, 최대 ${row.max}`}
      >
        {/* baseline */}
        <line
          x1={LEFT_PAD}
          x2={CHART_WIDTH - RIGHT_PAD}
          y1={26}
          y2={26}
          stroke="var(--gridline)"
          strokeWidth={1}
        />
        {/* whisker min-q1 */}
        <line
          x1={xFor(row.min)}
          x2={xFor(row.q1)}
          y1={20}
          y2={20}
          stroke="var(--baseline)"
          strokeWidth={2}
        />
        {/* whisker q3-max */}
        <line
          x1={xFor(row.q3)}
          x2={xFor(row.max)}
          y1={20}
          y2={20}
          stroke="var(--baseline)"
          strokeWidth={2}
        />
        {/* box q1-q3 */}
        <rect
          x={xFor(row.q1)}
          y={12}
          width={Math.max(xFor(row.q3) - xFor(row.q1), 1)}
          height={16}
          rx={4}
          fill="var(--accent-blue-soft)"
          stroke="var(--accent-blue)"
          strokeWidth={1}
        />
        {/* min / max ticks */}
        <line x1={xFor(row.min)} x2={xFor(row.min)} y1={14} y2={26} stroke="var(--baseline)" strokeWidth={2} />
        <line x1={xFor(row.max)} x2={xFor(row.max)} y1={14} y2={26} stroke="var(--baseline)" strokeWidth={2} />
        {/* median dot */}
        <circle cx={xFor(row.median)} cy={20} r={5} fill="var(--accent-blue)" stroke="#fff" strokeWidth={1.5} />
      </svg>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          fontSize: 11,
          color: "var(--text-muted)",
          marginTop: 2,
        }}
        className="tabular-nums"
      >
        <span>min {row.min}</span>
        <span>q1 {row.q1}</span>
        <span style={{ fontWeight: 700, color: "var(--accent-blue)" }}>중앙값 {row.median}</span>
        <span>q3 {row.q3}</span>
        <span>max {row.max}</span>
      </div>
    </div>
  );
}

export default function IndicatorDistributionSection({
  data,
}: {
  data: IndicatorDistribution[];
}) {
  return (
    <section className="card" style={{ padding: "24px 28px" }}>
      <h2 style={{ fontSize: 16, margin: "0 0 4px" }}>Layer 1~3 핵심 지표 분포</h2>
      <p style={{ fontSize: 13, color: "var(--text-secondary)", margin: "0 0 20px" }}>
        23개국의 분포 모양(최소~최대, 1·3분위, 중앙값)을 보여줍니다. 특정 국가나 1위를 강조하지 않습니다.
      </p>
      {data.map((row) => (
        <Row key={row.indicator} row={row} />
      ))}
    </section>
  );
}
