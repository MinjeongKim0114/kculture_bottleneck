"""
PDF 표 원수치 추출 파이프라인 (핵심 모듈)

이 모듈은 다음 파일들을 재사용한다 (재구현하지 않음):
- data/processed/country_table_page_map.csv  : 국가 x 표 x 페이지 매핑 (이미 검증됨)
- data/raw/2026 한류실태조사_통계.pdf         : 원본 PDF (읽기 전용, 절대 수정하지 않음)

책임 범위:
1. 페이지 매핑 조회 (기존 CSV 재활용)
2. PDF 페이지 렌더링 (PyMuPDF)
3. EasyOCR로 텍스트 + bounding box + confidence 추출
4. bounding box 좌표 기반 행/열 구조 복원 시도 (실패 시 raw만 보존하고 manual_review 표시)

주의:
- 이 모듈은 숫자를 "추정"하거나 "보간"하지 않는다. OCR이 읽지 못한 값은 빈 값으로 남긴다.
- 표마다 구조가 다르므로 행/열 복원은 최선 노력(best-effort)이며, 실패 시 raw만 신뢰한다.
"""
from __future__ import annotations

import csv
import json
import os
from dataclasses import dataclass, field, asdict
from typing import Optional

import pymupdf

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PDF_PATH = os.path.join(PROJECT_ROOT, "data", "raw", "2026 한류실태조사_통계.pdf")
PAGE_MAP_CSV = os.path.join(PROJECT_ROOT, "data", "processed", "country_table_page_map.csv")

IMG_DIR = os.path.join(PROJECT_ROOT, "data", "processed", "page_images")
OCR_RAW_DIR = os.path.join(PROJECT_ROOT, "data", "processed", "ocr_raw")
EXTRACTED_DIR = os.path.join(PROJECT_ROOT, "data", "processed", "extracted")
VERIFICATION_DIR = os.path.join(PROJECT_ROOT, "data", "processed", "verification")

for d in (IMG_DIR, OCR_RAW_DIR, EXTRACTED_DIR, VERIFICATION_DIR):
    os.makedirs(d, exist_ok=True)


# ---------------------------------------------------------------------------
# 1. 페이지 매핑 조회 (기존 country_table_page_map.csv 재활용, 재계산하지 않음)
# ---------------------------------------------------------------------------

