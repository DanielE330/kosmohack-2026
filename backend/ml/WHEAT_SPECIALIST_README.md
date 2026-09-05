# Wheat specialist — отдельный эксперимент

Дополнение не изменяет существующие `src/modeling.py`, `src/train.py` и
`src/inference.py`.

## Куда скопировать файлы

- `src/wheat_specialist.py` → в папку `src/` проекта;
- `src/train_wheat_experiment.py` → в папку `src/` проекта;
- `src/inference_ensemble.py` → в папку `src/` проекта.

## Запуск

Сначала должна быть обучена исходная global-модель и создан её OOF:

```bash
python src/train.py
```

Запуск честной проверки и обучение wheat specialist:

```bash
python src/train_wheat_experiment.py
```

Смотри две главные строки:

```text
Global OOF RMSE
Ensemble OOF RMSE
```

Ансамбль полезен, только если `Ensemble OOF RMSE` меньше. Дополнительно проверь,
что улучшились хотя бы 4 из 5 фолдов в
`reports/wheat_validation_metrics.json`.

Создание отдельного файла для отправки на платформу:

```bash
python src/inference_ensemble.py
```

Результат:

```text
submission_wheat_ensemble.csv
```

В нём используется ожидаемая живым валидатором колонка
`primary_ndvi_true`.

## Создаваемые файлы

```text
models/wheat_gap_model.joblib
reports/wheat_validation_metrics.json
reports/wheat_oof_predictions.csv
submission_wheat_ensemble.csv
```

Если лучший `wheat_blend_weight` оказался равен нулю, эксперимент не дал
улучшения. Это нормальный результат: submission тогда остаётся равен прогнозу
глобальной модели.
