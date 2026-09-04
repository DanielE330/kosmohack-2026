# ExtraTrees ensemble v2

Этот вариант не заменяет текущие global и wheat модели. Он добавляет третью
модель, которая предсказывает residual другим способом, и смешивает прогнозы:

```text
70% (global HGB + wheat specialist) + 30% ExtraTrees
```

Скопируй файлы в уже реорганизованный проект:

```text
src/extra_trees_model.py
scripts/train_extra_trees.py
scripts/predict_ensemble_v2.py
```

До запуска должны существовать:

```text
models/gap_model.joblib
models/wheat_gap_model.joblib
reports/wheat_oof_predictions.csv
```

Запуск из корня проекта:

```bash
python scripts/train_extra_trees.py
python scripts/predict_ensemble_v2.py
```

Первый скрипт честно повторяет GroupKFold и затем создаёт:

```text
models/extra_trees_gap_model.joblib
reports/extra_trees_validation_metrics.json
reports/extra_trees_oof_predictions.csv
```

Второй создаёт готовый для платформы файл:

```text
submission_ensemble_v2.csv
```

Контрольные OOF-значения:

```text
Текущий HGB ensemble: 0.063122
Новый ensemble:       0.062646
Улучшено фолдов:      5/5
ExtraTrees weight:    0.30
```

ExtraTrees обучается заметно дольше HGB. На машине с небольшим количеством
ядер GroupKFold может занять несколько минут.
