"""Технический batch-инференс, требуемый ТЗ отдельно от веб-сервиса.

Принимает `private_features.csv`, восстанавливает `primary_ndvi` для строк с
`is_synthetic_gap=True` и пишет `submission.csv` в формате
`anon_polygon_id,date,primary_ndvi_pred` (см. `tasks/backend.md`, п.2).
Не поднимает веб-сервис и не трогает БД — использует ту же baseline-функцию
восстановления, что и веб-API (`app/services/gapfill.interpolate`), чтобы не
дублировать логику; замените её на финальную ML-модель без изменения этого
файла.

Запуск (из backend/):
    python -m inference.run_inference --input private_features.csv --output submission.csv
"""

from __future__ import annotations

import argparse

import pandas as pd

from app.services.gapfill import interpolate


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Путь к private_features.csv")
    parser.add_argument("--output", default="submission.csv", help="Путь для submission.csv")
    return parser.parse_args()


def run(input_path: str, output_path: str) -> None:
    df = pd.read_csv(input_path)
    df["date"] = pd.to_datetime(df["date"]).dt.date

    if "is_synthetic_gap" not in df.columns:
        raise ValueError(
            "В private_features.csv нет колонки is_synthetic_gap — уточните у "
            "организаторов её точное имя (см. tasks/backend.md, п.1)"
        )

    rows: list[dict[str, object]] = []
    for polygon_id, group in df.sort_values("date").groupby("anon_polygon_id"):
        group = group.reset_index(drop=True)
        dates = list(group["date"])
        values = [None if pd.isna(v) else float(v) for v in group["primary_ndvi"]]
        predicted = interpolate(dates, values)

        for i, is_gap in enumerate(group["is_synthetic_gap"]):
            if bool(is_gap):
                rows.append(
                    {
                        "anon_polygon_id": polygon_id,
                        "date": dates[i].isoformat(),
                        "primary_ndvi_pred": round(predicted[i], 6),
                    }
                )

    submission = pd.DataFrame(rows, columns=["anon_polygon_id", "date", "primary_ndvi_pred"])
    submission = submission.drop_duplicates(subset=["anon_polygon_id", "date"])
    submission.to_csv(output_path, index=False, encoding="utf-8")
    print(f"Готово: {len(submission)} строк -> {output_path}")


if __name__ == "__main__":
    args = parse_args()
    run(args.input, args.output)
