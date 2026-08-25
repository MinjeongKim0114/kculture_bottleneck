"""
표별 타겟 추출 로직 (라벨 텍스트 위치 기반).

이 모듈은 "표 전체를 완전한 그리드로 복원"하지 않는다. 대신 이미 3개국 샘플에서
검증된 방식 — 특정 라벨(예: "한국 관광", "5점 척도 평균(점)")을 찾고, 같은 행(row)에서
"전체" 열(라벨 바로 다음에 오는 첫 숫자 셀)의 값을 읽는 방식 — 을 30개국에 일반화한다.

각 함수는 (values: list[dict], issues: list[str]) 를 반환한다.
values 안의 각 dict는 최소 {item, value, unit, base, ocr_confidence, source_row_text} 를 갖는다.
찾지 못하면 값 대신 issues 에 사유를 남기고, 절대 값을 추정하지 않는다.
"""
from __future__ import annotations

import re

from pdf_table_extractor import OcrBox, cluster_rows

NUM_RE = re.compile(r"-?\d[\d,]*\.?\d*")


def parse_number(text: str) -> float | None:
    """텍스트에서 숫자를 추출한다. 쉼표는 천단위 구분자로 제거. 실패하면 None."""
    m = NUM_RE.search(text.replace(" ", ""))
    if not m:
        return None
    raw = m.group(0).replace(",", "")
    try:
        return float(raw)
    except ValueError:
        return None


def _find_rows_with(rows: list[list[OcrBox]], substrings: list[str]) -> list[int]:
    """row 리스트 중 substring을 포함하는 row의 인덱스들.

    라벨이 "매우" + "긍정적으로 변함" 처럼 여러 박스로 쪼개져 인식되는 경우가 있어
    (박스 하나에서 못 찾을 수 있음) 같은 행을 이어붙인 문자열에서도 검사한다.
    """
    idxs = []
    for i, row in enumerate(rows):
        joined = " ".join(b.text for b in row)
        for b in row:
            if any(s in b.text for s in substrings):
                idxs.append(i)
                break
        else:
            if any(s.replace(" ", "") in joined.replace(" ", "") for s in substrings):
                idxs.append(i)
    return idxs


def _label_box_in_row(row: list[OcrBox], substrings: list[str]) -> OcrBox | None:
    """라벨에 해당하는 박스를 찾는다. 값을 읽을 때 '이 박스보다 오른쪽'의 기준점으로 쓰인다.

    라벨이 하나의 박스에 통째로 있으면 그 박스를 반환한다. 만약 "매우" + "긍정적으로 변함"
    처럼 여러 박스로 쪼개져 인식된 경우, substring 하나가 정확히 일치하는 박스가 없으므로
    라벨 파편(각 substring의 부분 문자열)을 찾아 그중 가장 오른쪽(=라벨의 끝 부분) 박스를
    기준점으로 쓴다 — 값은 라벨이 끝난 지점 오른쪽에서 시작하기 때문.
    """
    for b in row:
        if any(s in b.text for s in substrings):
            return b
    fragments = []
    for b in row:
        bt = b.text.replace(" ", "")
        if not bt:
            continue
        if any(bt in s.replace(" ", "") for s in substrings):
            fragments.append(b)
    if fragments:
        return max(fragments, key=lambda b: b.x_center)
    return None


def _value_right_of(row: list[OcrBox], label_box: OcrBox) -> OcrBox | None:
    """같은 행에서 label_box 오른쪽에 있는 박스 중 숫자로 해석 가능한 첫 번째 박스 (=전체 열)."""
    candidates = [b for b in row if b.x_center > label_box.x_center and parse_number(b.text) is not None]
    if not candidates:
        return None
    return min(candidates, key=lambda b: b.x_center)


def _nearest_base_above(rows: list[list[OcrBox]], target_row_idx: int) -> tuple[float | None, str | None]:
    """target_row_idx보다 위(작은 인덱스)에 있는 행 중 '(사례수)' 텍스트를 포함하는 가장 가까운 행에서
    '전체' 열(사례수 라벨 바로 다음 숫자) 값을 BASE로 반환."""
    for i in range(target_row_idx, -1, -1):
        row = rows[i]
        label = _label_box_in_row(row, ["사례수"])
        if label:
            val_box = _value_right_of(row, label)
            if val_box:
                return parse_number(val_box.text), val_box.text
            return None, None
    return None, None


