# CLAUDE.md — ScoutGlobe Çalışma Sözleşmesi

Bu repo, futbolcu verisiyle transfer önerisi ve future-star keşfi yapan **ScoutGlobe** projesidir.
Arayüzün merkezi Three.js (react-globe.gl) ile uzaydan görünen interaktif dünyadır.

## Her oturumda okuma sırası
1. `docs/TODO.md` → hangi görev sırada, kurallar orada.
2. `docs/ARCHITECTURE.md` → mimari kararlar; sapacaksan ÖNCE orada güncelle ve gerekçele.
3. Göreve göre: `docs/DATA_SOURCES.md` (ETL işleri) · `docs/DESIGN.md` (UI işleri).

## Komutlar
```bash
pnpm dev          # web + api birlikte (turbo)
pnpm lint         # eslint + ruff
pnpm typecheck    # tsc --noEmit
docker compose -f db/docker-compose.yml up -d   # Postgres + pgvector
cd services/api && uv run alembic upgrade head  # migration
cd services/etl && uv run python -m jobs.<job>  # ETL çalıştır
```

## Kurallar
- **TODO disiplini:** Oturum sonunda `docs/TODO.md` güncellenmeden iş "bitti" sayılmaz.
  Keşfedilen işler Backlog'a `(keşif)` ile eklenir. Görev silinmez.
- **Kalite kapısı:** commit öncesi `pnpm lint && pnpm typecheck` (+ dokunduysan `pytest`) yeşil olmalı.
- **Commit:** küçük ve konvansiyonel — `feat(globe): ülke zoom`, `feat(etl): kaggle importer`, `fix(api): ...`
- **Sırlar:** `.env` asla commit edilme z; yeni anahtar gerektiğinde `.env.example`'a ekle ve kullanıcıya söyle.
- **Kota/scraping:** API-Football günlük ~100 istek — önce `data/raw/` cache'ine bak. FBref'e istekler
  arası ≥3 sn, tek thread. Detay: `docs/DATA_SOURCES.md`.
- **Platform bağımsızlık:** `packages/core` içinde DOM/window kullanma (mobil hazırlığı).
- **Tasarım:** UI'da renk/font uydurma — sadece `docs/DESIGN.md` tokenları. İstatistik rakamları her zaman mono.
- **Dil:** Kullanıcıyla iletişim Türkçe; kod, commit ve tanımlayıcılar İngilizce.
- **Belirsizlik:** Kabul kriteri net değilse veya mimariyi değiştirecek bir karar gerekiyorsa
  tahmin etme — kısa seçenekler sunup sor.
- **Doğrulama:** UI işinde ekran görüntüsü/`pnpm dev` ile gerçekten çalıştığını gör; "derleniyor" yetmez.

## Sık düşülen tuzaklar
- react-globe.gl SSR'da patlar → `next/dynamic` + `ssr:false`.
- pgvector extension'ı migration'da `CREATE EXTENSION IF NOT EXISTS vector` ile açılmalı.
- Kaynaklar arası oyuncu ID eşleşmesi otomatik %100 olmaz → eşleşmeyenleri
  `data/reference/manual_mappings.csv` akışına düşür, sessizce atlama.
- Per-90 hesapları 900 dk altı oyuncularda yanıltıcıdır → eşiği uygula.
