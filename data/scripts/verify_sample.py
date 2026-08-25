"""
샘플 검증 스크립트.

이 스크립트는 "정답"을 자동으로 만들지 않는다 — 아래 GROUND_TRUTH 값은
사람이 PDF 렌더링 이미지를 직접 읽어서 (Read 도구로 원본 페이지를 열어 육안 확인)
기록한 값이다. 이 스크립트는 그 정답이 OCR raw 결과 안에 실제로 존재하는지,
그리고 흔한 OCR 오류 패턴(소수점 누락 등)이 있는지만 기계적으로 대조한다.

원칙: OCR 결과를 사실로 간주하지 않는다. 이 스크립트의 역할은 "일치/불일치"를
보고하는 것이지, 값을 보정하거나 추정하는 것이 아니다.
"""
from __future__ import annotations

import csv
import glob
import json
import os

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OCR_RAW_DIR = os.path.join(BASE, "data", "processed", "ocr_raw")
VERIFICATION_DIR = os.path.join(BASE, "data", "processed", "verification")

# 사람이 PDF 렌더링 이미지를 직접 읽어 확인한 정답값 (2026-08-25, Read 도구로 원본 대조)
# label: 표 안에서 어떤 값인지 설명 (사람이 이해할 수 있는 이름)
GROUND_TRUTH = [
    # 중국 (BASE 2,100)
    {"country": "중국", "table_id": "1-16", "page": 82, "label": "호감도-전반적만족도-전체-5점척도평균", "value": "3.78"},
    {"country": "중국", "table_id": "1-16", "page": 82, "label": "호감도-전반적만족도-BASE", "value": "2,100"},
    {"country": "중국", "table_id": "1-33", "page": 116, "label": "관심도-본인관심도변화(1년전대비)-전체-5점척도평균", "value": "3.36"},
    {"country": "중국", "table_id": "1-35", "page": 118, "label": "인식변화-전체-5점척도평균", "value": "3.56"},
    {"country": "중국", "table_id": "1-35", "page": 118, "label": "인식변화-①매우부정적-전체", "value": "1.6"},
    {"country": "중국", "table_id": "1-35", "page": 118, "label": "인식변화-④약간긍정적-전체", "value": "41.6"},
    {"country": "중국", "table_id": "1-41", "page": 121, "label": "관광경험-한국관광-구매경험률(%)", "value": "62.2"},
    {"country": "중국", "table_id": "1-41", "page": 121, "label": "관광경험-한국관광-평균구매횟수(회)", "value": "1.21"},
    # 미국 (BASE 1,300)
    {"country": "미국", "table_id": "1-16", "page": 802, "label": "호감도-전반적만족도-전체-5점척도평균", "value": "3.96"},
    {"country": "미국", "table_id": "1-16", "page": 802, "label": "호감도-전반적만족도-BASE", "value": "1,300"},
    {"country": "미국", "table_id": "1-33", "page": 836, "label": "관심도-본인관심도변화(1년전대비)-전체-5점척도평균", "value": "3.70"},
    {"country": "미국", "table_id": "1-35", "page": 838, "label": "인식변화-전체-5점척도평균", "value": "3.92"},
    {"country": "미국", "table_id": "1-35", "page": 838, "label": "인식변화-③변화없음-전체", "value": "28.2"},
    {"country": "미국", "table_id": "1-41", "page": 841, "label": "관광경험-한국관광-구매경험률(%)", "value": "36.9"},
    {"country": "미국", "table_id": "1-41", "page": 841, "label": "관광경험-한국관광-평균구매횟수(회)", "value": "1.38"},
    # 베트남 (BASE 900)
    {"country": "베트남", "table_id": "1-16", "page": 502, "label": "호감도-전반적만족도-전체-5점척도평균", "value": "3.99"},
    {"country": "베트남", "table_id": "1-16", "page": 502, "label": "호감도-전반적만족도-BASE", "value": "900"},
    {"country": "베트남", "table_id": "1-33", "page": 536, "label": "관심도-본인관심도변화(1년전대비)-전체-5점척도평균", "value": "3.69"},
    {"country": "베트남", "table_id": "1-35", "page": 538, "label": "인식변화-전체-5점척도평균", "value": "4.02"},
    {"country": "베트남", "table_id": "1-35", "page": 538, "label": "인식변화-⑤매우긍정적-전체", "value": "29.3"},
    {"country": "베트남", "table_id": "1-41", "page": 541, "label": "관광경험-한국관광-구매경험률(%)", "value": "53.3"},
    {"country": "베트남", "table_id": "1-41", "page": 541, "label": "관광경험-한국관광-평균구매횟수(회)", "value": "1.34"},
]

