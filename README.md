# CAPM / VaR / ES (учебный проект)

См. [SOLUTION.md](./SOLUTION.md) — продуктовая архитектура.

## Стек

- **Бэкенд:** Python 3.11+, FastAPI, Uvicorn.
- **Фронтенд:** Vite 6 + React 19 + TypeScript.

## Что установить локально

1. **Python** 3.11 или новее (`python3 --version`).
2. **Node.js** 20 LTS или новее (`node --version`, `npm --version`).

## Запуск (два терминала)

### Терминал 1 — API

```bash
cd /Users/Alex/dev/ml/curr/curr/capm-var-proj/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Проверка: откройте в браузере [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health) — должен быть JSON `{"status":"ok"}`.

### API (фазы 0–3)

- `POST /api/portfolio/analyze` — см. OpenAPI ([/docs](http://127.0.0.1:8000/docs)). По умолчанию: **MOEX ISS** (TQBR + индекс), кэш SQLite в `data/moex_cache.sqlite`, расчёт **β** (OLS к индексу), **VaR/ES** по исторической портфельной доходности, в ответе **chart** для графика. Поле **`use_mock`: true** — старый демо-ответ без сети.
- `GET /api/instruments/resolve?ticker=SBER` — проверка наличия тикера в истории **TQBR** через MOEX.
- `GET /api/news?tickers=SBER,GAZP&days=10` — новости по тикерам за **последние N календарных дней** (по умолчанию источник — RSS Google News; при **`NEWS_API_KEY`** пробуется NewsAPI.org с откатом на RSS).

Тесты: из `backend` выполнить `python -m pytest tests/ -q` (при недоступности MOEX тест `resolve` помечается как skipped).

Переменная **`MOEX_ISS_USER_AGENT`** (см. `.env.example`) задаёт заголовок для запросов к MOEX; при отсутствии используется значение по умолчанию в коде.

Если после добавления тикера «пропадают» общие даты или ошибка про «слишком мало дней», удалите файл **`data/moex_cache.sqlite`** и пересчитайте (старый кэш мог собраться с некорректной склейкой сессий MOEX).

**Тикеры без длинной истории на TQBR:** приложение берёт только доску **TQBR**. Если бумагу сняли с режима или история обрывается (в справочнике MOEX у **TCSG** на TQBR последняя дата около **27.11.2024**), длинное окно вместе с ликвидными SBER/GAZP даст мало общих дней — это не баг расчёта, а отсутствие котировок на выбранной доске после даты делистинга/перевода.

### Терминал 2 — фронтенд

```bash
cd /Users/Alex/dev/ml/curr/curr/capm-var-proj/frontend
npm install
npm run dev
```

Откройте [http://localhost:5173](http://localhost:5173). Запросы на `/api/...` Vite **проксирует** на `http://127.0.0.1:8000`. В коде используется `apiUrl("/api/...")` (см. `frontend/src/apiBase.ts`): локально база пустая, в проде можно задать `VITE_API_BASE_URL`).

## Переменные окружения

Шаблон имён — в [.env.example](./.env.example). Скопируйте в **`backend/.env`** или **корень проекта**; при старте подгружаются оба пути (`load_dotenv` в `app.main`). Секреты в git не коммитятся.

## Сборка фронта для продакшена

```bash
cd frontend && npm run build
```

Перед `vite build` скрипт генерирует `frontend/public/_redirects` для Netlify (файл в `.gitignore`). Статика — в `frontend/dist/`. Раздачу с того же хоста, что и FastAPI, можно настроить отдельно (`StaticFiles` или nginx).

## Деплой фронтенда на Netlify

**Важно:** Netlify отдаёт только **статику** из `frontend/dist`. **FastAPI нужно запустить отдельно** (Railway, Render, Fly.io, VPS и т.п.) с публичным HTTPS-URL. В репозитории лежит [`netlify.toml`](./netlify.toml): каталог сборки `frontend`, команда `npm ci && npm run build`, публикация `dist`, Node 20.

### Что сделать в Netlify

1. **Подключить репозиторий** (GitHub/GitLab/Bitbucket) и создать сайт. Netlify подхватит `netlify.toml` из корня — менять root/base вручную обычно не нужно.
2. **Переменные окружения (Build environment)** — один из двух вариантов API:

   **Вариант A — прокси `/api` через Netlify** (запросы из браузера идут на тот же origin, отдельный CORS для API не нужен):

   - `NETLIFY_API_ORIGIN` — URL бэкенда **без** завершающего слэша, например `https://capm-api-xxxx.up.railway.app`.
   - При сборке в `public/_redirects` попадёт правило `/api/* → …/api/:splat` и fallback для SPA.

   **Вариант B — прямой вызов API из браузера:**

   - `VITE_API_BASE_URL` — тот же базовый URL API (без `/` в конце).
   - На бэкенде задайте **`ALLOW_ORIGINS`** — список origin фронта через запятую, например `https://your-app.netlify.app` (и кастомный домен при необходимости).

