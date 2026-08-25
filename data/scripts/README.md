# PDF 표 원수치 추출 파이프라인 (샘플 검증 단계)

## 목적

`2026 해외한류실태조사_통계.pdf` (1,866페이지)에서 국가별 핵심 표의 실제 원수치를
자동으로 추출할 수 있는지, 3개국(중국/미국/베트남) x 4개 표 샘플로 먼저 검증한다.

**이 단계에서는 30개국 전체를 추출하지 않는다.** 샘플 검증 결과를 보고 자동화
가능 여부를 판단하는 것이 목적이다.

## 전제 조건 (이미 완료됨, 재사용)

- `data/processed/country_table_page_map.csv` / `.json`: 국가 x 표 x 페이지 매핑
  (러닝풋터 `[표 X-Y]`를 숫자암호로 해독해 전수 검증 완료, 403개 조합 NOT_FOUND 0건)
- 이 스크립트들은 위 매핑을 그대로 읽어서 쓸 뿐, 페이지 매핑 로직을 다시 구현하지 않는다.

## 파일 구성

- `pdf_table_extractor.py` : 핵심 함수 모음 (페이지 조회 / 렌더링 / OCR / 그리드 복원)
- `run_sample_extraction.py` : 샘플 12개 국가-표 조합 실행 스크립트 (렌더링 + OCR + 구조복원 시도)
- `verify_sample.py` : OCR raw 결과를 사람이 직접 읽은 정답값과 대조하는 검증 스크립트
- `build_sample_key_values.py` : 검증 완료된 핵심 수치만 모아 표준 스키마 CSV로 저장

## 실행 방법 (순서대로)

```bash
cd data/scripts
python run_sample_extraction.py     # 1) 렌더링 + OCR + 구조복원 시도
python verify_sample.py             # 2) 정답값과 OCR raw 대조
python build_sample_key_values.py   # 3) 검증된 값만 모은 최종 샘플 CSV 생성
```

## 출력물

| 위치 | 내용 |
|---|---|
| `data/processed/page_images/{국가}_1-{표}_p{페이지}.png` | 렌더링된 원본 페이지 이미지 (200dpi) |
| `data/processed/ocr_raw/{국가}_1-{표}_p{페이지}_ocr_raw.json` | EasyOCR 원본 결과 (text, bbox, confidence) — 가공하지 않은 그대로 |
| `data/processed/extracted/{국가}_1-{표}_p{페이지}_extracted.json` | bounding box 기반 행/열 그리드 복원 시도 결과 + `status`(ok/manual_review) |
| `data/processed/extracted/sample_extraction_manifest.json` | 이번 실행 전체 요약 (어떤 페이지가 어떤 상태로 처리됐는지) |
| `data/processed/verification/sample_verification.csv` | 사람이 원본 이미지와 대조한 검증 결과 (숫자 31건: exact_match 28 / found_as_substring 3, 불일치 0) |
| `data/processed/extracted/sample_key_values.csv` | 검증 완료된 핵심 수치만 모은 최종 표 (country/table_id/page/category/item/value/unit/base/...) |

## 30개국 전체 추출 (2단계, 2026-08-25)

3개국 샘플 검증 이후, 같은 방식(라벨 타겟 추출)을 30개국 전체로 확장했다.

### 실행 방법

```bash
cd data/scripts
python run_full_extraction.py    # 30개국 x 4개 표(1-16,1-33,1-35,1-41) 전체 추출
```

`targeted_extract.py`(표별 추출 함수) + `anomaly_checks.py`(자동 이상치 탐지)를 사용한다.
`pdf_table_extractor.py`의 `get_ocr_for_page()`가 이미 OCR한 페이지(3개국 샘플)는
캐시를 재사용하고, 나머지 27개국만 새로 렌더링+OCR 한다.

### 산출물

| 파일 | 내용 |
|---|---|
| `data/processed/extracted/all_countries_key_values.csv` / `.json` | 30개국 x 4개 표 전체 원수치 (810행) |
| `data/processed/extracted/full_extraction_manifest.json` | 국가x표별 성공/이슈/소요시간, 중복·BASE 일관성 검사 결과 |
| `data/processed/verification/manual_review_list.csv` | 자동 이상치 탐지에 걸린 값만 모은 목록 |
| `data/processed/ocr_raw/`, `page_images/` | 30개국분 OCR 원본 + 렌더링 이미지 (기존과 동일 형식으로 누적) |