# 라벨(행 제목) 검증 — 숫자와 분리해서 별도로 신뢰도를 확인한다 (요청사항 5).
LABEL_GROUND_TRUTH = [
    {"country": "중국", "table_id": "1-41", "page": 121, "label_type": "row_label", "value": "한국 관광"},
    {"country": "미국", "table_id": "1-41", "page": 841, "label_type": "row_label", "value": "한국 관광"},
    {"country": "베트남", "table_id": "1-41", "page": 541, "label_type": "row_label", "value": "한국 관광"},
    {"country": "중국", "table_id": "1-16", "page": 82, "label_type": "row_group_label", "value": "만족도"},
    {"country": "미국", "table_id": "1-16", "page": 802, "label_type": "row_group_label", "value": "만족도"},
    {"country": "베트남", "table_id": "1-16", "page": 502, "label_type": "row_group_label", "value": "만족도"},
    {"country": "중국", "table_id": "1-35", "page": 118, "label_type": "column_label", "value": "변화 없음"},
    {"country": "미국", "table_id": "1-35", "page": 838, "label_type": "column_label", "value": "변화 없음"},
    {"country": "베트남", "table_id": "1-35", "page": 538, "label_type": "column_label", "value": "변화 없음"},
]


def load_ocr_texts(page: int) -> list[str]:
    pattern = os.path.join(OCR_RAW_DIR, f"*_p{page}_ocr_raw.json")
    matches = glob.glob(pattern)
    if not matches:
        return []
    with open(matches[0], encoding="utf-8") as f:
        data = json.load(f)
    return [item["text"] for item in data]


def _no_dot(s: str) -> str:
    return s.replace(".", "").replace(",", "")


def check_value(expected: str, texts: list[str]) -> tuple[str, str]:
    """(status, note) 반환.
    status: exact_match | found_as_substring | decimal_point_error | comma_error | not_found
    """
    if expected in texts:
        return "exact_match", ""
    for t in texts:
        if expected in t and expected != t:
            return "found_as_substring", f"OCR 텍스트 내 포함: '{t}'"
    # 소수점 누락 패턴 (예: 3.78 -> 378, 62.2 -> 622)
    if "." in expected:
        collapsed = expected.replace(".", "")
        if collapsed in texts:
            return "decimal_point_error", f"소수점 누락 의심: OCR='{collapsed}' (기대값='{expected}')"
        for t in texts:
            if collapsed in t:
                return "decimal_point_error", f"소수점 누락 의심(부분일치): OCR='{t}' (기대값='{expected}')"
    # 콤마 누락 (예: 2,100 -> 2100)
    if "," in expected:
        collapsed = expected.replace(",", "")
        if collapsed in texts:
            return "comma_error", f"천단위 콤마 누락: OCR='{collapsed}' (기대값='{expected}')"
        for t in texts:
            if collapsed in t:
                return "comma_error", f"천단위 콤마 누락(부분일치): OCR='{t}' (기대값='{expected}')"
    return "not_found", "OCR 결과 어디에서도 발견되지 않음"


def main():
    rows = []
    for gt in GROUND_TRUTH:
        texts = load_ocr_texts(gt["page"])
        status, note = check_value(gt["value"], texts)
        rows.append({
            "check_type": "numeric_value",
            "country": gt["country"],
            "table_id": gt["table_id"],
            "page": gt["page"],
            "label": gt["label"],
            "expected_value": gt["value"],
            "verification_status": status,
            "notes": note,
            "n_ocr_boxes_on_page": len(texts),
        })

    for gt in LABEL_GROUND_TRUTH:
        texts = load_ocr_texts(gt["page"])
        exact = gt["value"] in texts
        if exact:
            status, note = "exact_match", ""
        else:
            sub = [t for t in texts if gt["value"] in t]
            status, note = ("found_as_substring", f"OCR 텍스트 내 포함: {sub[:2]}") if sub else ("not_found", "발견되지 않음")
        rows.append({
            "check_type": f"label_{gt['label_type']}",
            "country": gt["country"],
            "table_id": gt["table_id"],
            "page": gt["page"],
            "label": gt["value"],
            "expected_value": gt["value"],
            "verification_status": status,
            "notes": note,
            "n_ocr_boxes_on_page": len(texts),
        })

    out_path = os.path.join(VERIFICATION_DIR, "sample_verification.csv")
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

    print(f"saved: {out_path}")
    from collections import Counter
    c = Counter(r["verification_status"] for r in rows)
    print("status summary:", dict(c))
    for r in rows:
        print(f"  [{r['verification_status']:20s}] {r['country']:4s} {r['table_id']:5s} p{r['page']} - {r['label']}: expected={r['expected_value']!r} | {r['notes']}")


if __name__ == "__main__":
    main()