3. **Задеплойте бэкенд** отдельно: `uvicorn app.main:app --host 0.0.0.0 --port $PORT` (или Docker), переменные из `.env.example`; для варианта B обязательно `ALLOW_ORIGINS`.
4. **Проверка:** после деплоя откройте сайт Netlify — статус API должен стать `ok`, затем расчёт портфеля без mock.

**Замечания:** у прокси Netlify есть лимиты на бесплатном плане; при большой нагрузке удобнее вариант B. Файл кэша SQLite на бэкенде в среде без постоянного диска может не переживать перезапуски — для стабильного кэша нужен том или внешняя БД.

## Деплой на VPS (DigitalOcean Droplet и аналоги)

Один сервер отдаёт и **API**, и **собранный фронт**: после `npm run build` каталог `frontend/dist` подхватывается FastAPI (`StaticFiles`), если он существует. Достаточно **одного** процесса Uvicorn за reverse proxy (nginx) на портах 80/443.

Ниже — схема для **Ubuntu 24.04**, пользователь с sudo, репозиторий уже в Git (GitHub и т.д.). IP в примере замените на свой (например `64.226.116.2`).

### 1. Зайти по SSH и базовая защита

```bash
ssh root@ВАШ_IP
apt update && apt upgrade -y
apt install -y ufw
ufw allow OpenSSH
ufw enable
```

### 2. Зависимости: Python, Node (для сборки фронта), nginx, git

```bash
apt install -y python3-venv python3-pip git nginx curl
# Node 20 LTS (через NodeSource; либо поставьте версию из репозитория, если ≥ 20)
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt install -y nodejs
```

На **512 MB RAM** сборка `npm ci` на сервере может упираться в память: тогда соберите фронт **на своём ПК** (`cd frontend && npm run build`) и скопируйте на сервер только каталог `frontend/dist` (например `rsync -avz frontend/dist/ root@ВАШ_IP:/opt/capm-var-proj/frontend/dist/`).

### 3. Клонировать проект и окружение

```bash
cd /opt
git clone https://github.com/ВАШ_ЛОГИН/capm-var-proj.git
cd capm-var-proj
python3 -m venv backend/.venv
backend/.venv/bin/pip install -r backend/requirements.txt
```

Создайте **`backend/.env`** по образцу `.env.example` (хотя бы `MOEX_ISS_USER_AGENT=…` с контактом). Каталог под кэш:

```bash
mkdir -p data
chown -R www-data:www-data data   # если будете запускать от www-data; иначе оставьте владельца тем пользователем, от которого стартует uvicorn
```

### 4. Сборка фронтенда

Из корня репозитория (на сервере, если хватает RAM):

```bash
cd frontend
npm ci
# без NETLIFY_API_ORIGIN — в _redirects только SPA-fallback; для одного хоста это нормально
npm run build
cd ..
```

Убедитесь, что появился **`frontend/dist`**. Для **одного происхождения** (браузер и `/api` с одного домена/IP) **не задавайте** `VITE_API_BASE_URL` — запросы останутся относительными `/api/...`.

### 5. Systemd: Uvicorn на localhost

Файл `/etc/systemd/system/capm-var.service`:

```ini
[Unit]
Description=CAPM VaR API + static
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/opt/capm-var-proj/backend
EnvironmentFile=/opt/capm-var-proj/backend/.env
ExecStart=/opt/capm-var-proj/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```bash
systemctl daemon-reload
systemctl enable --now capm-var.service
systemctl status capm-var.service
curl -sS http://127.0.0.1:8000/api/health
```

Права для `User=www-data`: выдать владение деревом проекта и `data/`, например  
`chown -R www-data:www-data /opt/capm-var-proj` (или создайте отдельного пользователя `capm` вместо `www-data`).

### 6. Nginx: порт 80 → прокси на Uvicorn

Файл `/etc/nginx/sites-available/capm-var` (замените `server_name` на домен или оставьте `_` для проверки по IP):

```nginx
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
ln -sf /etc/nginx/sites-available/capm-var /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx
ufw allow 'Nginx Full'
```

Откройте в браузере `http://ВАШ_IP/` — интерфейс; `http://ВАШ_IP/api/health` — `{"status":"ok"}`.

### 7. HTTPS и домен (по желанию)

Привяжите **A-запись** домена к IP Droplet, в `server_name` укажите домен, затем например **Certbot** (`certbot --nginx`) для Let’s Encrypt.

### VPN на том же Droplet

WireGuard/OpenVPN ставятся отдельно; следите за **RAM** (512 MB для веба + VPN уже плотно). Закройте лишние порты в **ufw**, оставьте только нужные (SSH, 80/443, порт VPN).
