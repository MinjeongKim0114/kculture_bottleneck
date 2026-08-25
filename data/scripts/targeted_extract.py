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


# ---------------------------------------------------------------------------
# 표 1-17 / 1-18 / 1-37: "순위형" 표 (콘텐츠별 호감요인 / 호감 저해요인 / 한류
# 부정적 인식 공감 이유) 공용 로직
#
# 이 표들은 1-16/1-33/1-35/1-41과 근본적으로 다른 구조다:
#   - 항목(이유) 텍스트가 국가/카테고리마다 사실상 고정된 보기 목록이지만, 화면에는
#     응답률 내림차순으로 재정렬되어 표시된다 → "N번째 행 = 특정 항목"이라는 순서
#     가정을 쓸 수 없다.
#   - "1순위" 블록과 "1+2순위(중복)" 블록이 같은 항목 집합을 두 번(각각 다른 값으로)
#     보여준다. 두 블록을 구분하는 라벨("1순위" / "1+2순위(중복)")은 세로 병합된
#     낱글자 셀이라 bbox로 안정적으로 못 읽는다(1-16의 콘텐츠 카테고리명과 동일한
#     문제, README 참고).
#   - 따라서 카테고리명 순서로 매칭하는 1-16 방식과, 항목 라벨 자체는 OCR 텍스트를
#     그대로 신뢰하되 "1순위/1+2순위" 구분은 같은 라벨이 한 블록 안에서 몇 번
#     등장하는지(정상적으로는 정확히 2번)로 추론하는 방식을 결합한다:
#       1) "(사례수)" 행을 카테고리 블록 경계로 사용한다.
#       2) 블록 안에서 각 행의 라벨 = "전체" 열(가장 왼쪽 숫자 셀) 왼쪽의 텍스트를
#          모두 이어붙인 것, 값 = 그 숫자 셀.
#       3) 같은 라벨 텍스트가 그 블록 안에서 정확히 2번 나오면, 먼저 나온 것을
#          "1순위", 나중 것을 "1+2순위(중복)"로 확정한다(값 자체는 원본 그대로).
#       4) "기타"처럼 1순위에서 0%라 아예 그 블록에 안 나타나 1번만 등장하는 항목은,
#          그 등장 위치가 "2번 등장하는 항목들의 2번째(1+2순위) 등장 위치"보다
#          뒤쪽이면 1+2순위로, 앞쪽이면 1순위로 추정하되 verification_status를
#          manual_review로 남긴다(원본 대조 전까지 확정하지 않음).
#       5) 3번 이상 등장하거나 위치를 판단할 수 없으면 manual_review로 남기고
#          모든 등장을 raw로 보존한다(값을 버리지 않음).
#   - 콘텐츠 카테고리명(드라마/예능/... )은 1-16과 동일하게 bbox로 안정적으로
#     못 읽으므로, 표본 3개국(중국/미국/베트남)에서 공통으로 확인된 고정 순서
#     (1-16의 13개 카테고리 중 "전반적 만족도"를 제외한 12개, 같은 순서)를 쓴다.
#     카테고리 블록 개수가 12개가 아니면 라벨을 "카테고리_순서N(미확인)"으로 남기고
#     manual_review 처리한다(1-16과 동일 원칙).
# ---------------------------------------------------------------------------

CONTENT_CATEGORIES_1_17_18 = [
    "드라마", "예능", "영화", "음악", "애니메이션", "출판물", "웹툰",
    "게임", "패션", "뷰티", "음식", "한국어",
]

