-- Supabase(PostgreSQL) 스키마 생성 스크립트
--
-- 출처: data/processed/dashboard_data_dictionary.md (1~12절)
-- 이 스크립트는 딕셔너리에 정의된 컬럼/타입을 그대로 테이블로 옮긴 것이며,
-- 새로운 컬럼이나 계산 로직을 추가하지 않는다.
--
-- 사용법: Supabase 대시보드 > SQL Editor 에 전체를 붙여넣고 실행한다.

create extension if not exists vector;

-- =====================================================================
-- 1. country_profile_base (23행, A급) — 국가별 기본 프로필
-- =====================================================================
create table if not exists country_profile_base (
    country                             text primary key,
    culture_experience_rate_pct         double precision not null,
    culture_experience_rate_base_type   text not null,
    hallyu_overall_liking_score         double precision,
    culture_to_korea_positive_pct       double precision,
    hallyu_perception_positive_pct      double precision,
    visit_intention_positive_pct        double precision not null,
    culture_to_visit_positive_pct       double precision,
    top_visit_barrier                   text,
    top_visit_barrier_rate_pct          double precision
);

-- =====================================================================
-- 2. gap_analysis (23행, A급) — Direct Gap
-- =====================================================================
create table if not exists gap_analysis (
    country                       text primary key references country_profile_base(country),
    culture_experience_rate_pct  double precision not null,
    visit_intention_positive_pct double precision not null,
    observed_gap_pct_point       double precision not null,
    gap_tier                     text not null
        check (gap_tier in ('Gap_큼(상위3분위)', 'Gap_중간(중위3분위)', 'Gap_작음(하위3분위)')),
    base_type                    text not null,
    comparability                text not null default 'direct_within_survey'
        check (comparability = 'direct_within_survey')
);

-- =====================================================================
-- 3. conditional_gap_analysis (23행, A급) — Conditional Gap
-- =====================================================================
create table if not exists conditional_gap_analysis (
    country                                text primary key references country_profile_base(country),
    culture_to_korea_positive_pct         double precision not null,
    culture_to_visit_positive_pct         double precision not null,
    observed_conditional_gap_pct_point    double precision not null,
    gap_tier                              text not null
        check (gap_tier in ('Gap_큼(상위3분위)', 'Gap_중간(중위3분위)', 'Gap_작음(하위3분위)')),
    base_type                             text not null,
    comparability                         text not null default 'conditional'
        check (comparability = 'conditional')
);

-- =====================================================================
-- 4. barrier_pattern_analysis (23행, A급) — 8개 장벽
-- =====================================================================
create table if not exists barrier_pattern_analysis (
    country              text primary key references country_profile_base(country),
    base_type            text not null,
    sample_n             double precision,
    small_sample_flag    text check (small_sample_flag in ('Y', 'N')),
    "한류_관심_부재"       double precision,
    "낮은_한국_인지도"     double precision,
    "부정적_한국_이미지"   double precision,
    "불편한_언어소통"      double precision,
    "여행경비_물가"        double precision,
    "비자_출입국_절차"     double precision,
    "장거리_비행"          double precision,
    "불편한_종교환경"      double precision
);

-- =====================================================================
-- 5. country_bottleneck_profile (23행, A급) — 병목 프로파일
-- =====================================================================
create table if not exists country_bottleneck_profile (
    country                                   text primary key references country_profile_base(country),
    direct_gap_pct_point                      double precision,
    direct_gap_type_flag                      text check (direct_gap_type_flag in ('Y', 'N')),
    conditional_gap_pct_point                 double precision,
    conditional_gap_type_flag                 text check (conditional_gap_type_flag in ('Y', 'N')),
    cognition_interest_barrier_flag           text check (cognition_interest_barrier_flag in ('Y', 'N', '가능성(소표본 주의)')),
    image_barrier_flag                        text check (image_barrier_flag in ('Y', 'N', '가능성(소표본 주의)')),
    economic_physical_access_barrier_flag     text check (economic_physical_access_barrier_flag in ('Y', 'N', '가능성(소표본 주의)')),
    institutional_language_barrier_flag       text check (institutional_language_barrier_flag in ('Y', 'N', '가능성(소표본 주의)')),
    religious_cultural_env_barrier_flag       text check (religious_cultural_env_barrier_flag in ('Y', 'N', '가능성(소표본 주의)')),
    small_sample_barrier_note                 text check (small_sample_barrier_note in ('Y', 'N')),
    key_observed_pattern                      text,
    interpretation_caution                    text
);

