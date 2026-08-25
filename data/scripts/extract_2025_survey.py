"""
2025 잠재방한여행객조사 집계표 추출 (pymupdf 표 인식 사용, OCR 아님).

이 PDF는 텍스트 PDF라서 렌더링/OCR 없이 pymupdf의 find_tables()로 바로 표를
인식한다. 2026년 한류실태조사(OCR 파이프라인)와는 완전히 다른, 훨씬 신뢰도
높은 방식이다.

포함/제외 페이지는 사용자와 합의한 기준(핵심 질문 - 국가별 인식/행동 Gap과
사업기회 발굴 - 과 직결되는가)에 따라 INCLUDE_PAGES에 명시한다. 목차 전체를
훑어서 결정한 것이며, 제외된 페이지(아시아 13개국 경쟁국 비교, 일반 해외여행
의향, 여권발급 등)는 data/scripts/README.md에 사유를 기록한다.

표 구조가 예상과 다르면 값을 추정하지 않고 raw 그리드를 그대로 보존하며
verification_status로 표시한다.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pymupdf

REPO_ROOT = Path(__file__).resolve().parents[2]
PDF_PATH = REPO_ROOT / "data" / "raw" / "2025_잠재방한여행객조사_분석.pdf"
RAW_DIR = REPO_ROOT / "data" / "raw" / "2025_survey_tables"
OUT_CSV = REPO_ROOT / "data" / "processed" / "extracted" / "potential_tourist_2025_key_values.csv"
OUT_MANIFEST = REPO_ROOT / "data" / "processed" / "extracted" / "potential_tourist_2025_manifest.json"

# (시작페이지, 끝페이지, 조사대상) - 끝페이지 포함. 목차 분석 결과 합의된 포함 범위.
INCLUDE_RANGES = [
    (229, 229, "일반외국인"),
    (240, 243, "일반외국인"),
    (245, 248, "일반외국인"),
    (249, 261, "일반외국인"),   # 한국여행 비의향/미결정 이유 + 8개 장벽 세그먼트
    (262, 287, "일반외국인"),   # 도시/지역 인지·방문의향
    (288, 305, "일반외국인"),   # 한국문화 경험률/이용빈도/선호/영향력
    (306, 309, "일반외국인"),   # 비자/K-ETA
    (311, 311, "일반외국인"),   # 음식 민감도
    (314, 337, "방한의향자"),   # 관심계기~희망여행형태~지출~숙박~쇼핑~결제~스마트폰
    (339, 359, "방한의향자"),   # 참여희망활동 세분류(의료관광/한류콘텐츠체험 등)
    (360, 361, "방한의향자"),   # 희망교통수단
]

TOPIC_RE = re.compile(r"^\d+\.\s")


def include_pages() -> list[tuple[int, str]]:
    pages = []
    for start, end, survey in INCLUDE_RANGES:
        for p in range(start, end + 1):
            pages.append((p, survey))
    return pages


def find_topic_and_base(page: "pymupdf.Page") -> tuple[str, str]:
    """페이지 텍스트에서 'N. 제목' 라인과 '(...base..., 단위: ...)' 라인을 찾는다."""
    lines = [l.strip() for l in page.get_text().split("\n") if l.strip()]
    topic = ""
    base_desc = ""
    for line in lines:
        if TOPIC_RE.match(line) and len(line) < 80 and not topic:
            topic = line
        if line.startswith("(") and ("base" in line or "단위" in line) and not base_desc:
            base_desc = line
    return topic, base_desc


def clean_group_label(text: str | None) -> str | None:
    if text is None:
        return None
    return text.replace("\n", "").strip() or None


def parse_sample_n(text: str | None):
    if not text:
        return None
    m = re.search(r"([\d,]+)", text)
    return int(m.group(1).replace(",", "")) if m else None


def is_numeric(text: str | None) -> bool:
    if text is None:
        return False
    return bool(re.fullmatch(r"-?\d+\.?\d*", text.strip()))


def extract_page(page_num: int, survey: str) -> tuple[list[dict], list[str]]:
    issues = []
    doc_page = DOC[page_num - 1]
    topic, base_desc = find_topic_and_base(doc_page)
    tabs = doc_page.find_tables()
    if not tabs.tables:
        issues.append("표를 찾지 못함")
        return [], issues
    if len(tabs.tables) > 1:
        issues.append(f"표가 {len(tabs.tables)}개 발견됨 - 첫 번째만 사용, 나머지 확인 필요")

    grid = tabs.tables[0].extract()

    with open(RAW_DIR / f"p{page_num}_raw.json", "w", encoding="utf-8") as f:
        json.dump({"topic": topic, "base_desc": base_desc, "grid": grid}, f, ensure_ascii=False, indent=2)

    data_start = None
    for i, row in enumerate(grid):
        if row and row[0] and clean_group_label(row[0]) == "전체":
            data_start = i
            break
    if data_start is None:
        issues.append("'전체' 행을 찾지 못해 헤더/데이터 경계 불명")
        return [], issues

    header_rows = grid[:data_start]
    n_cols = len(grid[0]) if grid else 0
    col_labels = []
    for c in range(n_cols):
        parts = []
        for hr in header_rows:
            if c < len(hr) and hr[c]:
                cleaned = hr[c].replace("\n", " ").strip()
                if cleaned and (not parts or parts[-1] != cleaned):
                    parts.append(cleaned)
        col_labels.append(" - ".join(parts))

    # 사례수 컬럼(세그먼트마다 값이 바뀌는 표본수) 위치 찾기
    samplen_cols = {c for c in range(n_cols) if col_labels[c] == "사례수"}

    rows = []
    current_group = None
    for row in grid[data_start:]:
        if not row:
            continue
        g = clean_group_label(row[0])
        seg = clean_group_label(row[1]) if len(row) > 1 else None
        if g:
            current_group = g if seg else None
            group = g
            segment = seg if seg else g
        else:
            group = current_group
            segment = seg
        if segment is None:
            issues.append(f"세그먼트 라벨을 찾지 못한 행: {row}")
            continue

        # 이 행에서 적용할 사례수: 바로 왼쪽에 있는 사례수 컬럼 값 사용(블록마다 다를 수 있음)
        nearest_samplen = None
        for c in range(2, n_cols):
            if c in samplen_cols and c < len(row):
                nearest_samplen = parse_sample_n(row[c])
            if c < len(row) and row[c] is not None and c not in samplen_cols and is_numeric(row[c]):
                rows.append({
                    "survey": survey,
                    "page": page_num,
                    "topic": topic,
                    "base_desc": base_desc,
                    "group": group,
                    "segment": segment,
                    "sample_n": nearest_samplen,
                    "item": col_labels[c] if c < len(col_labels) else f"col{c}",
                    "value": float(row[c]),
                })
    return rows, issues


PLATFORM_RANK_PAGES = {319, 320}  # 국가별 SNS/OTA 플랫폼 Top5 랭킹 - 일반 표와 형태가 달라 별도 처리


def extract_platform_rank_page(page_num: int, survey: str) -> tuple[list[dict], list[str]]:
    issues = []
    doc_page = DOC[page_num - 1]
    topic, base_desc = find_topic_and_base(doc_page)
    tabs = doc_page.find_tables()
    if not tabs.tables:
        issues.append("표를 찾지 못함")
        return [], issues
    grid = tabs.tables[0].extract()

    with open(RAW_DIR / f"p{page_num}_raw.json", "w", encoding="utf-8") as f:
        json.dump({"topic": topic, "base_desc": base_desc, "grid": grid}, f, ensure_ascii=False, indent=2)

    header = grid[0]  # ['거주국별','1위','2위','3위','4위','5위']
    rows = []
    cell_re = re.compile(r"^(.+?)\n\((?:각\s*)?([\d.]+)\)$")
    for row in grid[1:]:
        if not row or not row[0]:
            continue
        country = clean_group_label(row[0])
        for c in range(1, len(row)):
            cell = row[c]
            if not cell:
                continue
            m = cell_re.match(cell.strip())
            if not m:
                issues.append(f"'{country}' {header[c]} 셀 파싱 실패: {cell!r}")
                continue
            platforms, pct = m.group(1).strip(), float(m.group(2))
            # "A/B (각 14.6)"처럼 동점인 경우, 두 플랫폼 다 같은 값으로 기록한다
            # (지어낸 값이 아니라 원문이 "각각 동일하다"고 명시한 값 그대로임)
            for platform in [p.strip() for p in platforms.split("/")]:
                rows.append({
                    "survey": survey, "page": page_num, "topic": topic, "base_desc": base_desc,
                    "group": "거주국별", "segment": country, "sample_n": None,
                    "item": f"{header[c]} - {platform}", "value": pct,
                })
    return rows, issues


def main():
    global DOC
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    DOC = pymupdf.open(PDF_PATH)

    all_rows = []
    manifest = []
    for page_num, survey in include_pages():
        if page_num in PLATFORM_RANK_PAGES:
            rows, issues = extract_platform_rank_page(page_num, survey)
        else:
            rows, issues = extract_page(page_num, survey)
        all_rows.extend(rows)
        manifest.append({
            "page": page_num, "survey": survey, "n_values": len(rows),
            "issues": issues,
        })
        status = "OK" if not issues else "ISSUE"
        print(f"[p{page_num}] {survey} values={len(rows)} {status} {issues if issues else ''}")

    with open(OUT_MANIFEST, "w", encoding="utf-8") as f:
        json.dump({"total_values": len(all_rows), "pages": manifest}, f, ensure_ascii=False, indent=2)

    import csv
    fieldnames = ["survey", "page", "topic", "base_desc", "group", "segment", "sample_n", "item", "value"]
    with open(OUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in all_rows:
            writer.writerow(r)

    print(f"\n총 {len(all_rows)}건, 저장: {OUT_CSV}")
    n_issue_pages = sum(1 for m in manifest if m["issues"])
    print(f"이슈 있는 페이지: {n_issue_pages}/{len(manifest)}")


if __name__ == "__main__":
    main()
