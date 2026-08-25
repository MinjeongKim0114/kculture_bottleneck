"""
샘플 원수치 추출 실행 스크립트.

대상: 중국 / 미국 / 베트남 x [1-16 호감도, 1-33 관심도, 1-35 인식변화, 1-41 관광경험]
목적: 30개국 전체 자동 추출에 앞서, 이 방식(EasyOCR + bbox 그리드 복원)의
      신뢰도를 12개 국가-표 조합에 대해 먼저 검증한다.

이 스크립트는 country_table_page_map.csv 를 그대로 재활용하며,
페이지 매핑을 다시 계산하지 않는다.
"""
from __future__ import annotations

import json
import os
import time

from pdf_table_extractor import (
    load_page_map, get_pages, render_page, save_page_image,
    ocr_image, save_ocr_raw, reconstruct_grid, save_extracted,
    EXTRACTED_DIR,
)

SAMPLE_COUNTRIES = ["중국", "미국", "베트남"]
SAMPLE_TABLES = ["16", "33", "35", "41"]


def main():
    page_map = load_page_map()
    manifest = []

    for country in SAMPLE_COUNTRIES:
        for table_index in SAMPLE_TABLES:
            pages = get_pages(page_map, country, table_index)
            print(f"[{country} / 표1-{table_index}] pages={pages}")

            page_results = []
            for page_num in pages:
                t0 = time.time()
                img = render_page(page_num, dpi=200)
                img_path = save_page_image(img, country, table_index, page_num)

                boxes = ocr_image(img)
                raw_path = save_ocr_raw(boxes, country, table_index, page_num)

                grid = reconstruct_grid(boxes)
                extracted_path = save_extracted(
                    grid, country, table_index, page_num,
                    extra={"source_pdf": "data/raw/2026 한류실태조사_통계.pdf",
                           "page_image": os.path.relpath(img_path),
                           "ocr_raw_file": os.path.relpath(raw_path)},
                )
                elapsed = round(time.time() - t0, 2)
                print(f"  page {page_num}: boxes={len(boxes)} status={grid['status']} "
                      f"cols={grid['n_cols_detected']} time={elapsed}s")

                page_results.append({
                    "page": page_num,
                    "image": os.path.relpath(img_path),
                    "ocr_raw": os.path.relpath(raw_path),
                    "extracted": os.path.relpath(extracted_path),
                    "status": grid["status"],
                    "n_boxes": len(boxes),
                    "elapsed_sec": elapsed,
                })

            manifest.append({
                "country": country,
                "table_id": f"1-{table_index}",
                "pages": pages,
                "page_results": page_results,
            })

    manifest_path = os.path.join(EXTRACTED_DIR, "sample_extraction_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"\nmanifest saved: {manifest_path}")


if __name__ == "__main__":
    main()