### 결과 요약

- 총 810개 값 (30개국 x [1-16: 13개 콘텐츠 카테고리 + 1-33: 6개 블록 + 1-35: 6개 항목 + 1-41: 2개 항목])
- `auto_extracted` 809건 / `manual_review` 1건 (필리핀 1-16 패션 항목, OCR이 "4.17"을 "417"로 소수점 누락 — 자동 검증이 정확히 탐지함, 원본 대조로 실제값 4.17 확인됨. **CSV 값 자체는 고치지 않고 manual_review로만 표시**)
- 중복 탐지 0건, BASE 불일치 0건 (최초 실행 시 중복 30건이 나왔으나 이는 검증 스크립트의 키 이름 버그였고, 실제 데이터 문제가 아니었음 — 수정 후 재검사 완료)
- 표본 3개국(중국/미국/베트남) 외 4개국(일본/브라질/사우디아라비아/남아프리카공화국)을 무작위로 추가 선정해 원본 PDF와 전수 대조 → 전부 정확히 일치

### 개발 중 발견/수정한 버그 (기록용)

1. **행 클러스터링 과병합**: row_gap=18px였을 때 세로 병합 카테고리 라벨("본인/관심도/변화" 등 여러 줄)이 인접한 데이터 행들을 하나의 거대한 행으로 잘못 묶어 값이 완전히 틀어짐. row_gap=10px로 낮춰서 해결.
2. **다중 페이지 좌표 충돌**: 표1-16처럼 2페이지에 걸친 표를 합칠 때 각 페이지가 y=0부터 시작하는 별도 좌표계라 서로 다른 페이지의 행이 섞였음. 페이지마다 큰 offset을 더해서 해결(`combine_multipage_boxes`).
3. **같은 페이지에 다른 표가 있을 때 라벨 혼선**: 표1-35(인식변화) 페이지에 표1-34(유료이용의향)가 함께 인쇄되어 있어, "5점 척도 평균" 첫 번째 매칭을 그냥 쓰면 다른 표의 값을 가져오는 버그가 있었음(3개국 모두 재현됨). 1-35 고유 항목(①~⑤ "...변함") 행 이후의 occurrence만 쓰도록 수정.
4. **라벨이 여러 박스로 쪼개짐**: "매우" + "긍정적으로 변함"처럼 OCR이 한 라벨을 여러 박스로 나눠 인식하는 경우, 정확히 일치하는 박스가 없어 항목을 못 찾는 문제. 라벨 조각(fragment) 매칭으로 완화.

## 현재까지 확인된 사실 (2026-08-25 샘플 검증 결과)

- 표 구조(행/열) 자동 복원: **15/15 페이지 모두 `manual_review`**로 표시됨 —
  bounding box 기반 열 클러스터링만으로는 이 표들(다중 블록, 병합 셀, 원문자 등)의
  행/열을 안정적으로 복원하지 못했다. 억지로 맞추지 않고 정직하게 flag한 것이며,
  raw OCR(text+bbox+confidence)은 100% 보존되어 있다.
- 반면 **특정 셀 값을 좌표/키워드로 지목해서 읽는 방식**(예: "한국 관광" 행의 오른쪽
  숫자, "전반적 만족도" 블록의 5점 척도 평균)은 31/31 검증 항목에서 전부 정확했다.
- 따라서 현재 파이프라인은 "표 전체를 통째로 자동 복원"하는 데는 아직 부족하지만,
  "필요한 특정 지표 값을 타겟팅해서 뽑는" 용도로는 이미 신뢰할 수 있는 수준이다.

## 설계 원칙 (AGENTS.md 준수)

- 원본 PDF는 `pymupdf.open()`으로 읽기만 하며 저장하지 않는다.
- OCR 결과를 사실로 간주하지 않는다 — `verification/` 폴더에 사람이 원본 이미지와
  직접 대조한 결과를 별도로 남긴다.
- 표 구조 복원이 불안정한 경우(`status=manual_review`) 억지로 행/열을 맞추지 않고
  raw OCR 텍스트를 그대로 보존한다.
- 값을 추정/보간하지 않는다. OCR이 못 읽은 셀은 빈 문자열로 남긴다.
