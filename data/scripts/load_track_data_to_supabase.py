"""
1-17/18/37 정제 데이터 + Reddit Track1/2 데이터를 Supabase에 적재한다.

backend/db/schema.sql 13/14절에 정의된 테이블을 대상으로 한다. 이 스크립트는
스키마를 직접 실행(CREATE TABLE IF NOT EXISTS)하고 CSV를 그대로 넣는다 - 값을
가공하거나 새로 계산하지 않는다.

Reddit 원본은 유저네임을 포함하므로 public 레포에 올리지 않고 이 DB에만 저장한다.
"""
import sys
from pathlib import Path

import pandas as pd
import psycopg

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))
from app.core.config import DATABASE_URL  # noqa: E402

SCHEMA_SQL = REPO_ROOT / "backend" / "db" / "schema.sql"
CONTENT_REASONS_CSV = REPO_ROOT / "data" / "processed" / "extracted" / "tables_17_18_37_key_values_clean.csv"
REDDIT_CSV = REPO_ROOT / "data" / "processed" / "qualitative" / "reddit_candidates_business_classified.csv"
SURVEY_2025_CSV = REPO_ROOT / "data" / "processed" / "extracted" / "potential_tourist_2025_key_values.csv"


def ensure_schema(conn):
    sql = SCHEMA_SQL.read_text(encoding="utf-8")
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()
    print("스키마 확인/생성 완료")


def load_content_reasons(conn):
    df = pd.read_csv(CONTENT_REASONS_CSV, encoding="utf-8-sig")
    df = df.where(pd.notna(df), None)
    cols = ["country", "table_id", "indicator", "content_category", "item", "raw_item",
            "rank_group", "value", "unit", "base", "source_page", "extraction_method",
            "ocr_confidence", "verification_status", "notes", "label_confidence"]
    with conn.cursor() as cur:
        cur.execute("TRUNCATE content_liking_disliking_reasons RESTART IDENTITY")
        with cur.copy(
            f"COPY content_liking_disliking_reasons ({', '.join(cols)}) FROM STDIN"
        ) as copy:
            for row in df[cols].itertuples(index=False, name=None):
                copy.write_row(row)
    conn.commit()
    print(f"content_liking_disliking_reasons: {len(df)}행 적재")


def load_reddit_evidence(conn):
    df = pd.read_csv(REDDIT_CSV, encoding="utf-8-sig")
    df = df.where(pd.notna(df), None)
    cols = ["post_id", "barrier_category", "matched_query", "subreddit", "permalink",
            "author", "created_utc", "title", "selftext", "nationality_mentions_guess",
            "relevance_status", "all_matched_barrier_categories", "ai_relevance_suggestion",
            "ai_relevance_reason", "population_type", "business_theme", "business_theme_reason"]
    with conn.cursor() as cur:
        cur.execute("TRUNCATE reddit_qualitative_evidence")
        with cur.copy(
            f"COPY reddit_qualitative_evidence ({', '.join(cols)}) FROM STDIN"
        ) as copy:
            for row in df[cols].itertuples(index=False, name=None):
                copy.write_row(row)
    conn.commit()
    print(f"reddit_qualitative_evidence: {len(df)}행 적재")


def load_2025_survey(conn):
    df = pd.read_csv(SURVEY_2025_CSV, encoding="utf-8-sig")
    df = df.where(pd.notna(df), None)
    cols = ["survey", "page", "topic", "base_desc", "group", "segment", "sample_n", "item", "value"]
    with conn.cursor() as cur:
        cur.execute("TRUNCATE potential_tourist_2025_survey RESTART IDENTITY")
        with cur.copy(
            'COPY potential_tourist_2025_survey (survey, page, topic, base_desc, "group", '
            'segment, sample_n, item, value) FROM STDIN'
        ) as copy:
            for row in df[cols].itertuples(index=False, name=None):
                copy.write_row(row)
    conn.commit()
    print(f"potential_tourist_2025_survey: {len(df)}행 적재")


def main():
    with psycopg.connect(DATABASE_URL) as conn:
        ensure_schema(conn)
        load_content_reasons(conn)
        load_reddit_evidence(conn)
        load_2025_survey(conn)


if __name__ == "__main__":
    main()