# ---------------------------------------------------------------------------
# 표 1-41: 최근 4년간 고관여 한국산 제품/서비스 구매 여부 -> "한국 관광" 행
# ---------------------------------------------------------------------------

def extract_1_41(rows: list[list[OcrBox]]) -> tuple[list[dict], list[str]]:
    issues = []
    values = []

    tour_row_idxs = _find_rows_with(rows, ["한국 관광", "한국관광"])
    if len(tour_row_idxs) != 2:
        issues.append(f"'한국 관광' 행이 {len(tour_row_idxs)}개 발견됨 (기대값 2: 구매여부% + 평균횟수)")

    labels = ["구매(방문) 경험률(%)", "평균 구매(방문) 횟수(회)"]
    units = ["%", "회"]

    for order, row_idx in enumerate(tour_row_idxs[:2]):
        row = rows[row_idx]
        label_box = _label_box_in_row(row, ["한국 관광", "한국관광"])
        val_box = _value_right_of(row, label_box) if label_box else None
        base_val, base_text = _nearest_base_above(rows, row_idx)

        item_name = labels[order] if order < len(labels) else f"한국 관광 (순서미상 #{order+1})"
        unit = units[order] if order < len(units) else "unknown"

        if val_box is None:
            issues.append(f"'{item_name}' 값의 오른쪽 숫자를 찾지 못함 (row_idx={row_idx})")
            values.append({
                "item": f"한국 관광 - {item_name}", "value": None, "unit": unit,
                "base": base_val, "ocr_confidence": None, "source_row_text": None,
                "verification_status": "manual_review",
            })
        else:
            values.append({
                "item": f"한국 관광 - {item_name}", "value": parse_number(val_box.text), "unit": unit,
                "base": base_val, "ocr_confidence": val_box.confidence, "source_row_text": val_box.text,
                "verification_status": "auto_extracted",
            })

    if not tour_row_idxs:
        issues.append("'한국 관광' 행을 전혀 찾지 못함")

    return values, issues


# ---------------------------------------------------------------------------
# 표 1-35: 한국 문화콘텐츠 경험 후 한국에 대한 인식 변화
# ---------------------------------------------------------------------------

ITEMS_1_35 = [
    "매우 부정적으로 변함",
    "약간 부정적으로 변함",
    "변화 없음",
    "약간 긍정적으로 변함",
    "매우 긍정적으로 변함",
]