def load_page_map(csv_path: str = PAGE_MAP_CSV) -> list[dict]:
    with open(csv_path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    return rows


def get_pages(page_map: list[dict], country: str, table_index: str | int) -> list[int]:
    """country/table_index 조합에 해당하는 페이지 번호 리스트를 반환한다.

    표가 여러 페이지에 걸쳐 있으면(예: 1-17, 1-18) 전부 반환한다.
    country_table_page_map.csv 의 'pages' 컬럼은 콤마로 구분된 문자열이거나 'NOT_FOUND'.
    """
    table_index = str(table_index)
    for r in page_map:
        if r["country"] == country and r["table_index"] == table_index:
            if r["pages"] == "NOT_FOUND":
                return []
            return [int(p) for p in r["pages"].split(",")]
    raise KeyError(f"country={country!r}, table_index={table_index!r} not found in page map")


# ---------------------------------------------------------------------------
# 2. PDF 페이지 렌더링
# ---------------------------------------------------------------------------

def render_page(page_num: int, dpi: int = 200, pdf_path: str = PDF_PATH):
    """1-based page_num 을 렌더링해서 (PIL.Image, save_path) 반환. 원본 PDF는 읽기 전용으로만 연다."""
    from PIL import Image

    doc = pymupdf.open(pdf_path)
    try:
        page = doc[page_num - 1]
        pix = page.get_pixmap(dpi=dpi)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    finally:
        doc.close()
    return img


def save_page_image(img, country: str, table_index: str, page_num: int) -> str:
    fname = f"{country}_1-{table_index}_p{page_num}.png"
    path = os.path.join(IMG_DIR, fname)
    img.save(path)
    return path


# ---------------------------------------------------------------------------
# 3. OCR (EasyOCR) - bbox + confidence 보존
# ---------------------------------------------------------------------------

@dataclass
class OcrBox:
    text: str
    bbox: list  # [[x,y] x4] 원본 폴리곤 좌표 (EasyOCR 반환 형식 그대로)
    confidence: float
    x_center: float = field(init=False)
    y_center: float = field(init=False)

    def __post_init__(self):
        # EasyOCR은 bbox 좌표를 numpy int32로 반환하는 경우가 있어 JSON 직렬화를 위해 float로 변환
        self.bbox = [[float(p[0]), float(p[1])] for p in self.bbox]
        xs = [p[0] for p in self.bbox]
        ys = [p[1] for p in self.bbox]
        self.x_center = sum(xs) / len(xs)
        self.y_center = sum(ys) / len(ys)


_reader = None


def get_reader():
    global _reader
    if _reader is None:
        import easyocr

        _reader = easyocr.Reader(["ko", "en"], gpu=False)
    return _reader


def ocr_image(img) -> list[OcrBox]:
    import numpy as np

    reader = get_reader()
    arr = np.array(img)
    results = reader.readtext(arr, detail=1)
    return [OcrBox(text=t, bbox=box, confidence=float(conf)) for box, t, conf in results]


def save_ocr_raw(boxes: list[OcrBox], country: str, table_index: str, page_num: int) -> str:
    fname = f"{country}_1-{table_index}_p{page_num}_ocr_raw.json"
    path = os.path.join(OCR_RAW_DIR, fname)
    data = [
        {"text": b.text, "bbox": b.bbox, "confidence": b.confidence,
         "x_center": b.x_center, "y_center": b.y_center}
        for b in boxes
    ]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return path


def _ocr_raw_path_for_page(page_num: int) -> Optional[str]:
    """이미 해당 페이지를 OCR한 raw 파일이 있으면 경로를 반환 (국가/표 무관하게 페이지 번호로 검색).

    같은 페이지가 여러 (country, table) 조합에서 재사용될 수 있으므로(예: 1-16이 2페이지에
    걸쳐 있고 그 중 한 페이지에 다른 표가 같이 있는 경우) 페이지 번호 기준으로 캐시를 찾는다.
    """
    import glob

    matches = glob.glob(os.path.join(OCR_RAW_DIR, f"*_p{page_num}_ocr_raw.json"))
    return matches[0] if matches else None


def load_ocr_raw(path: str) -> list[OcrBox]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    boxes = []
    for item in data:
        b = OcrBox(text=item["text"], bbox=item["bbox"], confidence=item["confidence"])
        boxes.append(b)
    return boxes


def get_ocr_for_page(country: str, table_index: str, page_num: int, dpi: int = 200,
                      use_cache: bool = True) -> tuple[list[OcrBox], bool]:
    """페이지에 대한 OCR 결과를 반환한다. 이미 캐시(ocr_raw)가 있으면 재사용하고
    (반환값 두 번째 요소 True), 없으면 새로 렌더링+OCR 해서 저장한다 (False).

    같은 원본 PDF 페이지를 다른 (country, table) 조합에서 중복 OCR하지 않기 위한 캐시.
    """
    if use_cache:
        cached = _ocr_raw_path_for_page(page_num)
        if cached:
            return load_ocr_raw(cached), True

    img = render_page(page_num, dpi=dpi)
    save_page_image(img, country, table_index, page_num)
    boxes = ocr_image(img)
    save_ocr_raw(boxes, country, table_index, page_num)
    return boxes, False


# ---------------------------------------------------------------------------
# 3b. 행 클러스터링 (targeted extraction 재사용용으로 공개 함수화)
# ---------------------------------------------------------------------------

def combine_multipage_boxes(pages_boxes: list[list[OcrBox]], y_margin: float = 100000.0) -> list[OcrBox]:
    """여러 페이지의 OcrBox 리스트를 하나로 합친다.

    각 페이지는 y=0 부터 시작하는 독립된 좌표계를 쓰므로, 그냥 이어붙이면 서로 다른
    페이지의 행이 같은 y 범위에서 섞여버린다(예: 1페이지 상단 행과 2페이지 상단 행이
    같은 row로 잘못 클러스터링됨). 페이지마다 y를 큰 값(y_margin)만큼 누적으로
    띄워서 절대 겹치지 않게 만든다.
    """
    combined = []
    offset = 0.0
    for boxes in pages_boxes:
        for b in boxes:
            shifted = OcrBox(text=b.text, bbox=[[x, y + offset] for x, y in b.bbox], confidence=b.confidence)
            combined.append(shifted)
        offset += y_margin
    return combined


def cluster_rows(boxes: list[OcrBox], row_gap: float = 18.0) -> list[list[OcrBox]]:
    """y좌표 기준으로 같은 행에 속한다고 판단되는 박스들을 묶는다.
    각 행 내부는 x좌표 순으로 정렬해서 반환한다 (왼쪽→오른쪽 읽기 순서)."""
    if not boxes:
        return []
    ys = [b.y_center for b in boxes]
    clusters = _cluster_1d(ys, row_gap)
    rows = []
    for cluster in clusters:
        row_boxes = sorted((boxes[i] for i in cluster), key=lambda b: b.x_center)
        rows.append(row_boxes)
    rows.sort(key=lambda r: sum(b.y_center for b in r) / len(r))
    return rows


# ---------------------------------------------------------------------------
# 4. 행/열 구조 복원 (best-effort, bounding box 좌표 클러스터링)
# ---------------------------------------------------------------------------

def _cluster_1d(values: list[float], gap: float) -> list[list[int]]:
    """정렬된 값들을 gap 이상 벌어지면 새 클러스터로 나눈다. 인덱스 리스트를 반환."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    clusters: list[list[int]] = []
    for idx in order:
        v = values[idx]
        if clusters and v - values[clusters[-1][-1]] <= gap:
            clusters[-1].append(idx)
        else:
            clusters.append([idx])
    return clusters


def reconstruct_grid(boxes: list[OcrBox], row_gap: float = 18.0, col_gap: float = 40.0) -> dict:
    """bounding box 좌표만으로 행/열 그리드 복원을 시도한다.

    반환값:
        {
          "rows": [[cell_text, ...], ...],   # 열 인덱스 기준 정렬된 행별 텍스트
          "n_cols_detected": int,
          "row_count_consistency": float,    # 0~1, 대부분의 행이 동일한 셀 개수를 가지는 비율
          "status": "ok" | "manual_review",
        }

    표마다 레이아웃이 다르므로 이 복원 결과는 참고용이며, 신뢰도가 낮으면
    status="manual_review" 로 표시하고 raw OCR 결과를 그대로 보존해야 한다.
    """
    if not boxes:
        return {"rows": [], "n_cols_detected": 0, "row_count_consistency": 0.0, "status": "manual_review"}

    # 1) y 좌표로 행 클러스터링
    ys = [b.y_center for b in boxes]
    row_clusters = _cluster_1d(ys, row_gap)

    rows_raw = []
    for cluster in row_clusters:
        cluster_boxes = sorted((boxes[i] for i in cluster), key=lambda b: b.x_center)
        rows_raw.append(cluster_boxes)

    # 2) 가장 셀 개수가 많은 행을 기준으로 열 중심 좌표 추정 (헤더/사례수 행일 가능성이 높음)
    header_row = max(rows_raw, key=len)
    col_centers = [b.x_center for b in header_row]

    def nearest_col(x):
        return min(range(len(col_centers)), key=lambda i: abs(col_centers[i] - x))

    grid = []
    for row_boxes in rows_raw:
        row_cells = [""] * len(col_centers)
        for b in row_boxes:
            ci = nearest_col(b.x_center)
            row_cells[ci] = (row_cells[ci] + " " + b.text).strip() if row_cells[ci] else b.text
        grid.append(row_cells)

    # 3) 신뢰도 평가: 각 행의 non-empty 셀 개수가 header와 얼마나 비슷한지
    target_len = len(col_centers)
    consistent = sum(1 for r in grid if sum(1 for c in r if c) >= max(1, target_len - 2))
    consistency = consistent / len(grid) if grid else 0.0

    status = "ok" if consistency >= 0.6 and target_len >= 3 else "manual_review"

    return {
        "rows": grid,
        "n_cols_detected": target_len,
        "row_count_consistency": round(consistency, 3),
        "status": status,
    }


def save_extracted(grid_result: dict, country: str, table_index: str, page_num: int,
                    extra: Optional[dict] = None) -> str:
    fname = f"{country}_1-{table_index}_p{page_num}_extracted.json"
    path = os.path.join(EXTRACTED_DIR, fname)
    payload = {
        "country": country,
        "table_id": f"1-{table_index}",
        "page": page_num,
        "extraction_method": "easyocr+bbox_grid_reconstruction",
        **grid_result,
    }
    if extra:
        payload.update(extra)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return path
