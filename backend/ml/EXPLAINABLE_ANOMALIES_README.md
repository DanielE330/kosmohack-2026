# Обновление интерпретации аномалий

Эта сборка исправляет ложную трактовку погоды. Раньше температура сравнивалась
с другими датами того же месяца в одном запросе, поэтому обычный тёплый день
октября мог называться температурным стрессом.

Теперь отдельно возвращаются:

- `anomaly_status`, `z_score`, `anomaly_confidence` — наличие и сила аномалии;
- `anomaly_cause` — машинный код вероятной причины;
- `cause_confidence` — уверенность именно в причине;
- `cause_evidence` — числа, на которых основана гипотеза;
- `requires_review` — признак обязательной ручной проверки.

Поддерживаемые причины: `heat_and_drought`, `moisture_deficit`, `heat_stress`,
`cold_stress`, `possible_harvest`, `weather_or_harvest`, `sensor_conflict`,
`unconfirmed`.

## Проверка

Из корня проекта:

```bash
export EARTHENGINE_PROJECT="fluent-century-446709-i9"
python -m uvicorn webapp.main:app --host 127.0.0.1 --port 8770
```

Во втором терминале:

```bash
curl -fS -X POST \
  http://127.0.0.1:8770/analyze \
  -H "Content-Type: application/json" \
  --data @examples/analyze_request.json \
  --output reports/live_result_explainable.json

jq '.summary, .anomaly_periods' reports/live_result_explainable.json
```

В `summary` должны присутствовать `measured_anomaly_points` и
`periods_requiring_review`. В каждом периоде должны присутствовать `cause`,
`cause_confidence` и `requires_review`.

## Отображение во Flutter

Показывайте `severity` как уровень отклонения, `reason` как гипотезу,
`cause_confidence` как уверенность в гипотезе. При `requires_review=true`
добавляйте заметную подпись «Требуется проверка специалистом». Не подписывайте
гипотезу как установленный диагноз.
