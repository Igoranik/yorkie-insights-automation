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

## GitHub Actions
В `.github/workflows/insights.yml` готово расписание автоматического запуска.
Добавьте secrets:
- META_ACCESS_TOKEN
- IG_USER_ID

Текущие cron-времена соответствуют примерно 08:00, 11:00, 14:00 и 16:00 CEST.
