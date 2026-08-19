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
- [x] ETL-1: Kaggle Transfermarkt dataseti importer (players, clubs, transfers, market_value_history) (✓ 2026-08-18)
      — Gerçek dataset (219 MB) indirildi ve yüklendi: **219 kulüp · 15.188 oyuncu · 43.465 transfer ·
      245.422 piyasa değeri** (2 dk 06 sn, `ingest_runs` → success). İkinci çalıştırma cache'ten okudu.
      Milliyet eşlemesi %100: eşleşmeyen tek isim kalmadı, boş kalan 102 oyuncunun kaynakta zaten
      `country_of_citizenship` değeri yok.
- [x] ETL-2: soccerdata/FBref → Big-5 son sezon `player_season_stats` (rate limit'e saygılı, cache'li) (✓ 2026-08-18)
      — 2025-26 sezonu: 2.839 FBref satırından **2.728'i** yazıldı (5 lig, 96 kulüp).
      Kulüp eşleşmesi %100, oyuncu %96,1. Ham HTML `data/raw/fbref/` altında cache'li.
      ⚠️ **xg/xa NULL kaldı: FBref artık xG yayınlamıyor** (DATA_SOURCES.md güncellendi).
- [ ] ETL-3: API-Football → Süper Lig kadro + sezon istatistikleri (günlük kota bütçesi kodda)
- [x] Kimlik eşleme: FBref ↔ Transfermarkt fuzzy match script + `manual_mappings.csv` akışı (✓ 2026-08-18)
      — `jobs/common/matching.py`: isim normalizasyonu (unidecode), doğum yılı + soyadı,
      kadro içi kapsama ve fuzzy katmanları. Eşleşmeyen her satır `manual_mappings.csv`'ye
      `target_id` boş olarak düşer; doldurulunca sonraki koşuda otomatik kullanılır
      (7 kulüp böyle çözüldü). Çakışan kulüp anahtarları sessizce ezilmez, belirsiz sayılır.
- [x] `ingest_runs` loglama her ETL job'ında (✓ 2026-08-18)
      — `jobs.common.ingest.ingest_run` context manager; mevcut iki job kullanıyor, yeni job'lar da kullanmalı.
