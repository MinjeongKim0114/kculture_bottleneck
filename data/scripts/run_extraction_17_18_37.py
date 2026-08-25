"""
30개국 x 3개 표(1-17 호감요인, 1-18 호감 저해요인, 1-37 한류 부정적 인식 공감 이유)
원수치 전체 추출.

run_full_extraction.py(1-16/33/35/41)와 동일한 구조를 따르되, 산출물은 별도 파일
(tables_17_18_37_key_values.csv/.json)로 저장한다 — 기존 all_countries_key_values.csv는
덮어쓰지 않는다.

- 페이지 매핑은 기존 country_table_page_map.csv 를 그대로 조회한다 (재계산 없음).
- 이미 OCR한 페이지(표본국가 등)는 캐시를 재사용하고, 나머지는 새로 OCR한다.
- 표 구조 전체를 복원하지 않고, targeted_extract.py 의 라벨 기반 타겟 추출만 사용한다.
- 값을 추정/보간하지 않는다. 못 찾으면 value=None, verification_status=manual_review.
- 1-17/1-18은 항목(이유) 텍스트가 국가별로 다른 순서로 나타나는 자유 텍스트라
  1-16과 달리 "몇 개 값이 나와야 한다"는 고정 개수를 기대하지 않는다(카테고리별
  보기 항목 개수 자체가 표에 인쇄된 그대로이며, 다만 12개 콘텐츠 카테고리 블록
  개수만 고정 기대값으로 검증한다).
"""
from __future__ import annotations

import csv
import json
import os
import time

from pdf_table_extractor import (
    load_page_map, get_pages, get_ocr_for_page, cluster_rows, combine_multipage_boxes,
    EXTRACTED_DIR, VERIFICATION_DIR,
)
import targeted_extract as te
import anomaly_checks as ac

COUNTRIES_30 = [
    "중국", "일본", "대만", "태국", "말레이시아", "인도네시아", "인도", "베트남", "카자흐스탄",
    "필리핀", "싱가포르", "호주", "미국", "캐나다", "멕시코", "브라질", "아르헨티나", "칠레",
    "영국", "프랑스", "이탈리아", "스페인", "독일", "러시아", "튀르키예", "폴란드", "UAE",
    "사우디아라비아", "남아프리카공화국", "이집트",
]

TABLES = {
    "17": ("호감요인", te.extract_1_17),
    "18": ("호감 저해요인", te.extract_1_18),
    "37": ("한류 부정적 인식 공감 이유", te.extract_1_37),
}

ROW_GAP = 10.0  # 1-16/33/35/41 과 동일값 (README에서 확정된 값, 세로 병합 카테고리 라벨 과병합 방지)

OUT_CSV = os.path.join(EXTRACTED_DIR, "tables_17_18_37_key_values.csv")
OUT_JSON = os.path.join(EXTRACTED_DIR, "tables_17_18_37_key_values.json")
OUT_REVIEW = os.path.join(VERIFICATION_DIR, "manual_review_list_17_18_37.csv")
OUT_MANIFEST = os.path.join(EXTRACTED_DIR, "extraction_manifest_17_18_37.json")

FIELDNAMES = ["country", "table_id", "indicator", "content_category", "item", "rank_group",
              "value", "unit", "base", "source_page", "extraction_method", "ocr_confidence",
              "verification_status", "notes"]


