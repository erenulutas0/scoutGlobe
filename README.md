# ScoutGlobe

Futbolcu istatistiklerini toplayan, kulüp ihtiyacına göre **transfer önerisi** üreten ve
**future-star** adaylarını erken tespit etmeyi hedefleyen platform. Arayüzün merkezi,
uzaydan bakılan interaktif 3D dünya: ülkeye tıkla → lige in → oyuncuyu keşfet.

> Mimari kararlar `docs/ARCHITECTURE.md`, görev listesi `docs/TODO.md`,
> veri kaynakları `docs/DATA_SOURCES.md`, görsel yön `docs/DESIGN.md` dosyalarındadır.

## Gereksinimler

| Araç | Sürüm | Not |
|---|---|---|
| Node | ≥ 20.9 | `pnpm` Node 20 ile uyumlu 10.x sürümünü kullanır |
| pnpm | 10.x | `npm install -g pnpm@10` |
| Python | ≥ 3.12 | `uv` yönetir |
| uv | ≥ 0.12 | `python -m pip install uv` |
| Docker | — | Postgres 16 + pgvector için |

## Kurulum (temiz makine)

```bash
# 1) Bağımlılıklar
pnpm install

# 2) Veritabanı (Postgres 16 + pgvector, host portu 5435)
docker compose -f db/docker-compose.yml up -d

# 3) Ortam dosyaları
cp apps/web/.env.example apps/web/.env.local
cp services/api/.env.example services/api/.env
cp services/etl/.env.example services/etl/.env

# 4) Şema
cd services/api && uv run alembic upgrade head && cd ../..

# 5) Referans veri (ülke merkezleri + ligler)
pnpm seed:countries                                    # data/reference/countries.csv üretir
cd services/etl && uv run python -m jobs.seed_reference && cd ../..

# 6) Çalıştır
pnpm dev        # web :3000 + api :8000
```

`http://localhost:3000` → dönen dünya, ülke hover'ı ve tıklayınca açılan panel.
`http://localhost:8000/health` → `{"status":"ok", ...}`, `http://localhost:8000/docs` → OpenAPI.

## Komutlar

```bash
pnpm dev          # web + api birlikte (turbo)
pnpm lint         # eslint (web, core) + ruff (api, etl)
pnpm typecheck    # tsc --noEmit
pnpm test         # pytest (api, etl)
pnpm seed:countries                                    # countries.csv + globe geo verisi
docker compose -f db/docker-compose.yml up -d          # veritabanı
cd services/api && uv run alembic upgrade head         # migration
cd services/etl && uv run python -m jobs.<job>         # ETL çalıştır
```

## Yapı

```
apps/web         Next.js 16 + Tailwind v4 + react-globe.gl  (globe, paneller, sayfalar)
packages/core    Platform-bağımsız TS: zod şemaları, API client, per-90 yardımcıları
packages/config  Paylaşılan eslint / tsconfig
services/api     FastAPI + SQLAlchemy 2 + Alembic  (şema kaynağı: app/models)
services/etl     Veri işleri: jobs/seed_reference.py, jobs/kaggle_transfermarkt.py
db               docker-compose (postgres+pgvector) + alembic/versions
data/reference   countries.csv, leagues.csv, country_aliases.csv (repoda)
data/raw         Ham kaynak yanıtları — gitignore'da, cache-first ETL buraya bakar
```

## Veri kaynakları ve sırlar

- ETL-1 (Kaggle Transfermarkt) çalışması için `services/etl/.env` içine `KAGGLE_USERNAME` +
  `KAGGLE_KEY` gerekir. Anahtar yoksa job **sessizce geçmez**, ne yapılacağını söyleyip durur;
  alternatif olarak dataset'i elle `data/raw/kaggle/player-scores/` altına açabilirsin.
- API-Football free tier ~100 istek/gün. Tüm yanıtlar `data/raw/` altına yazılır, ETL önce
  cache'e bakar. Detay: `docs/DATA_SOURCES.md`.
- `.env` asla commit edilmez; yeni anahtar gerektiğinde ilgili `.env.example` güncellenir.