def extract_1_35(rows: list[list[OcrBox]]) -> tuple[list[dict], list[str]]:
    """주의: 이 표(1-35)가 있는 페이지에는 다른 표(예: 1-34 유료이용의향)가 같은 페이지에
    함께 인쇄되어 있고, 그 표에도 "5점 척도 평균(점)" 행이 여러 번 나온다(카테고리별로).
    따라서 "5점 척도 평균"을 페이지 전체에서 무작정 첫 번째로 찾으면 엉뚱한 표(1-34)의
    값을 가져오는 버그가 있었다(교차검증에서 실제로 발견됨). 반드시 1-35 고유 항목
    (①~⑤ "...변함")이 위치한 행보다 아래에 있는 5점 척도 평균만 사용한다.
    """
    issues = []
    values = []

    base_val, base_text = None, None
    base_rows = _find_rows_with(rows, ["사례수"])

    item_rows: dict[str, int] = {}
    for item in ITEMS_1_35:
        idxs = _find_rows_with(rows, [item])
        if idxs:
            item_rows[item] = idxs[0]

    # 1-35 고유 항목이 위치한 행 범위를 기준으로, 그 범위와 가장 가까운 사례수 행을 BASE로 사용
    if item_rows:
        first_item_idx = min(item_rows.values())
        candidate_base_idxs = [i for i in base_rows if i <= first_item_idx]
        base_row_idx = max(candidate_base_idxs) if candidate_base_idxs else (base_rows[-1] if base_rows else None)
    else:
        base_row_idx = base_rows[0] if base_rows else None

    if base_row_idx is not None:
        base_val, base_text = _nearest_base_above(rows, base_row_idx)
    else:
        issues.append("'(사례수)' 행을 찾지 못해 BASE 확인 불가")

    for item in ITEMS_1_35:
        if item not in item_rows:
            issues.append(f"항목 '{item}' 행을 찾지 못함")
            values.append({"item": item, "value": None, "unit": "%", "base": base_val,
                            "ocr_confidence": None, "source_row_text": None,
                            "verification_status": "manual_review"})
            continue
        row = rows[item_rows[item]]
        label_box = _label_box_in_row(row, [item])
        val_box = _value_right_of(row, label_box)
        if val_box is None:
            issues.append(f"항목 '{item}' 값을 찾지 못함")
            values.append({"item": item, "value": None, "unit": "%", "base": base_val,
                            "ocr_confidence": None, "source_row_text": None,
                            "verification_status": "manual_review"})
        else:
            values.append({"item": item, "value": parse_number(val_box.text), "unit": "%", "base": base_val,
                            "ocr_confidence": val_box.confidence, "source_row_text": val_box.text,
                            "verification_status": "auto_extracted"})

    # "5점 척도 평균"은 반드시 1-35 고유 항목들보다 아래(뒤)에 있는 첫 occurrence를 사용
    lower_bound = max(item_rows.values()) if item_rows else -1
    avg_idxs = [i for i in _find_rows_with(rows, ["5점 척도 평균"]) if i > lower_bound]
    if avg_idxs:
        row = rows[avg_idxs[0]]
        label_box = _label_box_in_row(row, ["5점 척도 평균"])
        val_box = _value_right_of(row, label_box)
        if val_box:
            values.append({"item": "5점 척도 평균(점)", "value": parse_number(val_box.text), "unit": "score(1-5)",
                            "base": base_val, "ocr_confidence": val_box.confidence,
                            "source_row_text": val_box.text, "verification_status": "auto_extracted"})
        else:
            issues.append("'5점 척도 평균' 값을 찾지 못함")
    else:
        issues.append("'5점 척도 평균' 행을 찾지 못함 (1-35 항목 이후 범위에서)")

    return values, issues


# ---------------------------------------------------------------------------
# 표 1-33: 한국 문화콘텐츠 관심도 및 소비지출 의향 (6개 블록, 각 5점 척도 평균)
# ---------------------------------------------------------------------------

BLOCKS_1_33 = [
    "본인 관심도 변화 (1년 전 대비)",
    "본인 관심도 변화 (1년 후 예상)",
    "자국민 관심도 변화 (1년 전 대비)",
    "자국민 관심도 변화 (1년 후 예상)",
    "본인 소비지출 의향 변화 (1년 전 대비)",
    "본인 소비지출 의향 변화 (1년 후 예상)",
]


def extract_1_33(rows: list[list[OcrBox]]) -> tuple[list[dict], list[str]]:
    issues = []
    values = []

    base_val, base_text = None, None
    base_rows = _find_rows_with(rows, ["사례수"])
    if base_rows:
        base_val, base_text = _nearest_base_above(rows, base_rows[0])
    else:
        issues.append("'(사례수)' 행을 찾지 못해 BASE 확인 불가")

    avg_idxs = _find_rows_with(rows, ["5점 척도 평균"])
    if len(avg_idxs) != len(BLOCKS_1_33):
        issues.append(f"'5점 척도 평균' 행이 {len(avg_idxs)}개 발견됨 "
                       f"(기대값 {len(BLOCKS_1_33)}). 표 형식이 예상과 다를 수 있음 — 순서 기반 라벨링을 신뢰하지 말 것")

    for order, idx in enumerate(avg_idxs):
        row = rows[idx]
        label_box = _label_box_in_row(row, ["5점 척도 평균"])
        val_box = _value_right_of(row, label_box)
        block_name = BLOCKS_1_33[order] if order < len(BLOCKS_1_33) else f"블록 순서미상 #{order+1}"
        status = "auto_extracted" if (val_box is not None and order < len(BLOCKS_1_33)) else "manual_review"
        values.append({
            "item": f"{block_name} - 5점 척도 평균(점)",
            "value": parse_number(val_box.text) if val_box else None,
            "unit": "score(1-5)", "base": base_val,
            "ocr_confidence": val_box.confidence if val_box else None,
            "source_row_text": val_box.text if val_box else None,
            "verification_status": status,
        })
        if val_box is None:
            issues.append(f"블록 #{order+1} 값의 오른쪽 숫자를 찾지 못함")

    return values, issues


