import type { BottleneckTypeSummary } from "@/types/api";

const MAX_COUNT = 23;

// Type A/B의 원본 라벨("Direct/Conditional Gap 상위3분위")은 통계적 정의를 그대로 서술한 것이라
// C~G의 장벽 이름과 톤이 달라 직관적이지 않다는 피드백에 따라 화면 표시용으로만 순화한다.
// 원본 정의는 criterion 텍스트(비압축 모드)에 그대로 남아 있어 정보 손실은 없다.
const DISPLAY_LABEL_OVERRIDES: Record<string, string> = {
  "Type A": "격차 상위국 (전체 응답자 기준)",
  "Type B": "격차 상위국 (문화경험자 기준)",
};

export default function BottleneckSummary({
  data,
  compact = false,
}: {
  data: BottleneckTypeSummary[];
  compact?: boolean;
}) {
  return (
    <section className="card" style={{ padding: compact ? "16px 18px" : "24px 28px", height: "100%" }}>
      <h2 style={{ fontSize: compact ? 14 : 16, margin: "0 0 4px" }}>병목 프로파일 요약 (Type A~G)</h2>
      {compact ? (
        <p style={{ fontSize: 11, color: "var(--text-muted)", margin: "0 0 10px" }}>
          유형별 관찰 국가 수 · 중복 소속 가능 · &quot;위험도&quot;가 아닌 관찰된 조합
        </p>
      ) : (
        <p style={{ fontSize: 13, color: "var(--text-secondary)", margin: "0 0 4px" }}>
          각 유형에 해당하는 관찰 조합이 몇 개국에서 나타나는지를 보여줍니다. 한 국가가 여러 유형에 동시에 속할 수
          있어 합계가 23개국을 넘을 수 있습니다. &quot;위험하다&quot;가 아니라 &quot;이런 조합이 관찰된다&quot;는
          의미입니다.
        </p>
      )}
      <div style={{ marginTop: compact ? 4 : 16 }}>
        {data.map((type) => {
          const widthPct = (type.n_countries / MAX_COUNT) * 100;
          return (
            <div key={type.type_code} style={{ marginBottom: compact ? 8 : 14 }} title={type.criterion}>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  fontSize: compact ? 11 : 12,
                  marginBottom: 4,
                  gap: 8,
                }}
              >
                <span style={{ fontWeight: 600 }}>
                  {type.type_code}
                  {` · ${DISPLAY_LABEL_OVERRIDES[type.type_code] ?? type.type_label}`}
                  {type.overly_broad_flag === "Y" && (
                    <span
                      style={{
                        marginLeft: 6,
                        fontSize: 10,
                        color: "var(--text-muted)",
                        fontWeight: 400,
                      }}
                      title="OR 조건 기반이라 국가 구별력이 상대적으로 약함"
                    >
                      (구별력 낮음)
                    </span>
                  )}
                </span>
                <span className="tabular-nums" style={{ color: "var(--text-secondary)" }}>
                  {type.n_countries}개국 · {type.pct_of_23}%
                </span>
              </div>
              <div
                style={{
                  height: compact ? 7 : 10,
                  borderRadius: 6,
                  background: "var(--card-bg-soft)",
                  border: "1px solid var(--gridline)",
                  overflow: "hidden",
                }}
              >
                <div
                  style={{
                    width: `${widthPct}%`,
                    height: "100%",
                    background: "var(--accent-blue)",
                    borderRadius: 6,
                  }}
                />
              </div>
              {!compact && (
                <p style={{ fontSize: 11, color: "var(--text-muted)", margin: "4px 0 0" }}>{type.criterion}</p>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}