-- =====================================================================
-- 6. bottleneck_type_summary (7행, B급) — 유형별 요약
-- =====================================================================
create table if not exists bottleneck_type_summary (
    type_code                    text primary key,
    type_label                   text not null,
    criterion                    text not null,
    n_countries                  integer not null,
    pct_of_23                    double precision not null,
    country_list                 text not null,
    n_also_in_other_type         integer not null,
    major_barrier_detail         text,
    prior_gap_consistency_note   text,
    overly_broad_flag            text check (overly_broad_flag in ('Y', 'N'))
);

-- =====================================================================
-- 7. gap_barrier_correlation (18행, B급) — 상관표
-- =====================================================================
create table if not exists gap_barrier_correlation (
    pair          text not null,
    subset        text not null,
    n             integer not null,
    pearson_r     double precision,
    pearson_p     double precision,
    spearman_r    double precision,
    spearman_p    double precision,
    direction     text check (direction in ('양(+)의 방향', '음(-)의 방향', '뚜렷한 방향 없음(거의 0)')),
    primary key (pair, subset)
);

-- =====================================================================
-- 8. sensitivity_analysis (9행, B급) — 소표본 민감도
-- =====================================================================
create table if not exists sensitivity_analysis (
    pair                 text primary key,
    n_full               integer,
    pearson_r_full       double precision,
    pearson_p_full       double precision,
    n_excl               integer,
    pearson_r_excl       double precision,
    pearson_p_excl       double precision,
    pearson_r_diff       double precision,
    direction_changed    text check (direction_changed in ('Y', 'N'))
);

-- =====================================================================
-- 9. country_indicator_distribution (5행, B급) — 핵심 지표 분포
-- =====================================================================
create table if not exists country_indicator_distribution (
    indicator        text primary key,
    table_id         text,
    layer            text,
    comparability    text,
    base_type        text,
    n_countries      integer not null,
    min              double precision,
    q1                double precision,
    median           double precision,
    q3               double precision,
    max              double precision,
    mean             double precision,
    stdev            double precision
);

-- =====================================================================
-- 10. country_pattern_profile (23행, B급) — tercile 프로파일
-- =====================================================================
create table if not exists country_pattern_profile (
    country                                     text primary key references country_profile_base(country),
    culture_experience_rate_pct                double precision,
    culture_experience_rate_pct_tier           text,
    hallyu_perception_positive_pct             double precision,
    hallyu_perception_positive_pct_tier        text,
    culture_to_korea_positive_pct              double precision,
    culture_to_korea_positive_pct_tier         text,
    visit_intention_positive_pct               double precision,
    visit_intention_positive_pct_tier          text,
    culture_to_visit_positive_pct              double precision,
    culture_to_visit_positive_pct_tier         text,
    top_visit_barrier                          text,
    top_visit_barrier_rate_pct                 double precision
);

-- =====================================================================
-- 11. country_bottleneck_observations (25행, C급) — 서술형 관찰 로그
-- =====================================================================
create table if not exists country_bottleneck_observations (
    id                       bigint generated always as identity primary key,
    country                  text not null references country_profile_base(country),
    comparability_class      text,
    observation_type         text,
    detail                   text,
    confidence               text
);

-- =====================================================================
-- 12. analysis_long (5,658행, C급) — 원천 롱포맷
-- =====================================================================
create table if not exists analysis_long (
    id                bigint generated always as identity primary key,
    country           text,
    layer             text,
    source_survey     text,
    table_id          text,
    indicator         text,
    response_option   text,
    base_type         text,
    sample_n          double precision,
    value             double precision,
    unit              text,
    comparability     text,
    note              text
);