# 표 1-17/1-18은 6/8페이지에 걸쳐 있고, 각 페이지 맨 위에 표 헤더(구분/전체/성별/연령별/
# 지역 및 그 하위 컬럼명)가 반복 인쇄된다. 여러 페이지를 이어붙이면 이 헤더 행들이 이전
# 페이지 마지막 카테고리 블록의 "꼬리"에 섞여 들어간다(다음 '(사례수)' 행 전까지가 한
# 블록이므로). "10대"/"20대"처럼 숫자로 시작하는 헤더 토큰은 parse_number가 그대로 숫자로
# 읽어버려("10대" -> 10.0) 헤더 행 전체가 마치 항목 행처럼 보이는 사고가 실측 확인되었다
# (예: 중국 1-17에서 '남성 여성' 이라는 가짜 항목이 값 10.0으로 생성됨). 그룹화 이전에
# 헤더로만 이루어진 행을 통째로 제거해 원천 차단한다.
_HEADER_NOISE_TOKENS = {
    "구분", "전체", "성별", "연령별", "지역", "남성", "여성",
    "10대", "20대", "30대", "40대", "50대",
    "동부", "연안", "동부연안", "동부 연안", "동북부", "서부", "중부",
}


def _strip_header_noise_rows(rows: list[list[OcrBox]]) -> list[list[OcrBox]]:
    cleaned = []
    for row in rows:
        texts = [b.text.strip() for b in row if b.text.strip()]
        if texts and all(t in _HEADER_NOISE_TOKENS for t in texts):
            continue
        cleaned.append(row)
    return cleaned


def _block_boundaries(rows: list[list[OcrBox]]) -> list[tuple[int, int]]:
    """'(사례수)' 행 인덱스를 기준으로 (base_idx, next_base_idx_or_end) 블록 경계 목록을 반환."""
    base_idxs = _find_rows_with(rows, ["사례수"])
    boundaries = []
    for i, b in enumerate(base_idxs):
        end = base_idxs[i + 1] if i + 1 < len(base_idxs) else len(rows)
        boundaries.append((b, end))
    return boundaries


def _row_item_label_and_value(row: list[OcrBox]) -> tuple[str | None, "OcrBox | None"]:
    """행에서 '전체' 열(가장 왼쪽의 숫자로 해석 가능한 셀)과 그 왼쪽의 라벨 텍스트를 함께 추출.

    1-16/33/35/41 은 미리 알려진 라벨 문자열로 값 위치를 찾았지만, 1-17/18/37 은
    라벨 자체가 국가별로 다른 순서로 나타나는 자유 텍스트라 이 방식을 쓸 수 없다.
    대신 '가장 왼쪽 숫자 셀 = 전체 열'이라는 표 레이아웃 규칙(라벨 다음에 바로
    전체/성별/연령/지역 숫자 컬럼이 이어짐)을 이용해 라벨과 값을 동시에 분리한다.
    """
    numeric_boxes = [b for b in row if parse_number(b.text) is not None]
    if not numeric_boxes:
        return None, None
    value_box = min(numeric_boxes, key=lambda b: b.x_center)
    label_boxes = [b for b in row if b.x_center < value_box.x_center]
    if not label_boxes:
        return None, value_box
    label_text = " ".join(b.text for b in sorted(label_boxes, key=lambda b: b.x_center)).strip()
    return (label_text or None), value_box


def _merge_wrapped_label_rows(block_rows: list[list[OcrBox]]) -> list[list[OcrBox]]:
    """줄바꿈된 라벨(예: '사용자 환경이 편리해서 \\n (검색, 페이지 넘김...)')이 있는 항목은
    실제 렌더링 상 두 줄이라, row_gap=10 클러스터링이 라벨 텍스트 행과 숫자 값 행을
    서로 다른 행으로 쪼개는 경우가 실측 확인되었다(예: 중국 1-17 '웹툰' 카테고리
    '사용자 환경이 편리해서' 항목). 방치하면 라벨 없는 숫자 전용 행이 되어 값이
    조용히 버려진다(원칙 위반). 라벨이 있고 숫자가 전혀 없는 행 바로 다음 행이
    '숫자만 있고 텍스트가 전혀 없는' 행이면 두 행을 합쳐 하나의 항목으로 복원한다.
    그 외의 텍스트 전용 행(예: 괄호 안 부연설명 줄)은 다음 실제 항목에 잘못
    달라붙지 않도록 버린다(라벨 매칭은 접미사 기반이라 약간의 잡음은 허용됨)."""
    merged = []
    i = 0
    n = len(block_rows)
    while i < n:
        row = block_rows[i]
        has_num = any(parse_number(b.text) is not None for b in row)
        if not has_num:
            nxt = block_rows[i + 1] if i + 1 < n else None
            nxt_all_numeric = bool(nxt) and all(parse_number(b.text) is not None for b in nxt)
            if nxt_all_numeric:
                merged.append(row + nxt)
                i += 2
                continue
            i += 1
            continue
        merged.append(row)
        i += 1
    return merged


