"""
자동 이상치 탐지.

verify_sample.py 의 검증 로직(소수점 누락 등 패턴 탐지)을 일반화해서,
30개국 전체 추출 결과에 자동으로 적용한다. 문제를 발견하면 값을 고치지 않고
verification_status 를 manual_review 로 바꾸고 notes 에 사유를 남긴다.
"""
from __future__ import annotations

VALID_RANGES = {
    "%": (0.0, 100.0),
    "score(1-5)": (1.0, 5.0),
    "회": (0.0, 30.0),  # 참고용 상한 (극단값 탐지 목적, 이론적 상한 아님)
}


def check_row(row: dict) -> tuple[str, list[str]]:
    """row: {value, unit, base, ...}. (verification_status, notes 리스트) 반환.
    이미 manual_review 인 경우도 이유를 유지한 채 추가 사유가 있으면 덧붙인다."""
    notes = []
    status = row.get("verification_status", "auto_extracted")

    value = row.get("value")
    unit = row.get("unit")
    base = row.get("base")

    if value is None:
        notes.append("값 없음(OCR에서 못 찾음)")
        return "manual_review", notes

    rng = VALID_RANGES.get(unit)
    if rng:
        lo, hi = rng
        if not (lo <= value <= hi):
            notes.append(f"값 범위 이상: {value} (기대범위 {lo}~{hi}, 단위={unit}) — "
                         f"소수점 누락(예: 3.3->33) 또는 자릿수 오류 의심")
            status = "manual_review"

    # score 인데 정수로 끝나는 값이 5 초과인 경우: 소수점 완전 누락 의심 (예: 33 -> 3.3)
    if unit == "score(1-5)" and value is not None and value > 5:
        notes.append(f"5점 척도인데 {value} > 5 — 소수점 누락 의심")
        status = "manual_review"

    if unit == "%" and value is not None and value > 100:
        notes.append(f"%인데 {value} > 100 — 소수점 누락 또는 자릿수 오류 의심")
        status = "manual_review"

    # 평균 방문횟수(회)가 %스럽게 큰 경우(예: 53.3이 134로 나오는 등) 상한 초과 시 의심
    if unit == "회" and value is not None and value > 10:
        notes.append(f"평균 횟수치고 과도하게 큼: {value}회 — 자릿수 오류 의심")
        status = "manual_review"

    if base is None:
        notes.append("BASE 누락")
        status = "manual_review"
    elif base <= 0:
        notes.append(f"BASE 값 이상: {base}")
        status = "manual_review"

    return status, notes


def check_duplicates(all_rows: list[dict]) -> list[dict]:
    """같은 (country, table_id, item, content_category)에 값이 두 번 이상 들어간 경우 탐지."""
    from collections import defaultdict
    seen = defaultdict(list)
    for r in all_rows:
        key = (r["country"], r["table_id"], r.get("item"), r.get("category"))
        seen[key].append(r)
    dup_notes = []
    for key, rows in seen.items():
        if len(rows) > 1:
            dup_notes.append({"key": key, "count": len(rows)})
    return dup_notes


def check_base_consistency(all_rows: list[dict]) -> list[dict]:
    """같은 국가 내에서 표1-33/1-35/1-41 은 모두 '전체 응답자' 기준 BASE 를 쓰므로
    (표1-16은 콘텐츠 경험자 기준이라 다를 수 있어 제외) 세 표 간 BASE가 다르면 표시만 한다."""
    from collections import defaultdict
    by_country = defaultdict(dict)
    for r in all_rows:
        if r["table_id"] in ("1-33", "1-35", "1-41") and r.get("base") is not None:
            by_country[r["country"]].setdefault(r["table_id"], set()).add(r["base"])

    mismatches = []
    for country, table_bases in by_country.items():
        all_bases = set()
        for t, bases in table_bases.items():
            all_bases |= bases
        if len(all_bases) > 1:
            mismatches.append({"country": country, "table_bases": {k: list(v) for k, v in table_bases.items()}})
    return mismatches
