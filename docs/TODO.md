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
- [x] pnpm + Turborepo monorepo iskeleti (`apps/web`, `packages/core`, `packages/config`, `services/api`, `services/etl`, `db`, `docs`) (✓ 2026-08-18)
- [x] `apps/web`: Next.js 16 + TypeScript 5.9 + Tailwind v4 + shadcn/ui kurulumu, çalışan sayfa (✓ 2026-08-18)
      — shadcn CLI bağlandı (`components.json` + `cn`); semantik tokenları DESIGN.md paletine
      alias'landı, kendi renk temasını yazmasına izin verilmedi. TS 7 yerine 5.9: typescript-eslint
      henüz `<6.1` destekliyor.
- [x] `services/api`: FastAPI iskeleti (`/health` endpoint), uv ile bağımlılıklar, ruff config (✓ 2026-08-18)
- [x] `db/docker-compose.yml`: Postgres 16 + pgvector; `alembic init` + ilk migration (✓ 2026-08-18)
      — host portu **5435** (5432/5433/5434 bu makinede dolu).
- [x] Kök komutlar: `pnpm dev` (web+api birlikte), `pnpm lint`, `pnpm typecheck`, `pnpm test` çalışıyor (✓ 2026-08-18)
- [x] `.env.example` dosyaları (web, api, etl) + `.gitignore` (`data/raw/`, `.env`, cache) (✓ 2026-08-18)
- [x] `docs/` altına md dosyaları yerleştirildi (CLAUDE.md kökte kalır), README.md kök özet yazıldı (✓ 2026-08-18)
- [x] Git init + ilk commit + GitHub repo push (✓ 2026-08-18)
      — https://github.com/erenulutas0/scoutGlobe · varsayılan dal `main`.
- [x] CI: GitHub Actions ile lint + typecheck + test + build (`.github/workflows/ci.yml`) (✓ 2026-08-18)
      — GitHub'da yeşil koştu; action'lar Node 20 deprecation'ı nedeniyle v7'ye (pnpm v6) yükseltildi.

## Faz 1 — Veri Temeli
- [x] Alembic migration: ARCHITECTURE.md §4'teki tam şema (pgvector extension dahil) (✓ 2026-08-18)
      — 11 tablo + `CREATE EXTENSION vector`; `leagues.transfermarkt_id` eklendi (ARCHITECTURE.md §4 güncellendi).
- [x] `data/reference/countries.csv`: ülke kodu + isim + globe merkez koordinatları (seed script) (✓ 2026-08-18)
      — 174 ülke; koordinatlar world-atlas geometrisinden `d3-geo` ile hesaplandı (elle yazılmadı),
      isimler `i18n-iso-countries` (EN + TR). Anakara centroid'i: Fransa/ABD gibi ülkelerde okyanusa
      düşmemesi için en büyük parça alınır.
- [x] Seed: Big-5 ligleri + Süper Lig + lig katsayıları (`strength_coef`) (✓ 2026-08-18)
      — `strength_coef` değerleri **geçici** (`coef_source=provisional-uefa`); ClubElo görevi Backlog'da.
