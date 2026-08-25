"""
tables_17_18_37_key_values.csv의 item 라벨을 정정한다.

같은 항목(예: "드라마" 카테고리의 "배우의 외모가 매력적이어서")이 30개국에 걸쳐
반복되는데, OCR 잡음 때문에 국가마다 조금씩 다른 텍스트로 인식된 경우가 많다
(예: "배우의 외모가 매력적이어서" 51회, 같은 항목의 오타 변형들이 소수씩 흩어져 있음).

접근 방식: (table_id, content_category) 단위로 모든 라벨 변형을 모아서, 기존
targeted_extract.py의 라벨 유사도 판정 함수(_labels_match, 접미사+Levenshtein)로
같은 항목끼리 묶고, 각 묶음에서 **가장 많이 등장한 변형을 정답 라벨**로 채택한다.
값을 추정/변경하지 않는다 - 오직 라벨 텍스트만 정정하고, value/base/verification_status는
그대로 둔다. 원본 라벨은 raw_item 컬럼에 보존한다(삭제하지 않음).
"""
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "data" / "scripts"))
from targeted_extract import _labels_match  # noqa: E402

IN_CSV = REPO_ROOT / "data" / "processed" / "extracted" / "tables_17_18_37_key_values.csv"
OUT_CSV = REPO_ROOT / "data" / "processed" / "extracted" / "tables_17_18_37_key_values_clean.csv"
OUT_MAPPING = REPO_ROOT / "data" / "processed" / "extracted" / "label_cleaning_mapping.csv"


def cluster_labels(label_counts: Counter) -> dict[str, str]:
    """빈도 내림차순으로 라벨을 순회하며, 이미 만들어진 클러스터 대표 라벨과
    매칭되면 합치고, 아니면 새 클러스터를 만든다. 가장 빈도 높은 라벨이 그
    클러스터의 대표(정답) 라벨이 된다."""
    labels_by_freq = [lbl for lbl, _ in label_counts.most_common()]
    representatives: list[str] = []
    mapping: dict[str, str] = {}

    for label in labels_by_freq:
        matched_rep = None
        for rep in representatives:
            if _labels_match(rep, label):
                matched_rep = rep
                break
        if matched_rep is None:
            representatives.append(label)
            mapping[label] = label
        else:
            mapping[label] = matched_rep
    return mapping


def main():
    df = pd.read_csv(IN_CSV, encoding="utf-8-sig")
    df["raw_item"] = df["item"]

    group_cols = ["table_id", "content_category"]
    mapping_rows = []

    for (table_id, category), group in df.groupby(group_cols, dropna=False):
        counts = Counter(group["item"])
        mapping = cluster_labels(counts)
        df.loc[group.index, "item"] = group["item"].map(mapping)
        for raw, canonical in mapping.items():
            if raw != canonical:
                mapping_rows.append({
                    "table_id": table_id, "content_category": category,
                    "raw_item": raw, "canonical_item": canonical, "count": counts[raw],
                })

    # 라벨 신뢰도: 같은 (table_id, content_category, item) 조합이 몇 개 행에 등장하는지로
    # 판단한다. 30개국 x 최대 2개 rank_group = 최대 60건 중, 20건 이상 등장하면
    # "여러 국가에서 반복 확인된 항목"으로 보고 high_confidence, 그 밑은 low_confidence
    # (심하게 깨진 OCR 잔여물일 가능성이 높음 - 값은 보존하되 라벨을 신뢰하지 말라는 신호).
    item_counts = df.groupby(group_cols + ["item"], dropna=False)["item"].transform("count")
    df["label_confidence"] = pd.Series(
        ["high_confidence" if c >= 20 else "low_confidence" for c in item_counts],
        index=df.index,
    )

    df.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
    pd.DataFrame(mapping_rows).sort_values(["table_id", "content_category", "count"], ascending=[True, True, False]) \
        .to_csv(OUT_MAPPING, index=False, encoding="utf-8-sig")

    print(f"저장: {OUT_CSV}")
    print(f"저장: {OUT_MAPPING} ({len(mapping_rows)}건 라벨 변형이 정규화됨)")

    for table_id in df["table_id"].unique():
        n_before = df[df["table_id"] == table_id]["raw_item"].nunique()
        n_after = df[df["table_id"] == table_id]["item"].nunique()
        print(f"{table_id}: 라벨 종류 {n_before} -> {n_after}")


if __name__ == "__main__":
    main()
