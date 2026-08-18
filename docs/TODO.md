# TODO.md — ScoutGlobe Görev Takibi

> **AGENT KURALLARI (her oturumda önce bunu oku):**
> 1. Bu dosya görevlerin tek doğruluk kaynağıdır. Her çalışma oturumunun BAŞINDA oku, SONUNDA güncelle.
> 2. Biten görevi `- [x]` yap ve sonuna tarih ekle: `(✓ 2026-08-18)`.
> 3. Üzerinde çalıştığın göreve `⏳` koy. Aynı anda en fazla 1-2 görev ⏳ olabilir.
> 4. Çalışırken keşfedilen yeni görevleri **sil(e)mezsin, unutamazsın** → ilgili faza ya da
>    "Backlog" bölümüne `(keşif)` etiketiyle ekle.
> 5. Görev asla silinmez; kapsam dışı kaldıysa üzerini çiz (~~görev~~) ve nedenini yaz.
> 6. Bir fazın tüm görevleri bitmeden sonraki faza geçme (kullanıcı açıkça isterse hariç).
> 7. Kabul kriteri belirsizse görevi bölmeden önce kullanıcıya sor.

---

## Faz 0 — Kurulum ve İskelet
- [ ] pnpm + Turborepo monorepo iskeleti (`apps/web`, `packages/core`, `packages/config`, `services/api`, `services/etl`, `db`, `docs`)
- [ ] `apps/web`: Next.js + TypeScript + Tailwind + shadcn/ui kurulumu, boş ama çalışan sayfa
- [ ] `services/api`: FastAPI iskeleti (`/health` endpoint), uv ile bağımlılıklar, ruff config
- [ ] `db/docker-compose.yml`: Postgres 16 + pgvector; `alembic init` + ilk boş migration
- [ ] Kök komutlar: `pnpm dev` (web+api birlikte), `pnpm lint`, `pnpm typecheck` çalışıyor
- [ ] `.env.example` dosyaları (web, api, etl) + `.gitignore` (`data/raw/`, `.env`, cache)
- [ ] `docs/` altına bu 5 md dosyası yerleştirildi, README.md kök özet yazıldı
- [ ] Git init + ilk commit + (varsa) GitHub repo push
- [ ] CI: GitHub Actions ile lint + typecheck (basit tek workflow)

## Faz 1 — Veri Temeli
- [ ] Alembic migration: ARCHITECTURE.md §4'teki tam şema (pgvector extension dahil)
- [ ] `data/reference/countries.csv`: ülke kodu + isim + globe merkez koordinatları (seed script)
- [ ] Seed: Big-5 ligleri + Süper Lig + lig katsayıları (`strength_coef`)
- [ ] ETL-1: Kaggle Transfermarkt dataseti importer (players, clubs, transfers, market_value_history)
- [ ] ETL-2: soccerdata/FBref → Big-5 son sezon `player_season_stats` (rate limit'e saygılı, cache'li)
- [ ] ETL-3: API-Football → Süper Lig kadro + sezon istatistikleri (günlük kota bütçesi kodda)
- [ ] Kimlik eşleme: FBref ↔ Transfermarkt fuzzy match script + `manual_mappings.csv` akışı
- [ ] `ingest_runs` loglama her ETL job'ında
- [ ] Veri kalite kontrol scripti: satır sayıları, null oranları, eşleşmeyen oyuncu raporu

## Faz 2 — API Katmanı
- [ ] Router'lar: `/leagues`, `/clubs/{id}`, `/players/{id}`, `/players/search` (filtreler)
- [ ] `/globe/summary`: ülke + lig düğümleri + transfer arc agregasyonu (TTL cache)
- [ ] OpenAPI → `packages/core` TS client üretimi (script + CI kontrolü)
- [ ] pytest: her router için en az happy-path + 1 edge case
- [ ] Hata standardı: problem+json formatı, tutarlı 404/422

## Faz 3 — Globe MVP (web)
- [ ] `react-globe.gl` sahnesi: koyu doku, atmosfer, yıldız arka planı (DESIGN.md'ye uygun)
- [ ] Ülke polygon katmanı: hover highlight + tıkla → `pointOfView` zoom
- [ ] Lig/kulüp nokta katmanı (`/globe/summary` verisiyle)
- [ ] Sağ cam panel: ülke → ligler → oyuncu listesi drill-down
- [ ] Oyuncu profil sayfası `/players/[id]`: sezonluk istatistik tablosu + değer grafiği
- [ ] Global arama (⌘K): oyuncu/kulüp/lig
- [ ] Mobil viewport davranışı: düşük nokta sayısı, panel bottom-sheet olur
- [ ] Performans kontrolü: Lighthouse + FPS notu, `pauseAnimation` panel açıkken

## Faz 4 — Keşif Motoru (transfer önerisi)
- [ ] Per-90 + pozisyon grubu z-score pipeline (`services/api/similarity/`)
- [ ] Rol ağırlık profilleri (başlangıç: 8 rol) → `player_vectors` üretimi
- [ ] `/players/{id}/similar` endpoint (pgvector cosine + filtre)
- [ ] `POST /discover/recommendations`: kriter formu → sıralı liste + metrik bazlı gerekçe
- [ ] Web `/discover` sayfası: "Kulüp ihtiyacı" formu (pozisyon, yaş, bütçe, lig seviyesi, stil)
- [ ] Transfer arc katmanı globe'a eklendi (sezon filtresi ile)
- [ ] Sonuç kartlarında "neden bu oyuncu" açıklaması (en güçlü 3 metrik farkı)

## Faz 5 — Future Star v0
- [ ] Sezgisel skor: yaş + dakika trendi + lig-ayarlı persentil + değer momentumu
- [ ] `/discover/rising` + web'de "Yükselenler" görünümü (skor bileşenleri görünür)
- [ ] Backtest notebook'u: 2021 verisiyle skorla → 2024 gerçekleşmesiyle kıyasla, kısa rapor
- [ ] (v1 için hazırlık) Etiket tanımı ve eğitim seti çıkarma scripti — model eğitimi ayrı karar

## Faz 6 — Cila ve Yayın
- [ ] Deploy: web→Vercel, api→Railway/Fly, db→Neon/Supabase; ETL manuel/cron
- [ ] Landing + kısa "nasıl çalışır" bölümü (DESIGN.md sesiyle)
- [ ] Mobil karar görevi: Expo vs Capacitor — ARCHITECTURE.md §8'e göre karar + kayıt
- [ ] `apps/mobile` iskeleti (karara göre) — sadece iskelet, özellik yok
- [ ] Hata takibi (Sentry free tier) + basit analytics

## Backlog / Keşfedilen Görevler
- [ ] (fikir) TFF alt lig verisi araştırması — Türkiye nişi için kaynak keşfi
- [ ] (fikir) Shortlist paylaşım linki (kulübe/menajere gönderilebilir rapor)
- [ ] (fikir) StatsBomb open data ile event-bazlı radar grafikleri (oyuncu profili)
- [ ] (fikir) PDF scouting raporu üretimi

## Tamamlananlar Arşivi
> Biten fazların görevleri buraya taşınabilir (dosya şişerse), tarihleriyle birlikte.