- [⏳] ETL-1: Kaggle Transfermarkt dataseti importer (players, clubs, transfers, market_value_history)
      — Kod tamam ve **sentetik veriyle uçtan uca testli** (`services/etl/tests/`): cache-first indirme,
      lig kapsamı filtresi, upsert, `ingest_runs` logu. **Yarım kalan:** gerçek dataset için
      `KAGGLE_API_TOKEN` gerekiyor (kullanıcıdan istendi; Kaggle artık KGAT_ token'i veriyor,
      kimlik tespiti kagglehub'a devredildi).
- [ ] ETL-2: soccerdata/FBref → Big-5 son sezon `player_season_stats` (rate limit'e saygılı, cache'li)
- [ ] ETL-3: API-Football → Süper Lig kadro + sezon istatistikleri (günlük kota bütçesi kodda)
- [ ] Kimlik eşleme: FBref ↔ Transfermarkt fuzzy match script + `manual_mappings.csv` akışı
- [x] `ingest_runs` loglama her ETL job'ında (✓ 2026-08-18)
      — `jobs.common.ingest.ingest_run` context manager; mevcut iki job kullanıyor, yeni job'lar da kullanmalı.
- [ ] Veri kalite kontrol scripti: satır sayıları, null oranları, eşleşmeyen oyuncu raporu

## Faz 2 — API Katmanı
- [ ] Router'lar: `/leagues`, `/clubs/{id}`, `/players/{id}`, `/players/search` (filtreler)
- [ ] `/globe/summary`: ülke + lig düğümleri + transfer arc agregasyonu (TTL cache)
- [ ] OpenAPI → `packages/core` TS client üretimi (script + CI kontrolü)
- [ ] pytest: her router için en az happy-path + 1 edge case
- [ ] Hata standardı: problem+json formatı, tutarlı 404/422

## Faz 3 — Globe MVP (web)
- [x] `react-globe.gl` sahnesi: koyu doku, atmosfer, yıldız arka planı (DESIGN.md'ye uygun) (✓ 2026-08-18)
      — FIRST_PROMPT gereği Faz 0 ile birlikte öne alındı. Doku harici asset değil, token'lardan üretilen
      `MeshPhongMaterial` + CSS starfield.
- [x] Ülke polygon katmanı: hover highlight + tıkla → `pointOfView` zoom (✓ 2026-08-18)
      — Türkçe ülke adı + ISO kodu etiketi, ESC ile panel kapanır. Ekran görüntüsüyle doğrulandı.
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

### 2026-08-18 oturumunda keşfedilenler
- [ ] (keşif) **Kaggle anahtarı gelince ETL-1'i gerçek veriyle çalıştır**: satır sayıları, eşleşmeyen
      ülke isimleri ve `ingest_runs` çıktısı doğrulanacak. Anahtar yoksa dataset elle
      `data/raw/kaggle/player-scores/` altına açılabilir.
- [ ] (keşif) Kulüplerin `lat`/`lng` alanı boş — Transfermarkt dataseti stadyum koordinatı vermiyor.
      Globe'daki kulüp noktaları için koordinat kaynağı bul (OSM/Wikidata) veya lig merkezine düşür.
- [ ] (keşif) `strength_coef` şu an `provisional-uefa` tahmini → ClubElo CSV API'sinden otomatik hesapla
      (`data/reference/leagues.csv` içindeki `coef_source` sütunu takip için var).
- [ ] (keşif) API-Football lig ID'leri (39/140/135/78/61/203) **canlı doğrulanmadı**; ETL-3'te
      `/leagues` yanıtıyla karşılaştır, tutmuyorsa seed'i düzelt.
- [ ] (keşif) Süper Lig için soccerdata/FBref anahtarı yok (`leagues.fbref_id` boş) → ETL-2 kapsamı
      Big-5 ile sınırlı; Süper Lig istatistiği API-Football'a bağımlı.
- [ ] (keşif) `player_vectors` için pgvector index'i (ivfflat/hnsw) yok — Faz 4'te veri gelince
      ölçüp ekle (boş tabloda index parametresi seçmek anlamsız).
- [ ] (keşif) `transfers` tablosunda doğal tekil anahtar yok; ETL-1 şu an oyuncu bazlı sil-yaz yapıyor.
      Unique constraint (player_id, transfer_date, from_club_id, to_club_id) düşünülmeli.
- [ ] (keşif) Clash Display Fontshare CDN'inden geliyor → offline/CSP'li ortamda fallback'e düşer.
      woff2'yi `apps/web` içine alıp `next/font/local` ile self-host et.
- [ ] (keşif) world-atlas'ta ISO numeric id'si olmayan 3 geometri (K. Kıbrıs, Somaliland, Kosova)
      `countries-meta.json` dışında kalıyor → globe'da Türkçe ad/kod göstermiyorlar.
- [x] ~~(keşif) CI GitHub'da hiç koşmadı~~ → push edildi, iki koşu da yeşil (✓ 2026-08-18).
- [ ] (keşif) Proje OneDrive klasöründe ve yol Türkçe karakter içeriyor; `node_modules` senkronu
      build/watch performansını düşürebilir — sorun çıkarsa repoyu OneDrive dışına taşı.
- [ ] (keşif) `apps/web/src/components/ui/button.tsx` eklendi ama henüz kullanılmıyor — ilk gerçek
      form/dialog işinde kullanılacak, yoksa silinecek.

### Fikirler
- [ ] (fikir) TFF alt lig verisi araştırması — Türkiye nişi için kaynak keşfi
- [ ] (fikir) Shortlist paylaşım linki (kulübe/menajere gönderilebilir rapor)
- [ ] (fikir) StatsBomb open data ile event-bazlı radar grafikleri (oyuncu profili)
- [ ] (fikir) PDF scouting raporu üretimi

## Tamamlananlar Arşivi
> Biten fazların görevleri buraya taşınabilir (dosya şişerse), tarihleriyle birlikte.
