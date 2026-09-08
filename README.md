# Yorkie Insights Automation

Готовый сборщик Instagram Reels Insights для `kinematische_kette`.

Собирает: reach, views, likes, comments, saved, shares, average watch time,
total watch time и reels_skip_rate.

## Безопасность
Используйте новый access token. Не храните токен в коде и не показывайте его на скриншотах.
Передавайте его только через переменную окружения `META_ACCESS_TOKEN`.

## Запуск
```bash
python collector.py
```

Результаты сохраняются в папку `data/` как JSON и CSV.

## Read-only endpoint

После каждого сбора `analyzer.py` выбирает новейший JSON-снимок по UTC-метке в
имени файла и публикует очищенную копию:

`docs/api/insights/latest.json`

Публичный GET URL после включения GitHub Pages:

`https://igoranik.github.io/yorkie-insights-automation/api/insights/latest.json`

Резервный raw GET URL:

`https://raw.githubusercontent.com/Igoranik/yorkie-insights-automation/main/docs/api/insights/latest.json`

Формат ответа:

- `schema_version` — версия схемы endpoint;
- `generated_at` — UTC-время исходного снимка;
- `reels_count` — количество Reels в снимке;
- `items` — массив метрик Reels.

Endpoint статический: он поддерживает только чтение. В публичный JSON попадают
только поля из явного списка. Внутренние `*_error`, токены и неизвестные поля
отбрасываются.

Для ручной пересборки endpoint из уже собранных данных:

```bash
python endpoint.py
```

Для запуска тестов:

```bash
python -m unittest discover -s tests -v
```

## GitHub Actions
В `.github/workflows/insights.yml` готово расписание автоматического запуска.
Добавьте secrets:
- META_ACCESS_TOKEN
- IG_USER_ID

Текущие cron-времена соответствуют примерно 08:00, 11:00, 14:00 и 16:00 CEST.

Для первой публикации откройте `Settings → Pages` и выберите источник `GitHub Actions`,
затем запустите workflow `Yorkie Instagram Insights` вручную или дождитесь ближайшего
запланированного запуска.