def _normalize_item_label(text: str) -> str:
    return text.replace(" ", "").strip()


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
        prev = cur
    return prev[-1]


def _labels_match(a: str, b: str) -> bool:
    """두 항목 라벨이 같은 보기 항목을 가리키는지 판정한다.

    실측 확인된 두 종류의 OCR 잡음에 모두 대응해야 한다:
      1) '1 순위' / '1+2 순위(중복)' 열이나 콘텐츠 카테고리명이 세로 병합 셀이라, 그
         낱글자가 같은 줄의 항목 라벨 박스에 뒤섞여 붙는 경우 (예: '순 스토리 전개와
         장면 전환이 빨라서' vs '2 스토리 전개와 장면 전환이 빨라서') — 접미사(suffix)
         일치로 잡아낸다.
      2) 긴 한글 문장 안에서 글자 하나가 다르게 오인식되는 경우 (예: '단단해서' vs
         '탄단해서', '성계역할' vs '성계억할') — 편집거리(Levenshtein)가 작으면 같은
         항목으로 본다.
    두 기준 모두 "완전히 다른 두 항목을 잘못 합치는" 위험보다 "같은 항목을 못 알아보고
    manual_review로 남기는" 쪽이 안전하므로, 임계값은 보수적으로(짧은 오탈자/잡음
    수준만) 잡는다.
    """
    na, nb = _normalize_item_label(a), _normalize_item_label(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    shorter_len = min(len(na), len(nb))
    common = 0
    while common < len(na) and common < len(nb) and na[-1 - common] == nb[-1 - common]:
        common += 1
    if common >= max(6, int(shorter_len * 0.7)):
        return True
    # 편집거리 기반 보조 판정: 문장이 길수록(오탈자 비중이 작아지므로) 허용 오차를 늘림
    max_edit = 1 if shorter_len < 8 else (2 if shorter_len < 16 else 3)
    return _levenshtein(na, nb) <= max_edit


def _group_item_occurrences(rows: list[list[OcrBox]], base_idx: int,
                             end_idx: int) -> list[tuple[str, list[tuple[int, "OcrBox"]]]]:
    """블록 내 행들을 라벨 기준으로 그룹화한다(접미사 기반 fuzzy 매칭, 등장 순서 보존).
    그룹의 대표 라벨 문자열은 그 그룹에서 가장 긴(=잡음이 가장 적을 가능성이 높은) 것을 쓴다."""
    block_rows = _merge_wrapped_label_rows([rows[i] for i in range(base_idx + 1, end_idx)])
    row_idx_base = base_idx + 1  # 병합으로 인덱스가 밀릴 수 있어, 그룹 내 순서 비교용으로만 순번을 재부여

    groups: list[dict] = []  # [{"label": str, "occ": [(seq, box), ...]}]
    for seq, row in enumerate(block_rows):
        label, val_box = _row_item_label_and_value(row)
        if label is None or val_box is None:
            continue
        target = None
        for g in groups:
            if _labels_match(g["label"], label):
                target = g
                break
        if target is None:
            groups.append({"label": label, "occ": [(seq, val_box)]})
        else:
            if len(label) > len(target["label"]):
                target["label"] = label
            target["occ"].append((seq, val_box))
    return [(g["label"], g["occ"]) for g in groups]


def _extract_ranked_block(rows: list[list[OcrBox]], base_idx: int, end_idx: int,
                           category_label: str) -> tuple[list[dict], list[str]]:
    """하나의 카테고리 블록(사례수 행부터 다음 사례수 행 전까지)에서
    '1순위' / '1+2순위(중복)' 항목별 값을 추출한다."""
    issues = []
    values = []

    base_row = rows[base_idx]
    base_label = _label_box_in_row(base_row, ["사례수"])
    base_box = _value_right_of(base_row, base_label) if base_label else None
    base_val, base_text = (parse_number(base_box.text), base_box.text) if base_box else (None, None)
    if base_val is None:
        issues.append(f"[{category_label}] '(사례수)' 값을 찾지 못해 BASE 확인 불가")

    grouped = _group_item_occurrences(rows, base_idx, end_idx)
    if not grouped:
        issues.append(f"[{category_label}] 항목 행을 하나도 찾지 못함")
        return values, issues

    occurrences = {label: occ for label, occ in grouped}
    order = [label for label, _ in grouped]

    # '정상적으로 2번 등장'하는 항목들의 2번째(=1+2순위) 등장 위치 중 최솟값을
    # 두 블록의 경계로 사용 (1순위에서 0%라 1번만 등장하는 항목의 소속을 추정하기 위함)
    second_occurrence_idxs = [occ[1][0] for occ in occurrences.values() if len(occ) == 2]
    boundary_idx = min(second_occurrence_idxs) if second_occurrence_idxs else None

    for label in order:
        occ = occurrences[label]
        if len(occ) == 2:
            (idx1, box1), (idx2, box2) = occ
            values.append({
                "content_category": category_label, "item": label, "rank_group": "1순위",
                "value": parse_number(box1.text), "unit": "%", "base": base_val,
                "ocr_confidence": box1.confidence, "source_row_text": box1.text,
                "verification_status": "auto_extracted",
            })
            values.append({
                "content_category": category_label, "item": label, "rank_group": "1+2순위(중복)",
                "value": parse_number(box2.text), "unit": "%", "base": base_val,
                "ocr_confidence": box2.confidence, "source_row_text": box2.text,
                "verification_status": "auto_extracted",
            })
        elif len(occ) == 1:
            idx, box = occ[0]
            if boundary_idx is not None:
                rank_group = "1+2순위(중복)" if idx >= boundary_idx else "1순위"
            else:
                rank_group = "순위미상(1회만 발견)"
            issues.append(f"[{category_label}] 항목 '{label}' 이 블록 안에서 1번만 발견됨 "
                           f"(rank_group='{rank_group}'로 추정, 원본 대조 필요)")
            values.append({
                "content_category": category_label, "item": label, "rank_group": rank_group,
                "value": parse_number(box.text), "unit": "%", "base": base_val,
                "ocr_confidence": box.confidence, "source_row_text": box.text,
                "verification_status": "manual_review",
            })
        else:
            issues.append(f"[{category_label}] 항목 '{label}' 이 블록 안에서 {len(occ)}번 발견됨 "
                           f"(기대값 2) — 모든 등장을 raw로 보존, manual_review 처리")
            for i, (idx, box) in enumerate(occ):
                values.append({
                    "content_category": category_label, "item": label,
                    "rank_group": f"순위미상(중복{len(occ)}회 중 {i+1}번째)",
                    "value": parse_number(box.text), "unit": "%", "base": base_val,
                    "ocr_confidence": box.confidence, "source_row_text": box.text,
                    "verification_status": "manual_review",
                })

    return values, issues


def _extract_reason_table(rows: list[list[OcrBox]], table_label: str) -> tuple[list[dict], list[str]]:
    """1-17/1-18 공용: 12개 콘텐츠 카테고리 블록을 순서대로 순회하며 추출."""
    issues = []
    values = []

    rows = _strip_header_noise_rows(rows)
    boundaries = _block_boundaries(rows)
    if len(boundaries) != len(CONTENT_CATEGORIES_1_17_18):
        issues.append(f"[{table_label}] 카테고리 블록이 {len(boundaries)}개 발견됨 "
                       f"(표본 3개국 공통 기대값 {len(CONTENT_CATEGORIES_1_17_18)}). "
                       f"카테고리명을 순서로 매칭할 수 없어 '카테고리_순서N'으로 대체하고 manual_review 표시")

    for order, (b_idx, e_idx) in enumerate(boundaries):
        if len(boundaries) == len(CONTENT_CATEGORIES_1_17_18):
            category_label = CONTENT_CATEGORIES_1_17_18[order]
        else:
            category_label = f"카테고리_순서{order+1}(미확인)"

        block_values, block_issues = _extract_ranked_block(rows, b_idx, e_idx, category_label)
        if len(boundaries) != len(CONTENT_CATEGORIES_1_17_18):
            for v in block_values:
                v["verification_status"] = "manual_review"
        values.extend(block_values)
        issues.extend(block_issues)

    return values, issues


def extract_1_17(rows: list[list[OcrBox]]) -> tuple[list[dict], list[str]]:
    """표 1-17: 한국 문화콘텐츠 호감요인 (콘텐츠 카테고리별 1순위/1+2순위 이유, 전체 열)."""
    return _extract_reason_table(rows, "1-17 호감요인")


def extract_1_18(rows: list[list[OcrBox]]) -> tuple[list[dict], list[str]]:
    """표 1-18: 한국 문화콘텐츠 호감 저해요인 (콘텐츠 카테고리별 1순위/1+2순위 이유, 전체 열).

    1-17과 달리 각 블록 끝에 '없음'(해당 카테고리에 저해요인이 없다는 응답) 항목이
    추가로 존재한다. 별도 처리 없이 일반 항목과 동일하게(라벨 텍스트 그대로) 취급한다.
    """
    return _extract_reason_table(rows, "1-18 호감 저해요인")


def extract_1_37(rows: list[list[OcrBox]]) -> tuple[list[dict], list[str]]:
    """표 1-37: 한류에 대한 부정적 인식 공감 이유 (단일 블록, 콘텐츠 카테고리 구분 없음).

    구조는 1-17/1-18의 카테고리 블록 하나와 동일(사례수 행 + 1순위/1+2순위 항목들)
    하므로 같은 로직을 그대로 재사용하되 category_label만 없앤다.
    """
    rows = _strip_header_noise_rows(rows)
    boundaries = _block_boundaries(rows)
    if not boundaries:
        return [], ["'(사례수)' 행을 찾지 못해 표 전체를 인식하지 못함"]
    if len(boundaries) > 1:
        # 이 페이지에는 표 1-36(공감 정도)이 표 1-37 위에 함께 인쇄되어 있어
        # '(사례수)' 행이 여러 번 나올 수 있다(1-35/1-34 교차 오염과 동일 유형의 문제,
        # README 버그 3번 참고). 1-37 고유 항목은 페이지에서 가장 마지막에 나오는
        # 사례수 블록에 있으므로 그 블록만 사용한다.
        b_idx, e_idx = boundaries[-1]
    else:
        b_idx, e_idx = boundaries[0]

    values, issues = _extract_ranked_block(rows, b_idx, e_idx, "1-37")
    for v in values:
        v.pop("content_category", None)
    return values, issues


EXTRACTORS = {
    "16": extract_1_16,
    "33": extract_1_33,
    "35": extract_1_35,
    "41": extract_1_41,
    "17": extract_1_17,
    "18": extract_1_18,
    "37": extract_1_37,
}
