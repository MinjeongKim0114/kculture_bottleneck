"""
Reddit 정성 데이터 수집 (Arctic Shift API 사용).

목적: 8개 방문 장벽 중 "왜 그게 장벽인지"를 설문이 설명하지 못하는 3개 그룹
(제도/언어, 경제/물리적 접근성, 종교/문화환경)에 대해, 실제 여행자의 구체적인
경험/불만을 수집한다. 통계 목적이 아니라 챗봇이 인용할 수 있는 "구체적 사례"
확보가 목적이므로 대량 수집하지 않는다.

우선순위 선정 기준(사용자와 합의된 3가지 기준, 감으로 정하지 않음):
  1. 빈도 - country_bottleneck_profile.csv 기준 몇 개국에 해당 장벽이 Y로 플래그됐는지
  2. Reddit 서술 가능성 - "관심 부재"류는 애초에 글을 안 남기는 선택 편향이 커서 제외
  3. 기존/진행 중인 정량 데이터와의 중복 - 이미지 장벽은 1-37(호감 저해요인)과 겹칠
     가능성이 있어 제외

Arctic Shift API (https://github.com/ArthurHeitmann/arctic_shift/blob/master/api/README.md):
  - 인증 불필요, base URL: https://arctic-shift.photon-reddit.com
  - "No uptime or performance guarantees" 명시된 비공식 서비스 - 실패해도 재시도만
    하고 억지로 성공시키지 않는다.

이 스크립트는 "수집"만 한다. 국적 자기 언급 여부 판별, 관련성 검토는
`review_reddit_candidates.py`(별도, 사람이 눈으로 확인하는 단계)에서 처리한다.
이 단계에서 값을 추정하거나 지어내지 않는다 - API가 반환한 원본 그대로 저장한다.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

import pandas as pd
import requests

REPO_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = REPO_ROOT / "data" / "raw" / "reddit"
OUT_DIR = REPO_ROOT / "data" / "processed" / "qualitative"
BOTTLENECK_CSV = REPO_ROOT / "data" / "processed" / "country_bottleneck_profile.csv"

API_BASE = "https://arctic-shift.photon-reddit.com"
SEARCH_ENDPOINT = f"{API_BASE}/api/posts/search"

SUBREDDITS = ["korea", "KoreaTravel", "travel", "solotravel", "Living_in_Korea"]

# 채택된 3개 장벽 그룹과 검색 키워드 (barrier_pattern_analysis.csv의 컬럼명과 매핑)
BARRIER_KEYWORDS = {
    "institutional_language": {
        "flag_column": "institutional_language_barrier_flag",
        "queries": [
            "korea language barrier",
            "no english in korea",
            "korea visa rejected",
            "korea visa process difficult",
        ],
    },
    "economic_physical_access": {
        "flag_column": "economic_physical_access_barrier_flag",
        "queries": [
            "korea too expensive",
            "cost of traveling to korea",
            "flight to korea too long",
        ],
    },
    "religious_cultural_env": {
        "flag_column": "religious_cultural_env_barrier_flag",
        "queries": [
            "halal food korea",
            "muslim friendly korea travel",
            "prayer room korea",
        ],
    },
}

LIMIT_PER_QUERY = 50
AFTER_DATE = "2022-01-01"  # 최근 성향 반영 위해 최근 3~4년으로 제한
REQUEST_DELAY_SEC = 2.0  # 서버 부하를 주지 않기 위한 최소 간격 (문서에 명시된 동적 rate limit 대응)

NATIONALITY_PATTERN = re.compile(
    r"\bas an? ([a-z]+)\b|\bi'?m from ([a-z]+)\b|\bi am from ([a-z]+)\b",
    re.IGNORECASE,
)


def flagged_countries(flag_column: str) -> list[str]:
    """빈도 확인용 - 이 장벽이 Y로 플래그된 국가 목록 (참고용, 필터링에는 안 씀)."""
    df = pd.read_csv(BOTTLENECK_CSV, encoding="utf-8-sig")
    return df.loc[df[flag_column] == "Y", "country"].tolist()


def search_posts(query: str, subreddit: str, max_retries: int = 4) -> list[dict]:
    params = {
        "subreddit": subreddit,
        "query": query,
        "after": AFTER_DATE,
        "limit": LIMIT_PER_QUERY,
        "sort": "desc",
    }
    for attempt in range(max_retries):
        resp = requests.get(SEARCH_ENDPOINT, params=params, timeout=30)
        if resp.status_code == 429:
            reset = resp.headers.get("X-RateLimit-Reset") or resp.headers.get("X-RateLimit-Reset-At")
            wait = 10.0
            if reset:
                try:
                    wait = max(float(reset), 1.0)
                except ValueError:
                    pass
            print(f"  429 rate limited, waiting {wait}s (attempt {attempt+1}/{max_retries})")
            time.sleep(wait)
            continue

        if resp.status_code in (422, 500, 502, 503, 504):
            # 문서에 명시된 "No uptime or performance guarantees" - 실측 결과 같은 요청도
            # 재시도하면 성공하는 일시적 서버 불안정으로 확인됨. 값을 지어내지 않고 재시도만 한다.
            wait = 5.0 * (attempt + 1)
            print(f"  일시적 서버 에러({resp.status_code}), {wait}s 후 재시도 (attempt {attempt+1}/{max_retries})")
            time.sleep(wait)
            continue

        resp.raise_for_status()
        payload = resp.json()
        if payload.get("data") is None:
            # 문서에 명시된 "No uptime or performance guarantees" 상황 - 서버 과부하/타임아웃.
            # 값을 지어내지 않고 재시도만 한다.
            wait = 5.0 * (attempt + 1)
            print(f"  서버 에러 응답({payload.get('error')}), {wait}s 후 재시도 (attempt {attempt+1}/{max_retries})")
            time.sleep(wait)
            continue

        return payload["data"]

    print(f"  {max_retries}회 재시도 후에도 실패 - 이 조합은 건너뜀 (값을 지어내지 않음)")
    return []


def guess_nationality_mentions(text: str) -> list[str]:
    """텍스트 안에 자기 국적을 언급하는 패턴이 있는지 찾는다.

    확정이 아니라 사람이 검토할 후보를 추리는 용도. 값을 그대로 신뢰하지 않는다.
    """
    if not text:
        return []
    matches = NATIONALITY_PATTERN.findall(text.lower())
    found = set()
    for groups in matches:
        for g in groups:
            if g:
                found.add(g)
    return sorted(found)


def main():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("=== 참고: 장벽별 Y-플래그 국가 수 (빈도 확인용) ===")
    for barrier_key, info in BARRIER_KEYWORDS.items():
        countries = flagged_countries(info["flag_column"])
        print(f"{barrier_key}: {len(countries)}개국 - {', '.join(countries)}")
    print()

    combos = [
        (barrier_key, query, subreddit)
        for barrier_key, info in BARRIER_KEYWORDS.items()
        for query in info["queries"]
        for subreddit in SUBREDDITS
    ]

    for barrier_key, query, subreddit in combos:
        raw_path = RAW_DIR / f"{barrier_key}__{subreddit}__{query.replace(' ', '_')}.json"
        existing_posts: list[dict] = []
        if raw_path.exists():
            with open(raw_path, encoding="utf-8") as f:
                existing_posts = json.load(f)

        print(f"[{barrier_key}] query='{query}' subreddit=r/{subreddit}")
        try:
            new_posts = search_posts(query, subreddit)
        except requests.RequestException as e:
            print(f"  실패: {e} (기존 캐시 유지, 나중에 재실행하면 이 조합만 다시 시도됨)")
            time.sleep(REQUEST_DELAY_SEC)
            continue

        # 매 실행마다 API가 검색 시점 기준 상위 LIMIT_PER_QUERY건만 반환하므로, 그냥
        # 덮어쓰면 이전에 수집했지만 이번엔 순위 밖으로 밀린 오래된 글이 사라진다.
        # post_id 기준으로 기존 것과 합쳐서 계속 누적한다(주간 실행 전제).
        merged = {p["id"]: p for p in existing_posts if p.get("id")}
        added = 0
        for p in new_posts:
            if p.get("id") and p["id"] not in merged:
                added += 1
            if p.get("id"):
                merged[p["id"]] = p
        print(f"  신규 {added}건 추가 (누적 {len(merged)}건)")

        with open(raw_path, "w", encoding="utf-8") as f:
            json.dump(list(merged.values()), f, ensure_ascii=False, indent=2)
        time.sleep(REQUEST_DELAY_SEC)

    # CSV는 이번 실행 성공 여부와 무관하게, 지금까지 캐시된 모든 raw json에서 매번 새로
    # 재구성한다 - 네트워크 실패로 이번 실행이 일부만 성공해도 기존 데이터를 잃지 않는다.
    all_rows = []
    for raw_path in sorted(RAW_DIR.glob("*.json")):
        barrier_key, subreddit, query_slug = raw_path.stem.split("__", 2)
        query = query_slug.replace("_", " ")
        with open(raw_path, encoding="utf-8") as f:
            posts = json.load(f)

        for p in posts:
            title = p.get("title") or ""
            selftext = p.get("selftext") or ""
            nationality_hits = guess_nationality_mentions(f"{title} {selftext}")
            all_rows.append({
                "barrier_category": barrier_key,
                "matched_query": query,
                "subreddit": subreddit,
                "post_id": p.get("id"),
                "permalink": f"https://reddit.com{p.get('permalink', '')}" if p.get("permalink") else None,
                "author": p.get("author"),
                "created_utc": p.get("created_utc"),
                "title": title,
                "selftext": selftext[:2000],  # 과도하게 긴 본문은 잘라서 저장 (원본은 raw json에 보존)
                "nationality_mentions_guess": ";".join(nationality_hits) if nationality_hits else "",
                "relevance_status": "미검토",  # 사람이 검토 후 채워야 함 - 임의로 판정하지 않음
            })

    out_csv = OUT_DIR / "reddit_candidates.csv"
    df = pd.DataFrame(all_rows)
    df.to_csv(out_csv, index=False, encoding="utf-8-sig")
    print(f"\n총 {len(df)}건 수집, 저장: {out_csv}")
    print("다음 단계: 사람이 relevance_status를 직접 채우고, nationality_mentions_guess를 검증해야 함 (자동 확정 아님)")


if __name__ == "__main__":
    main()
