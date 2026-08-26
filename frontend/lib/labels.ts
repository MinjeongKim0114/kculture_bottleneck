import type { CountryBottleneckProfile } from "@/types/api";

// gap_tier 원본 문자열("Gap_큼(상위3분위)")은 통계적 정의를 그대로 서술한 것이라 일반 사용자에게
// 직관적이지 않다는 피드백에 따라 화면 표시용으로만 순화한다. 원본 값은 title 툴팁으로 보존한다.
// Country Detail Panel과 Country Grid가 같은 매핑을 공유해 표현이 어긋나지 않도록 여기서 관리한다.
export const GAP_TIER_LABELS: Record<string, string> = {
  "Gap_큼(상위3분위)": "격차 큰 편",
  "Gap_중간(중위3분위)": "격차 보통",
  "Gap_작음(하위3분위)": "격차 작은 편",
};

export const BOTTLENECK_FLAG_LABELS: { key: keyof CountryBottleneckProfile; label: string }[] = [
  { key: "direct_gap_type_flag", label: "A 격차상위(전체)" },
  { key: "conditional_gap_type_flag", label: "B 격차상위(경험자)" },
  { key: "cognition_interest_barrier_flag", label: "C 인지/관심" },
  { key: "image_barrier_flag", label: "D 이미지" },
  { key: "economic_physical_access_barrier_flag", label: "E 경제/물리적 접근성" },
  { key: "institutional_language_barrier_flag", label: "F 제도/언어" },
  { key: "religious_cultural_env_barrier_flag", label: "G 종교/문화환경" },
];