- [x] Veri kalite kontrol scripti: satır sayıları, null oranları, eşleşmeyen oyuncu raporu (✓ 2026-08-18)
      — `uv run python -m jobs.data_quality` (`--strict` ile CI'da kırar). Tablo sayıları, kaynak
      dağılımı, null eşikleri, 7 tutarlılık kontrolü ve bekleyen elle eşleme sayıları.
      Şu an: ihlal yok; null oranları milliyet %0,67 · doğum tarihi %0,20.

## Faz 1.5 — Veri Derinliği (2026-08-19'da araya alındı)

> **Neden araya girdi:** "Bir scout bunu kullanır mı?" değerlendirmesinde tek darboğaz veri
> genişliği çıktı. Big-5 oyuncuların *vardığı* liglerdir; scout'un para kazandırdığı ligler
> oyuncuların *çıktığı* liglerdir. Kullanıcı onayıyla Faz 4 öncesine alındı.

- [x] Transfermarkt tam kapsam: 31 birinci lig (Brezilya, Arjantin, Eredivisie, Portekiz,
      Belçika, İskandinavya, MLS, J1, Suudi...) (✓ 2026-08-19)
      — **776 kulüp · 46.357 oyuncu · 156.826 transfer · 618.627 piyasa değeri**
      (öncesi: 219 / 15.188 / 43.465 / 245.422). Küratörlü lig alanları ezilmiyor.
- [x] Maç granülaritesi: `matches` + `player_match_stats` tabloları (✓ 2026-08-19)
      — **63.382 maç · 1.583.535 oyuncu-maç satırı**, 2012-2026. `COPY` ile yükleniyor.
      Form eğrisi artık sorgulanabilir (Yamal: 2023'te ort 41 dk → 2025'te ort 84 dk).
- [x] Veri kalite raporu maç tablolarını da kapsıyor + tolerans mekanizması (✓ 2026-08-19)
      — `played_on` ile `matches.date` tutarlılığı kontrol ediliyor. Her koşuda kırmızı yanan
      kontrol görünmez hale gelir; bilinen kaynak gürültüsü için tolerans tanımlı.
- [x] ETL-2 çoklu lig: FBref Big-5 dışına açıldı (✓ 2026-08-19)
      — **12 lig** (öncesi 5): + Süper Lig 588, Eredivisie 548, Ekstraklasa 542, Primeira Liga 517,
      Belçika 373, İskoçya 359, Avusturya 218. Sezon satırı 5.340 → **8.558**.
      Süper Lig FBref'te olduğu için ETL-3 (API-Football) artık zorunlu değil.
      Yeni ligler `data/reference/soccerdata/config/league_dict.json` ile ekleniyor (ezme yok).
      Yan kazanç: oyuncu havuzu 46 bine çıkınca Big-5 eşleşmeyenleri 111 → **38**'e düştü.
- [ ] Çok sezonlu backfill: FBref + Understat için 2021-22'den bu yana
- [x] Understat şut olayları (`shots` tablosu, x/y koordinatlı) → şut haritası (✓ 2026-08-19)
      — `GET /players/{id}/shots`: bölge dağılımı (altıpas / ceza sahası / yan / dışarı) + xG farkı.
      Oyuncu sayfasında yarı saha üzerine çizilen şut haritası; daire büyüklüğü xG, yeşil olanlar gol.
      Bölge sınırları gerçek ceza sahası ölçülerinden (105×68 m) türetildi, testle kilitlendi.
      Maç eşleşmesi (tarih + kulüp) **%100**. Kapsam Understat'ın sınırı: Big-5.
      **Tam saha ısı haritası yapılmadı** — tüm dokunuşların pozisyonu hiçbir açık kaynakta yok;
      uydurmak yerine dürüst sınırı belirttik (bkz. ARCHITECTURE §4 notu).
- [x] Oyuncu sayfasında form/trend grafiği: metrik seçicili kayan ortalama + dakika payı eğrisi (✓ 2026-08-19)
      — `GET /players/{id}/form`: maç bazlı seri (rakip, iç/dış saha, kayan ortalama) + sezon trendi.
      UI'da metrik seçici (gol katkısı/gol/asist/dakika) ve 3-5-10 maçlık pencere.
      Eğri yönü ilk üçte bir ↔ son üçte bir ortalamasıyla belirlenir; tek maçlık sıçrama
      yükselen oyuncuyu kırmızıya boyamasın diye.

## Faz 2 — API Katmanı
- [x] Router'lar: `/leagues`, `/leagues/{id}`, `/clubs/{id}`, `/players/{id}`, `/players/search` (✓ 2026-08-19)
      — Arama filtreleri: isim, pozisyon, lig, uyruk, yaş aralığı, azami değer, asgari dakika, sayfalama.
      Yanıtlar camelCase (pydantic alias) → `packages/core` zod şemalarıyla birebir.
- [x] `/globe/summary`: ülke + lig düğümleri + transfer arc agregasyonu (TTL cache) (✓ 2026-08-19)
      — Tek istek: 6 ülke, 6 lig düğümü, ülke→ülke toplanmış 30 arc. 5 dk in-process TTL cache;
      arc sayısı 120 ile sınırlı (ARCHITECTURE §7 performans bütçesi).
- [x] OpenAPI → `packages/core` TS client üretimi (script + CI kontrolü) (✓ 2026-08-19)
      — `pnpm openapi`: FastAPI şemasını sunucu çalıştırmadan dışa aktarır, `openapi-typescript` ile
      `packages/core/src/api/schema.ts` üretir. CI `git diff --exit-code` ile sapmayı kırar.
      Üretilen tipler ölü değil: arama/lig sorgu parametreleri doğrudan onlardan türetiliyor.
- [x] pytest: her router için en az happy-path + 1 edge case (✓ 2026-08-19)
      — 18 test. Ayrı `scoutglobe_test` veritabanı Alembic ile kuruluyor (dev verisinden bağımsız,
      migration'ları da sınıyor); her test geri alınan bir transaction içinde koşuyor.
      CI'da gerçek Postgres servisi + migration + seed adımı eklendi.
- [x] Hata standardı: problem+json formatı, tutarlı 404/422 (✓ 2026-08-19)
      — `app/errors.py`: 404/422/400 tek şekilde `application/problem+json` döner (type, title,
      status, detail, instance). FastAPI'nin iki farklı hata gövdesi sorunu ortadan kalktı.

## Faz 3 — Globe MVP (web)
- [x] `react-globe.gl` sahnesi: koyu doku, atmosfer, yıldız arka planı (DESIGN.md'ye uygun) (✓ 2026-08-18)
      — FIRST_PROMPT gereği Faz 0 ile birlikte öne alındı. Doku harici asset değil, token'lardan üretilen
      `MeshPhongMaterial` + CSS starfield.
- [x] Ülke polygon katmanı: hover highlight + tıkla → `pointOfView` zoom (✓ 2026-08-18)
      — Türkçe ülke adı + ISO kodu etiketi, ESC ile panel kapanır. Ekran görüntüsüyle doğrulandı.
- [x] Lig/kulüp nokta katmanı (`/globe/summary` verisiyle) (✓ 2026-08-19)
      — Lig düğümleri ülke merkezinde; yükseklik lig katsayısına, yarıçap kulüp sayısına bağlı.
      Düğüme tıklayınca doğrudan lige iniyor.
- [x] Sağ cam panel: ülke → ligler → oyuncu listesi drill-down (✓ 2026-08-19)
      — Ülke → lig → kulüp → kadro; geri (←) ve ESC ile bir seviye yukarı. Ekran görüntüsüyle
      doğrulandı (Fransa → Ligue 1 → FC Metz → kadro).
- [x] Oyuncu profil sayfası `/players/[id]`: sezonluk istatistik tablosu + değer grafiği (✓ 2026-08-19)
      — Server component (ISR 300 sn). Solda kimlik kartı + saf SVG değer grafiği (JS yok; yükseliş
      `--grass`, düşüş `--alert-coral`), sağda kaynak başına ayrı satırlı mono istatistik tablosu.
      Kadro listesinden oyuncuya tıklanabiliyor. Radar grafik Faz 4'e bırakıldı: persentil için
      z-score hattı gerekiyor, uydurulmayacak.
- [ ] Global arama (⌘K): oyuncu/kulüp/lig
- [ ] Mobil viewport davranışı: düşük nokta sayısı, panel bottom-sheet olur
- [ ] Performans kontrolü: Lighthouse + FPS notu, `pauseAnimation` panel açıkken

## Faz 4 — Keşif Motoru (transfer önerisi)
- [ ] Per-90 + pozisyon grubu z-score pipeline (`services/api/similarity/`)
- [ ] Rol ağırlık profilleri (başlangıç: 8 rol) → `player_vectors` üretimi
- [ ] `/players/{id}/similar` endpoint (pgvector cosine + filtre)
- [ ] `POST /discover/recommendations`: kriter formu → sıralı liste + metrik bazlı gerekçe
- [ ] Web `/discover` sayfası: "Kulüp ihtiyacı" formu (pozisyon, yaş, bütçe, lig seviyesi, stil)
- [x] Transfer arc katmanı globe'a eklendi (sezon filtresi ile) (✓ 2026-08-19)
      — Ülke→ülke toplanmış akışlar, kalınlık transfer sayısına bağlı, `--arc-out` → `--grass`
      gradyanı ve dash animasyonu. `prefers-reduced-motion` altında animasyon duruyor.
      API sezon filtresini destekliyor; UI'da sezon seçici Faz 4'te.
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
- [x] ~~(keşif) Kaggle anahtarı gelince ETL-1'i gerçek veriyle çalıştır~~ → yapıldı (✓ 2026-08-18).
- [ ] (keşif) `countries` tablosu artık **tam ISO listesi** (250 ülke); 76'sının centroid'i yok çünkü
      world-atlas 110m onları çizmiyor. Globe yalnızca centroid'i olanları gösterir. Küçük ülkeleri de
      dünyada göstermek istersek 50m çözünürlüğe geçmek gerekir.
- [ ] (keşif) Oyuncular çok sezonlu geldi (15.188 kayıt, 219 kulüp) — `players.current_club_id` güncel
      sezonu değil dataset'teki son kulübü gösteriyor. Sezon bazlı kadro için ETL-2/ETL-3 gerekli.
- [ ] (keşif) ETL testleri dev veritabanında koşuyor; iddialar fixture satırlarına daraltıldı ama
      izolasyon için ayrı bir test şeması/veritabanı daha sağlam olur.
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

### 2026-08-18 ETL-2 oturumunda keşfedilenler
- [x] ~~(keşif) ETL-2b: Understat'tan xG/xAG~~ → yapıldı (✓ 2026-08-18).
      `jobs/understat_xg.py`: 2025-26 için 2.775 satırdan **2.612'si** yazıldı, hepsinde xg+xa.
      Kulüp eşleşmesi %100. FBref satırları ezilmiyor: Understat kendi `source` satırıyla geliyor,
      böylece hangi rakamın hangi sağlayıcıdan geldiği kaybolmuyor.
- [ ] (keşif) Aynı oyuncu-sezon için iki kaynak satırı var (fbref + understat). Keşif motoru
      (Faz 4) hangi kaynağı esas alacağına karar vermeli — öneri: hacim FBref, beklenen gol Understat.
- [ ] (keşif) Understat importunda 2 satır `ON CONFLICT DO NOTHING`'e takıldı → iki farklı Understat
      oyuncusu aynı bizim oyuncumuza eşleşmiş olabilir (yanlış pozitif). İncele.
- [ ] (keşif) FBref Big-5 birleşik sayfası `passing`/`defense`/`possession` tablolarını vermiyor;
      progressive pas ve defansif metrikler için **lig bazlı** okuma gerekir (5× istek, cache'li).
- [ ] (keşif) `manual_mappings.csv`'de 111 oyuncu `target_id` bekliyor (çoğu tek isimli Brezilyalı
      ya da transliterasyon farkı). Doldurulunca ETL-2 tekrar koşturulmalı.
- [ ] (keşif) Kaleci metrikleri yok — FBref `keeper` tablosu ayrı; GK scouting için ayrı akış gerekli.
- [ ] (keşif) Sadece 2025-26 sezonu yüklendi. Trend/momentum analizleri için en az 3 sezon lazım
      (`--season 2425` ile geriye doğru koşturulabilir).

### 2026-08-19 Faz 2 oturumunda keşfedilenler
- [x] ~~(keşif) Kulüp kadroları şişkin görünüyor~~ → düzeltildi (✓ 2026-08-19).
      Kadro ve sayımlar artık `player_season_stats`'in son sezonundan türüyor:
      Premier League 33 kulüp/2278 oyuncu yerine **20 kulüp/525 oyuncu (2025-26)**.
      Sezon istatistiği olmayan lig/kulüp kayıtlı veriye düşüyor ve bunu UI'da `season=null`
      etiketiyle söylüyor — iki farklı sayım tabanı sessizce karışmıyor.
- [ ] (keşif) Lig düğümleri ülke merkezinde toplanıyor; aynı ülkede birden çok lig olunca üst üste
      binecek. Kulüp koordinatı geldiğinde düğümleri kulüplere dağıt.
- [x] ~~(keşif) Oyuncu profil sayfası henüz yok~~ → yapıldı (✓ 2026-08-19).
- [ ] (keşif) Oyuncu sayfasında radar grafik yok (DESIGN.md §4 istiyor) — pozisyon grubu persentili
      Faz 4'teki z-score hattına bağlı.
- [ ] (keşif) `/globe/summary` cache'i in-process — birden çok API süreci çalışırsa tutarsız olur.
      Tek süreçte sorun yok, ölçeklenince Redis kararı gerekir (ARCHITECTURE bilinçli erteledi).

### 2026-08-19 veri derinliği oturumunda keşfedilenler
- [ ] (keşif) **Transfermarkt dataset'i yalnızca birinci ligleri taşıyor** (31 lig, hepsi
      `first_tier`). Championship, Ligue 2, 2. Bundesliga, League One için kulüp/oyuncu kaydı yok →
      FBref istatistiğini bağlayacak varlık yok. Bu ligler ayrı bir varlık kaynağı gerektirir
      (FBref'in kendisini varlık kaynağı yapmak ya da daha geniş TM çekimi).
- [ ] (keşif) `clubs.csv` içinde COL1 (Kolombiya, 20 kulüp) var ama `competitions.csv` içinde yok →
      lig kaydı üretilemediği için bu kulüpler atlanıyor. Dataset tutarsızlığı; elle lig eklenebilir.
- [ ] (keşif) ETL testleri hâlâ dev veritabanında koşuyor; `services/api` gibi ayrı test
      veritabanına taşınmalı. `kaggle_matches` işi bu yüzden test edilemiyor (COPY kendi
      transaction'ını açıyor, geri alınamıyor).
- [ ] (keşif) Kaggle importu tek dev transaction'da çalışıyor (~800 bin satır). Çalışırken sonuçlar
      görünmüyor ve kilit süresi uzun; adım adım commit daha sağlıklı olur.
- [ ] (keşif) 2018-02-21 Ukrayna maçında iki oyuncuya 135 dk yazılmış (kaynak hatası). Veri
      düzeltilmedi, tolerans tanımlandı.

- [ ] (keşif) ETL-2'de veri silen hata çıktı ve düzeltildi: eşleşme sıfır olduğunda silme kapsamı
      boş kalıyor, `if league_ids:` koşulu da kapsamı tamamen kaldırıp o sezonun **tüm** FBref
      satırlarını siliyordu. Artık kapsam okunan ligden türüyor ve boş kapsam hiçbir şey silmiyor
      (`tests/test_fbref_scope.py` bunu kilitliyor). Silinen Big-5 verisi cache'ten geri yüklendi.
- [ ] (keşif) Aynı oyuncuya eşleşen iki FBref satırı `ON CONFLICT` batch'ini patlatıyordu; artık
      dakikası fazla olan satır tutuluyor ve kaç satırın birleştirildiği raporlanıyor.
- [ ] (keşif) Belçika/İskoçya/Avusturya'da 307 satır kulüp eşleşmediği için atlandı — elle eşleme
      kuyruğunda; kapsamı yükseltmek için doldurulmalı.
- [ ] (keşif) uvicorn `--reload` bu makinede kod değişikliğini güvenilir almıyor (muhtemelen
      OneDrive dosya olayları). Doğrulama öncesi dev sunucusunu yeniden başlatmak gerekiyor.

- [ ] (keşif) Understat `situation` alanı bazı şutlarda boş geliyor (PL'de 91 şut, %83,5 dönüşüm →
      deseni penaltı). Kaynak etiketlemediği için biz de etiketlemiyoruz; UI'da "Belirtilmemiş".
- [ ] (keşif) Kalite raporundaki "son koşusu başarısız kaynak" kontrolü, o an **çalışan** job'ı da
      başarısız sayıyordu. Yalnızca `failed` durumuna daraltıldı.

### Fikirler
- [ ] (fikir) TFF alt lig verisi araştırması — Türkiye nişi için kaynak keşfi
- [ ] (fikir) Shortlist paylaşım linki (kulübe/menajere gönderilebilir rapor)
- [ ] (fikir) StatsBomb open data ile event-bazlı radar grafikleri (oyuncu profili)
- [ ] (fikir) PDF scouting raporu üretimi

## Tamamlananlar Arşivi
> Biten fazların görevleri buraya taşınabilir (dosya şişerse), tarihleriyle birlikte.
