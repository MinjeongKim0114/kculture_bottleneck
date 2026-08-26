"""
reddit_qualitative_evidence의 각 행(942건)에 임베딩을 생성해 저장한다.

목적: chat_service.py가 더 이상 고정된 THEME_CLUSTERS로 사전 분류된 몇 건만
주입하지 않고, 질문과 의미적으로 가까운 게시물을 그때그때 pgvector 유사도
검색으로 찾아 쓸 수 있게 한다.

임베딩 대상 텍스트: title + selftext 앞부분 + business_theme + business_theme_reason.
게시물 원문뿐 아니라 AI가 판단한 사업 테마/이유까지 포함해야, "할랄푸드 사업
기회 있어?" 같은 질문이 본문에 "할랄"이라는 단어가 없는 게시물도 찾을 수 있다.

재분류(classify_business_opportunity_themes.py)로 business_theme이 바뀔 때마다
이 스크립트도 다시 돌려야 한다 — population_type/business_theme이 바뀐 행만
다시 임베딩하지 않고, 매번 전체를 다시 계산한다(942건 규모라 비용/시간 부담 작음).
"""
from pathlib import Path

import psycopg
from openai import OpenAI
from pgvector.psycopg import register_vector
from psycopg.rows import dict_row

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ENV = REPO_ROOT / "backend" / ".env"

EMBEDDING_MODEL = "text-embedding-3-small"
BATCH_SIZE = 100


def load_env() -> tuple[str, str]:
    db_url = None
    api_key = None
    for line in BACKEND_ENV.read_text(encoding="utf-8").splitlines():
        if line.startswith("DATABASE_URL="):
            db_url = line.split("=", 1)[1].strip()
        elif line.startswith("LLM_API_KEY="):
            api_key = line.split("=", 1)[1].strip()
    if not db_url or not api_key:
        raise RuntimeError("DATABASE_URL 또는 LLM_API_KEY 없음")
    return db_url, api_key


def build_text(row: dict) -> str:
    parts = [
        row.get("title") or "",
        (row.get("selftext") or "")[:800],
        row.get("business_theme") or "",
        row.get("business_theme_reason") or "",
    ]
    return "\n".join(p for p in parts if p)


def main():
    db_url, api_key = load_env()
    client = OpenAI(api_key=api_key)

    with psycopg.connect(db_url, row_factory=dict_row) as conn:
        register_vector(conn)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT post_id, title, selftext, business_theme, business_theme_reason "
                "FROM reddit_qualitative_evidence"
            )
            rows = cur.fetchall()
        print(f"임베딩 대상: {len(rows)}건")

        for start in range(0, len(rows), BATCH_SIZE):
            batch = rows[start:start + BATCH_SIZE]
            texts = [build_text(r) for r in batch]
            resp = client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
            with conn.cursor() as cur:
                for row, item in zip(batch, resp.data):
                    cur.execute(
                        "UPDATE reddit_qualitative_evidence SET embedding = %s WHERE post_id = %s",
                        (item.embedding, row["post_id"]),
                    )
            conn.commit()
            print(f"  {start + len(batch)}/{len(rows)} 완료")

    print("임베딩 저장 완료")


if __name__ == "__main__":
    main()
