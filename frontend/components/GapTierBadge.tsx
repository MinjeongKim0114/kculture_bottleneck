import { GAP_TIER_LABELS } from "@/lib/labels";

// 격차 강도(작음/보통/큼)는 색조 진하기가 아니라 배지 텍스트로만 구분한다 — 단일 톤 고정.
export default function GapTierBadge({ tier, small = false }: { tier: string; small?: boolean }) {
  return (
    <span
      title={tier}
      style={{
        fontSize: small ? 11 : 12,
        fontWeight: 500,
        color: "var(--tone-gap-text)",
        background: "var(--tone-gap-bg)",
        borderRadius: 999,
        padding: small ? "3px 9px" : "4px 12px",
        whiteSpace: "nowrap",
        flexShrink: 0,
      }}
    >
      {GAP_TIER_LABELS[tier] ?? tier}
    </span>
  );
}
