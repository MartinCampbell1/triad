# Triad.app — Порядок исправлений

## Проблемы
1. Proxy не стартует с приложением (Python path не найден Electron'ом)
2. Floating widget не нужен — модели должны быть в нативном dropdown "GPT-5.4 ▾"
3. Нужно добавить endpoint `/api/models` который вернёт Claude/Codex/Gemini модели
4. Proxy должен маппить выбранную модель на провайдера

## Порядок действий

### Шаг 1: Proxy — добавить endpoint listModels
Codex app вызывает `listModels()` через AppServerManager.
Proxy должен вернуть наши модели в формате:
```json
[
  {"model": "claude-opus-4-6", "hidden": false, "isDefault": true, "supportedReasoningEfforts": [...]},
  {"model": "claude-sonnet-4-6", "hidden": false, ...},
  {"model": "codex-mini-latest", "hidden": false, ...},
  {"model": "gemini-3.1-pro", "hidden": false, ...}
]
```

### Шаг 2: Proxy — маппинг модель → провайдер
Когда приходит запрос с `model: "claude-opus-4-6"`, proxy определяет провайдера:
- claude-* → Claude adapter
- codex-* / gpt-* → Codex adapter  
- gemini-* → Gemini adapter

### Шаг 3: Убрать floating widget из injection
Заменить на ничего — нативный dropdown покроет.

### Шаг 4: Починить proxy auto-start
Проблема: Electron не находит Python. Решение: записать абсолютный путь в конфиг при build.

### Шаг 5: Пересобрать и протестировать