-- 조회 패턴에 맞춘 최소 인덱스 (딕셔너리 12절: table_id로 근거 조회)
create index if not exists idx_analysis_long_country on analysis_long (country);
create index if not exists idx_analysis_long_table_id on analysis_long (table_id);

-- =====================================================================
-- 13. content_liking_disliking_reasons (17,960행, C급) — 콘텐츠 호감/비호감·부정인식 이유
-- 출처: data/processed/dashboard_data_dictionary.md 13절 (2026-08-26 추가)
-- 주의: 이 표는 한류실태조사 대상 30개국 전체를 다룬다. country_profile_base는
-- 잠재방한객조사 기준 23개국 고정 목록이라 일부 국가(아르헨티나·칠레·이탈리아·스페인·
-- 이집트 등 7개국)가 그쪽에는 없다 - 그래서 FK를 걸지 않는다(다른 모집단, 다른 절 참고).
-- =====================================================================
create table if not exists content_liking_disliking_reasons (
    id                     bigint generated always as identity primary key,
    country                text not null,
    table_id               text not null,
    indicator              text not null,
    content_category       text,
    item                   text not null,
    raw_item               text not null,
    rank_group             text not null,
    value                  double precision not null,
    unit                   text not null,
    base                   double precision,
    source_page            text,
    extraction_method      text,
    ocr_confidence         double precision,
    verification_status    text,
    notes                  text,
    label_confidence       text check (label_confidence in ('high_confidence', 'low_confidence'))
);

create index if not exists idx_content_reasons_country on content_liking_disliking_reasons (country);
create index if not exists idx_content_reasons_table_id on content_liking_disliking_reasons (table_id);
alter table content_liking_disliking_reasons enable row level security;

-- =====================================================================
-- 14. reddit_qualitative_evidence (942행, C급, private) — Reddit 정성 근거 (Track1+2)
-- Reddit 원본(유저네임 포함)이라 public 레포에는 안 올리고 DB에만 보관한다.
-- relevance_status는 사람이 나중에 이 테이블에서 직접 갱신한다(아직 대부분 "미검토").
-- =====================================================================
create table if not exists reddit_qualitative_evidence (
    post_id                          text primary key,
    barrier_category                 text,
    matched_query                    text,
    subreddit                        text,
    permalink                        text,
    author                           text,
    created_utc                      bigint,
    title                            text,
    selftext                         text,
    nationality_mentions_guess       text,
    relevance_status                 text default '미검토',
    all_matched_barrier_categories   text,
    ai_relevance_suggestion          text,
    ai_relevance_reason              text,
    population_type                  text,
    business_theme                   text,
    business_theme_reason            text,
    embedding                        vector(1536)
);
alter table reddit_qualitative_evidence enable row level security;

-- 챗봇이 질문 임베딩과의 코사인 유사도로 관련 게시물을 그때그때 찾아오기 위한 인덱스.
-- title+business_theme_reason 기준으로 생성(data/scripts/generate_reddit_embeddings.py 참고).
create index if not exists reddit_qualitative_evidence_embedding_idx
    on reddit_qualitative_evidence using hnsw (embedding vector_cosine_ops);

-- =====================================================================
-- 15. potential_tourist_2025_survey (39,667행, C급) — 2025 잠재방한여행객조사
-- 출처: data/processed/dashboard_data_dictionary.md 15절 (2026-08-26 추가)
-- 주의: 26개국 대상. country_profile_base(23개국)와 다른 리스트라 FK 걸지 않음.
-- =====================================================================
create table if not exists potential_tourist_2025_survey (
    id           bigint generated always as identity primary key,
    survey       text not null,
    page         int,
    topic        text not null,
    base_desc    text,
    "group"      text not null,
    segment      text not null,
    sample_n     double precision,
    item         text not null,
    value        double precision not null
);

create index if not exists idx_2025survey_segment on potential_tourist_2025_survey (segment);
create index if not exists idx_2025survey_topic on potential_tourist_2025_survey (topic);
alter table potential_tourist_2025_survey enable row level security;
