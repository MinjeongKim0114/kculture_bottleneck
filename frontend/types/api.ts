/**
 * FastAPI 응답 타입.
 * 필드명은 dashboard_data_dictionary.md / CSV 컬럼명과 동일하게 유지한다.
 * 프론트엔드에서 새 지표를 만들지 않고, 백엔드가 내려주는 값만 그대로 표현한다.
 */

export interface IndicatorDistribution {
  indicator: string;
  table_id: string;
  layer: string;
  comparability: string;
  base_type: string;
  n_countries: number;
  min: number;
  q1: number;
  median: number;
  q3: number;
  max: number;
  mean: number;
  stdev: number;
}

export interface CountryGridItem {
  country: string;
  culture_experience_rate_pct: number | null;
  visit_intention_positive_pct: number | null;
  observed_gap_pct_point: number | null;
  top_visit_barrier: string | null;
  top_visit_barrier_rate_pct: number | null;
}

export interface BottleneckTypeSummary {
  type_code: string;
  type_label: string;
  criterion: string;
  n_countries: number;
  pct_of_23: number;
  country_list: string;
  n_also_in_other_type: number;
  major_barrier_detail: string;
  prior_gap_consistency_note: string;
  overly_broad_flag: string;
}

export interface CountryBottleneckProfile {
  country: string;
  direct_gap_pct_point: number | null;
  direct_gap_type_flag: "Y" | "N";
  conditional_gap_pct_point: number | null;
  conditional_gap_type_flag: "Y" | "N";
  cognition_interest_barrier_flag: "Y" | "N";
  image_barrier_flag: "Y" | "N";
  economic_physical_access_barrier_flag: "Y" | "N";
  institutional_language_barrier_flag: "Y" | "N";
  religious_cultural_env_barrier_flag: "Y" | "N";
  small_sample_barrier_note: string;
  key_observed_pattern: string;
  interpretation_caution: string;
}

export interface DirectGapRecord {
  country: string;
  culture_experience_rate_pct: number;
  visit_intention_positive_pct: number;
  observed_gap_pct_point: number;
  gap_tier: string;
  base_type: string;
  comparability: string;
}

export interface ConditionalGapRecord {
  country: string;
  culture_to_korea_positive_pct: number;
  culture_to_visit_positive_pct: number;
  observed_conditional_gap_pct_point: number;
  gap_tier: string;
  base_type: string;
  comparability: string;
}

export interface OverviewResponse {
  indicator_distribution: IndicatorDistribution[];
  country_grid: CountryGridItem[];
  bottleneck_type_summary: BottleneckTypeSummary[];
  country_bottleneck_profiles: CountryBottleneckProfile[];
  direct_gap: DirectGapRecord[];
  conditional_gap: ConditionalGapRecord[];
}

export interface CountryProfile {
  country: string;
  culture_experience_rate_pct: number;
  culture_experience_rate_base_type: string;
  hallyu_overall_liking_score: number;
  culture_to_korea_positive_pct: number;
  hallyu_perception_positive_pct: number;
  visit_intention_positive_pct: number;
  culture_to_visit_positive_pct: number;
  top_visit_barrier: string;
  top_visit_barrier_rate_pct: number;
}

export type Tercile = "하위3분위" | "중위3분위" | "상위3분위";

export interface CountryPatternProfile {
  country: string;
  culture_experience_rate_pct: number;
  culture_experience_rate_pct_tier: Tercile;
  hallyu_perception_positive_pct: number;
  hallyu_perception_positive_pct_tier: Tercile;
  culture_to_korea_positive_pct: number;
  culture_to_korea_positive_pct_tier: Tercile;
  visit_intention_positive_pct: number;
  visit_intention_positive_pct_tier: Tercile;
  culture_to_visit_positive_pct: number;
  culture_to_visit_positive_pct_tier: Tercile;
  top_visit_barrier: string;
  top_visit_barrier_rate_pct: number;
}

export interface BarrierPattern {
  country: string;
  base_type: string;
  sample_n: number;
  small_sample_flag: "Y" | "N";
  [barrierColumn: string]: string | number;
}

export interface TopBarrier {
  barrier: string;
  rate_pct: number;
}

export interface CountryDetailResponse {
  profile: CountryProfile;
  pattern_profile: CountryPatternProfile;
  direct_gap: DirectGapRecord | null;
  conditional_gap: ConditionalGapRecord | null;
  barrier_pattern: BarrierPattern | null;
  top_barriers: TopBarrier[];
  bottleneck_profile: CountryBottleneckProfile | null;
}

export interface ChatResponse {
  answer: string;
  follow_up_questions: string[];
}