# ---------------------------------------------------------------------------
# 표 1-16: 콘텐츠별 호감도 (여러 콘텐츠 카테고리 블록, 각 5점 척도 평균 + BASE)
#
# 카테고리명은 세로 병합 셀이라 bbox 좌표만으로는 안정적으로 못 읽어서(테스트 결과,
# "구분"/BASE 숫자 등 엉뚱한 박스가 최소 x로 잡힘), 3개 표본국가(중국/미국/베트남)에서
# 공통으로 확인된 고정 순서를 사용한다. 블록 개수가 13개가 아니면 이 가정이 깨진 것이므로
# 라벨을 "순서미상"으로 남기고 manual_review 로 표시한다 (값 자체는 그대로 보존).
# ---------------------------------------------------------------------------

CONTENT_CATEGORIES_1_16 = [
    "드라마", "예능", "영화", "음악", "애니메이션", "출판물", "웹툰",
    "게임", "패션", "뷰티", "음식", "한국어", "전반적 만족도",
]


def extract_1_16(rows: list[list[OcrBox]]) -> tuple[list[dict], list[str]]:
    issues = []
    values = []

    avg_idxs = _find_rows_with(rows, ["5점 척도 평균"])
    base_idxs = _find_rows_with(rows, ["사례수"])

    if not avg_idxs:
        issues.append("'5점 척도 평균' 행을 전혀 찾지 못함")
        return values, issues

    if len(avg_idxs) != len(CONTENT_CATEGORIES_1_16):
        issues.append(f"콘텐츠 블록이 {len(avg_idxs)}개 발견됨 (표본 3개국 공통 기대값 "
                       f"{len(CONTENT_CATEGORIES_1_16)}). 카테고리명을 순서로 매칭할 수 없어 "
                       f"'카테고리_순서N'으로 대체하고 manual_review 표시")

    prev_boundary = 0
    for order, avg_idx in enumerate(avg_idxs):
        row = rows[avg_idx]
        label_box = _label_box_in_row(row, ["5점 척도 평균"])
        val_box = _value_right_of(row, label_box)

        block_base_idxs = [i for i in base_idxs if prev_boundary <= i <= avg_idx]
        base_val, base_text = None, None
        if block_base_idxs:
            base_row = rows[block_base_idxs[-1]]
            base_label = _label_box_in_row(base_row, ["사례수"])
            base_box = _value_right_of(base_row, base_label)
            if base_box:
                base_val, base_text = parse_number(base_box.text), base_box.text
        else:
            issues.append(f"블록 #{order+1}(avg_row={avg_idx})의 BASE(사례수) 행을 찾지 못함")

        if len(avg_idxs) == len(CONTENT_CATEGORIES_1_16):
            category_label = CONTENT_CATEGORIES_1_16[order]
            status = "auto_extracted" if val_box else "manual_review"
        else:
            category_label = f"카테고리_순서{order+1}(미확인)"
            status = "manual_review"

        if val_box is None:
            issues.append(f"카테고리 '{category_label}' 의 5점 척도 평균 값을 찾지 못함")

        values.append({
            "item": "5점 척도 평균(점)",
            "content_category": category_label,
            "value": parse_number(val_box.text) if val_box else None,
            "unit": "score(1-5)",
            "base": base_val,
            "ocr_confidence": val_box.confidence if val_box else None,
            "source_row_text": val_box.text if val_box else None,
            "verification_status": status,
        })

        prev_boundary = avg_idx + 1

    return values, issues


EXTRACTORS = {
    "16": extract_1_16,
    "33": extract_1_33,
    "35": extract_1_35,
    "41": extract_1_41,
}
