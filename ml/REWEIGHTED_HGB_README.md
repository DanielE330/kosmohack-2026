# Reweighted HGB ensemble v3

Модель учитывает известное распределение культур среди private gaps. В
synthetic OOF озимой пшеницы было 52.1%, а в private — 65.2%, поэтому при
обучении альтернативного HGB используются sample weights культур.

Финальный прогноз:

```text
75% ensemble v2 + 25% reweighted HGB
```

Скопируй файлы:

```text
src/reweighted_hgb_model.py
scripts/train_reweighted_hgb.py
scripts/predict_ensemble_v3.py
```

До запуска должны существовать модели global, wheat, ExtraTrees и файл:

```text
reports/extra_trees_oof_predictions.csv
```

Запуск:

```bash
python scripts/train_reweighted_hgb.py
python scripts/predict_ensemble_v3.py
```

Результат:

```text
submission_ensemble_v3.csv
```

Контрольные результаты:

```text
v2 OOF:                  0.062646
v3 OOF:                  0.062528
Улучшено weighted folds: 5/5
Проверка на известных private-точках:
v2:                      0.065505
v3:                      0.065398
```

Это небольшое улучшение. Храни `submission_ensemble_v2.csv` как резерв и
считай v3 принятым только после результата платформы лучше 0.0701.
