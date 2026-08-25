# -*- coding: utf-8 -*-
"""
한류실태조사 <-> 2025 잠재방한객조사 결합 가능성 구조 검증

목적:
  - 두 데이터셋의 국가 목록을 실제 값 기준으로 비교하여 국가 매핑 테이블을 생성한다.
  - Gap 계산, 순위 산출, 상관분석 등은 하지 않는다. 오직 국가 매핑만 기계적으로 생성한다.
  - 지표(변수) 매핑은 수작업 판단이 필요하므로 이 스크립트에서 생성하지 않고,
    data/processed/potential_hallyu_indicator_mapping.csv 는 별도로 수기 작성한다.

입력 (읽기 전용, 수정하지 않음):
  - data/processed/potential_tourist_country_mapping.csv
  - data/processed/extracted/all_countries_key_values.csv

출력:
  - data/processed/potential_hallyu_country_mapping.csv
"""

from __future__ import annotations

import csv
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

POTENTIAL_MAPPING_CSV = PROCESSED_DIR / "potential_tourist_country_mapping.csv"
HALLYU_KEY_VALUES_CSV = PROCESSED_DIR / "extracted" / "all_countries_key_values.csv"
OUT_CSV = PROCESSED_DIR / "potential_hallyu_country_mapping.csv"

# 표기가 다르지만 동일 국가로 확실히 판단 가능한 경우만 기록 (임의 추정 금지)
# 근거: 잠재방한객조사 원본 Excel 표기 '아랍에미리트' == 한류실태조사 원본 표기 'UAE'
#       (potential_tourist_country_mapping.csv 에서 이미 standard_name='UAE'로 매핑됨)
CONFIRMED_NAME_VARIATIONS = {
    "아랍에미리트": "UAE",
}


def load_potential_countries():
    with open(POTENTIAL_MAPPING_CSV, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    return rows  # [{'original_name_잠재방한객조사':..., 'standard_name':..., 'note':...}, ...]


def load_hallyu_countries():
    with open(HALLYU_KEY_VALUES_CSV, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    countries = sorted({r["country"] for r in rows})
    return countries


def main():
    potential_rows = load_potential_countries()
    hallyu_countries = load_hallyu_countries()
    hallyu_set = set(hallyu_countries)

    out_rows = []

    matched_hallyu = set()

    for row in potential_rows:
        original = row["original_name_잠재방한객조사"]
        standard = row["standard_name"]

        if standard in hallyu_set:
            hallyu_country = standard
            if original == standard:
                status = "EXACT_MATCH"
                note = ""
            else:
                status = "NAME_VARIATION"
                note = f"원표기 '{original}' -> 한류실태조사 표기 '{standard}'"
            matched_hallyu.add(hallyu_country)
        elif original in hallyu_set:
            hallyu_country = original
            status = "EXACT_MATCH"
            note = ""
            matched_hallyu.add(hallyu_country)
        else:
            hallyu_country = ""
            status = "POTENTIAL_ONLY"
            note = "한류실태조사 30개국 목록에 문자열 일치 국가 없음 (조사 대상국 자체가 다름)"

        out_rows.append(
            {
                "potential_tourist_country": original,
                "potential_standard_country": standard,
                "hallyu_country": hallyu_country,
                "match_status": status,
                "note": note,
            }
        )

    # 한류실태조사에만 존재하는 국가
    for hc in hallyu_countries:
        if hc not in matched_hallyu:
            out_rows.append(
                {
                    "potential_tourist_country": "",
                    "potential_standard_country": "",
                    "hallyu_country": hc,
                    "match_status": "HALLYU_ONLY",
                    "note": "잠재방한객조사 26개 거주국 목록에 없음 (조사 대상국 자체가 다름)",
                }
            )

    with open(OUT_CSV, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "potential_tourist_country",
                "potential_standard_country",
                "hallyu_country",
                "match_status",
                "note",
            ],
        )
        writer.writeheader()
        for row in out_rows:
            writer.writerow(row)

    print(f"[저장] {OUT_CSV} ({len(out_rows)}행)")
    from collections import Counter

    print(Counter(r["match_status"] for r in out_rows))


if __name__ == "__main__":
    main()
