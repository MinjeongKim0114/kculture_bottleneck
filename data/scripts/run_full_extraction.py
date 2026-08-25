"""
30개국 x 4개 핵심표(1-16, 1-33, 1-35, 1-41) 원수치 전체 추출.

- 페이지 매핑은 기존 country_table_page_map.csv 를 그대로 조회한다 (재계산 없음).
- 이미 OCR한 페이지(중국/미국/베트남 샘플)는 캐시를 재사용하고, 나머지 27개국만 새로 OCR한다.
- 표 구조 전체를 복원하지 않고, targeted_extract.py 의 라벨 기반 타겟 추출만 사용한다.
- 값을 추정/보간하지 않는다. 못 찾으면 value=None, verification_status=manual_review.
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
    "16": ("호감도", te.extract_1_16),
    "33": ("관심도", te.extract_1_33),
    "35": ("인식변화", te.extract_1_35),
    "41": ("관광경험", te.extract_1_41),
}

ROW_GAP = 10.0  # 카테고리 라벨(세로 병합 셀)이 여러 데이터 행을 잘못 묶는 문제 수정 후 확정한 값


def main():
    page_map = load_page_map()

    all_value_rows = []
    manifest = []

    t_start = time.time()
    for country in COUNTRIES_30:
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
                row = {
                    "country": country,
                    "table_id": f"1-{table_index}",
                    "indicator": indicator,
                    "category": v.get("content_category"),
                    "item": v["item"],
                    "value": v["value"],
                    "unit": v["unit"],
                    "base": v["base"],
                    "source_page": ",".join(map(str, pages)),
                    "extraction_method": "easyocr+label_targeted_row_lookup",
                    "ocr_confidence": round(v["ocr_confidence"], 4) if v.get("ocr_confidence") is not None else None,
                    "verification_status": status,
                    "notes": "; ".join(notes) if notes else "",
                }
                all_value_rows.append(row)

            print(f"[{country} / 1-{table_index}] pages={pages} values={len(values)} "
                  f"issues={len(issues)} cache_hits={entry['cache_hits']}/{len(pages)} time={elapsed}s")
            manifest.append(entry)

    # 중복 / BASE 일관성 교차검증
    dup = ac.check_duplicates(all_value_rows)
    base_mismatch = ac.check_base_consistency(all_value_rows)

    total_elapsed = round(time.time() - t_start, 1)
    print(f"\n총 소요시간: {total_elapsed}초, 총 값 개수: {len(all_value_rows)}")
    print(f"중복 탐지: {len(dup)}건, BASE 불일치 국가: {len(base_mismatch)}건")

    # --- 저장 ---
    out_csv = os.path.join(EXTRACTED_DIR, "all_countries_key_values.csv")
    fieldnames = ["country", "table_id", "indicator", "category", "item", "value", "unit", "base",
                  "source_page", "extraction_method", "ocr_confidence", "verification_status", "notes"]
    with open(out_csv, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in all_value_rows:
            writer.writerow(r)
    print("saved:", out_csv)

    out_json = os.path.join(EXTRACTED_DIR, "all_countries_key_values.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(all_value_rows, f, ensure_ascii=False, indent=2)
    print("saved:", out_json)

    manual_review_rows = [r for r in all_value_rows if r["verification_status"] == "manual_review"]
    out_review = os.path.join(VERIFICATION_DIR, "manual_review_list.csv")
    with open(out_review, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in manual_review_rows:
            writer.writerow(r)
    print("saved:", out_review, f"({len(manual_review_rows)} rows)")

    manifest_path = os.path.join(EXTRACTED_DIR, "full_extraction_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump({
            "countries": COUNTRIES_30,
            "tables": list(TABLES.keys()),
            "total_elapsed_sec": total_elapsed,
            "total_values": len(all_value_rows),
            "manual_review_count": len(manual_review_rows),
            "duplicate_findings": dup,
            "base_mismatch_findings": base_mismatch,
            "per_country_table": manifest,
        }, f, ensure_ascii=False, indent=2)
    print("saved:", manifest_path)


if __name__ == "__main__":
    main()