def _load_existing():
    """이전 실행이 중간에 끊겼을 때 재사용할 기존 산출물을 불러온다.

    국가 단위로 재개한다: manifest에 이미 기록된 국가는 3개 표 모두 처리가
    끝난 것으로 보고 건너뛴다 (한 국가 처리 후에만 저장하므로 안전).
    """
    if not (os.path.exists(OUT_CSV) and os.path.exists(OUT_MANIFEST)):
        return [], [], set()
    with open(OUT_MANIFEST, encoding="utf-8") as f:
        old_manifest_data = json.load(f)
    manifest = old_manifest_data.get("per_country_table", [])
    done_countries = {m["country"] for m in manifest}
    with open(OUT_CSV, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        all_value_rows = [
            {k: (None if v == "" else v) for k, v in row.items()} for row in reader
        ]
    print(f"이전 산출물 발견: {len(done_countries)}개국 이미 완료됨, 이어서 진행")
    return all_value_rows, manifest, done_countries


def _save_progress(all_value_rows, manifest, elapsed_so_far):
    """국가 하나 끝날 때마다 호출 - 중간에 끊겨도 여기까지는 보존됨."""
    with open(OUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for r in all_value_rows:
            writer.writerow(r)

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(all_value_rows, f, ensure_ascii=False, indent=2)

    manual_review_rows = [r for r in all_value_rows if r["verification_status"] == "manual_review"]
    with open(OUT_REVIEW, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for r in manual_review_rows:
            writer.writerow(r)

    with open(OUT_MANIFEST, "w", encoding="utf-8") as f:
        json.dump({
            "countries": COUNTRIES_30,
            "tables": list(TABLES.keys()),
            "total_elapsed_sec": round(elapsed_so_far, 1),
            "total_values": len(all_value_rows),
            "manual_review_count": len(manual_review_rows),
            "per_country_table": manifest,
        }, f, ensure_ascii=False, indent=2)


def main():
    page_map = load_page_map()

    all_value_rows, manifest, done_countries = _load_existing()

    t_start = time.time()
    for country in COUNTRIES_30:
        if country in done_countries:
            print(f"[{country}] 이미 완료됨 (이전 실행), 건너뜀")
            continue

        country_rows_before = len(all_value_rows)
        for table_index, (indicator, extractor) in TABLES.items():
            pages = get_pages(page_map, country, table_index)
            entry = {"country": country, "table_id": f"1-{table_index}", "indicator": indicator,
                     "pages": pages, "status": None, "n_values": 0, "n_issues": 0,
                     "cache_hits": 0, "elapsed_sec": 0.0}

            if not pages:
                entry["status"] = "NOT_FOUND_IN_PAGE_MAP"
                manifest.append(entry)
                print(f"[{country} / 1-{table_index}] NOT_FOUND_IN_PAGE_MAP")
                continue

            t0 = time.time()
            pages_boxes = []
            for p in pages:
                boxes, from_cache = get_ocr_for_page(country, table_index, p, dpi=200)
                pages_boxes.append(boxes)
                if from_cache:
                    entry["cache_hits"] += 1

            combined = combine_multipage_boxes(pages_boxes)
            rows = cluster_rows(combined, row_gap=ROW_GAP)

            values, issues = extractor(rows)
            elapsed = round(time.time() - t0, 2)
            entry["elapsed_sec"] = elapsed
            entry["n_values"] = len(values)
            entry["n_issues"] = len(issues)
            entry["extraction_issues"] = issues
            entry["status"] = "ok" if not issues else "extracted_with_issues"

            for v in values:
                status, notes = ac.check_row(v)
                # 이미 targeted_extract 단계에서 manual_review로 표시된 값(순위 불명 등)은
                # anomaly_checks가 "auto_extracted"로 되돌리지 않도록 유지한다.
                if v.get("verification_status") == "manual_review":
                    status = "manual_review"
                    notes = notes or []
                    if v.get("rank_group", "").startswith("순위미상"):
                        notes = [f"순위 불명({v['rank_group']})"] + notes
                row = {
                    "country": country,
                    "table_id": f"1-{table_index}",
                    "indicator": indicator,
                    "content_category": v.get("content_category"),
                    "item": v["item"],
                    "rank_group": v.get("rank_group"),
                    "value": v["value"],
                    "unit": v["unit"],
                    "base": v["base"],
                    "source_page": ",".join(map(str, pages)),
                    "extraction_method": "easyocr+ranked_item_row_grouping",
                    "ocr_confidence": round(v["ocr_confidence"], 4) if v.get("ocr_confidence") is not None else None,
                    "verification_status": status,
                    "notes": "; ".join(notes) if notes else "",
                }
                all_value_rows.append(row)

            print(f"[{country} / 1-{table_index}] pages={pages} values={len(values)} "
                  f"issues={len(issues)} cache_hits={entry['cache_hits']}/{len(pages)} time={elapsed}s")
            manifest.append(entry)

        # 국가 하나(3개 표)가 끝날 때마다 즉시 저장한다 - 여기서 끊겨도
        # 재실행하면 done_countries로 건너뛰고 이어서 진행된다.
        _save_progress(all_value_rows, manifest, time.time() - t_start)
        print(f"[{country}] 완료, 지금까지 총 {len(all_value_rows)}건 저장됨 "
              f"(신규 {len(all_value_rows) - country_rows_before}건)")

    dup = ac.check_duplicates([
        {**r, "item": f"{r['item']}__{r.get('rank_group')}"} for r in all_value_rows
    ])
    total_elapsed = round(time.time() - t_start, 1)
    _save_progress(all_value_rows, manifest, total_elapsed)

    print(f"\n총 소요시간(이번 실행): {total_elapsed}초, 총 값 개수: {len(all_value_rows)}")
    print(f"중복 탐지: {len(dup)}건")
    print("saved:", OUT_CSV, OUT_JSON, OUT_REVIEW, OUT_MANIFEST)


if __name__ == "__main__":
    main()
