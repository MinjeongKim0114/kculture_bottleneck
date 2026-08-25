"""
샘플 원수치 데이터 파일 생성.

verify_sample.py 에서 사람이 원본 이미지와 대조해 확인한 값들 중,
verification_status 가 exact_match 또는 found_as_substring(괄호 등 서식 차이일 뿐
값 자체는 일치)인 항목만 골라 요청된 스키마로 저장한다.

이 파일에 들어가는 모든 값은:
  1) 사람이 PDF 렌더링 이미지를 직접 읽어 확인했고,
  2) 동일 값이 OCR raw 결과에서도 발견되어 교차 검증된 값이다.
추정/보간된 값은 없다.
"""
import csv
import os

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT_PATH = os.path.join(BASE, "data", "processed", "extracted", "sample_key_values.csv")

# (country, table_id, page, category, item, value, unit, base, notes)
ROWS = [
    # --- 호감도 (표1-16, 전반적 만족도 블록) ---
    ("중국", "1-16", 82, "호감도", "전반적 만족도 - 5점 척도 평균(전체)", 3.78, "score(1-5)", 2100, "콘텐츠 경험자 기준 BASE"),
    ("미국", "1-16", 802, "호감도", "전반적 만족도 - 5점 척도 평균(전체)", 3.96, "score(1-5)", 1300, "콘텐츠 경험자 기준 BASE"),
    ("베트남", "1-16", 502, "호감도", "전반적 만족도 - 5점 척도 평균(전체)", 3.99, "score(1-5)", 900, "콘텐츠 경험자 기준 BASE"),
    # --- 관심도 (표1-33, 본인 관심도 변화 1년전대비 블록) ---
    ("중국", "1-33", 116, "관심도", "본인 관심도 변화(1년전대비) - 5점 척도 평균(전체)", 3.36, "score(1-5)", 2100, "BASE=전체 응답자"),
    ("미국", "1-33", 836, "관심도", "본인 관심도 변화(1년전대비) - 5점 척도 평균(전체)", 3.70, "score(1-5)", 1300, "BASE=전체 응답자"),
    ("베트남", "1-33", 536, "관심도", "본인 관심도 변화(1년전대비) - 5점 척도 평균(전체)", 3.69, "score(1-5)", 900, "BASE=전체 응답자"),
    # --- 인식 변화 (표1-35) ---
    ("중국", "1-35", 118, "인식변화", "5점 척도 평균(전체)", 3.56, "score(1-5)", 2100, "BASE=전체 응답자"),
    ("중국", "1-35", 118, "인식변화", "① 매우 부정적으로 변함(%, 전체)", 1.6, "%", 2100, ""),
    ("중국", "1-35", 118, "인식변화", "④ 약간 긍정적으로 변함(%, 전체)", 41.6, "%", 2100, ""),
    ("미국", "1-35", 838, "인식변화", "5점 척도 평균(전체)", 3.92, "score(1-5)", 1300, "BASE=전체 응답자"),
    ("미국", "1-35", 838, "인식변화", "③ 변화 없음(%, 전체)", 28.2, "%", 1300, ""),
    ("베트남", "1-35", 538, "인식변화", "5점 척도 평균(전체)", 4.02, "score(1-5)", 900, "BASE=전체 응답자"),
    ("베트남", "1-35", 538, "인식변화", "⑤ 매우 긍정적으로 변함(%, 전체)", 29.3, "%", 900, ""),
    # --- 관광 경험 (표1-41, "한국 관광" 행) ---
    ("중국", "1-41", 121, "관광경험", "한국 관광 - 구매(방문) 경험률(%, 전체)", 62.2, "%", 2100, "최근 4년간 기준"),
    ("중국", "1-41", 121, "관광경험", "한국 관광 - 평균 구매(방문) 횟수(회, 전체)", 1.21, "회", 2100, "최근 4년간 기준"),
    ("미국", "1-41", 841, "관광경험", "한국 관광 - 구매(방문) 경험률(%, 전체)", 36.9, "%", 1300, "최근 4년간 기준"),
    ("미국", "1-41", 841, "관광경험", "한국 관광 - 평균 구매(방문) 횟수(회, 전체)", 1.38, "회", 1300, "최근 4년간 기준"),
    ("베트남", "1-41", 541, "관광경험", "한국 관광 - 구매(방문) 경험률(%, 전체)", 53.3, "%", 900, "최근 4년간 기준"),
    ("베트남", "1-41", 541, "관광경험", "한국 관광 - 평균 구매(방문) 횟수(회, 전체)", 1.34, "회", 900, "최근 4년간 기준"),
]


def main():
    fieldnames = ["country", "table_id", "page", "category", "item", "value", "unit",
                  "base", "source_page", "extraction_method", "verification_status", "notes"]
    with open(OUT_PATH, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for country, table_id, page, category, item, value, unit, base, notes in ROWS:
            writer.writerow({
                "country": country,
                "table_id": table_id,
                "page": page,
                "category": category,
                "item": item,
                "value": value,
                "unit": unit,
                "base": base,
                "source_page": page,
                "extraction_method": "manual_read_verified_by_ocr_crosscheck",
                "verification_status": "verified",
                "notes": notes,
            })
    print("saved:", OUT_PATH, f"({len(ROWS)} rows)")


if __name__ == "__main__":
    main()
