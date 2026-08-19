# ARCHITECTURE.md — ScoutGlobe

> Futbolcu istatistiklerini toplayan, kulüp ihtiyacına göre transfer önerisi üreten ve
> "future star" adaylarını erken tespit etmeyi hedefleyen platform.
> Arayüz: uzaydan bakılan interaktif 3D dünya (Three.js) — ülke → lig → kulüp → oyuncu akışı.
>
> Bu dosya mimari kararların **tek doğruluk kaynağıdır**. Sapma gerekiyorsa önce burada güncelle.

---

## 1. Vizyon ve Fazlama

- **Faz A (şimdi):** Web uygulaması. Ücretsiz/açık verilerle Big-5 Avrupa ligi + Süper Lig.
- **Faz B:** Benzerlik motoru + kulüp ihtiyaç filtresi ("transfer önerisi") + transfer arc görselleştirmesi.
- **Faz C:** Future Star skoru (önce sezgisel, sonra ML) + alt lig / genç oyuncu verisi derinleştirme (Türkiye nişi).
- **Faz D:** Mobil (kod tabanı bugünden buna hazır tutulur — bkz. §8).

## 2. Teknoloji Kararları (ve gerekçeleri)

| Katman | Seçim | Neden |
|---|---|---|
| Monorepo | **pnpm workspaces + Turborepo** | Web + gelecekteki mobil + paylaşılan paketler tek repoda; task cache. |
| Web | **Next.js (App Router) + TypeScript** | SSR/ISR ile veri sayfaları hızlı; API route'ları BFF olarak kullanılabilir. |
| 3D Globe | **react-globe.gl** (three-globe/Three.js tabanlı) | Points, arcs, polygons, hexbin, custom layer hazır; ekran görüntüsündeki örneklerin çoğu bu ekosistemden. Gerekirse `globeRef` üzerinden ham Three.js scene'e inilebilir. |
| UI | **Tailwind CSS + shadcn/ui + motion (framer-motion)** | Hızlı, tutarlı; tasarım tokenları DESIGN.md'de. |
| State/Data | **TanStack Query** (server state) + **Zustand** (globe/UI state) | Cache'li veri çekme + hafif global state. |
| Backend | **FastAPI (Python 3.12) + SQLAlchemy 2 + Alembic** | ETL ve ML zaten Python; tek dil. Otomatik OpenAPI şeması → TS client üretimi. |
| Python tooling | **uv + ruff** | Hızlı bağımlılık yönetimi ve lint. |
| Veritabanı | **PostgreSQL 16 + pgvector** | İlişkisel çekirdek + oyuncu vektörleri için cosine similarity aynı DB'de. |
| ETL | Bağımsız Python job'ları (`services/etl`), cron/manuel tetikleme | soccerdata, statsbombpy, API-Football client, Kaggle importer. MVP'de orkestratör (Prefect vb.) YOK — basit tut. |
| Deploy (hedef) | Web → **Vercel**, API+ETL → **Railway/Fly.io**, DB → **Neon/Supabase** | Ücretsiz/ucuz katmanlarla başla. |

**Bilinçli olarak ERTELENENLER:** Redis, mesaj kuyruğu, mikroservis, Kubernetes, auth provider seçimi.
MVP'de gereksiz karmaşıklık; ihtiyaç kanıtlanınca eklenir.

## 3. Monorepo Yapısı

```
scoutglobe/
├── apps/
│   ├── web/                  # Next.js uygulaması
│   │   └── src/
│   │       ├── app/          # route'lar: / (globe), /leagues/[id], /players/[id], /discover
│   │       ├── features/     # globe/, players/, discover/ (feature-first organizasyon)
│   │       └── lib/          # api client wrapper, utils
│   └── mobile/               # (Faz D) Expo — şimdilik sadece README + karar notu
├── packages/
│   ├── core/                 # PLATFORM-BAĞIMSIZ: TS tipleri, zod şemaları, API client
│   │                         #   ⚠️ Burada window/document/DOM API KULLANILMAZ (mobil hazırlığı)
│   └── config/               # paylaşılan eslint / tsconfig
├── services/
│   ├── api/                  # FastAPI: app/, models/, routers/, schemas/, similarity/
│   └── etl/                  # jobs/: kaggle_transfermarkt.py, fbref_seasons.py,
│                             #        apifootball_superlig.py, statsbomb_open.py
├── db/                       # docker-compose.yml (postgres+pgvector), alembic/
├── data/                     # raw/ (gitignore), reference/ (ülke merkezleri, lig katsayıları)
└── docs/                     # ARCHITECTURE.md, TODO.md, DATA_SOURCES.md, DESIGN.md, CLAUDE.md
```

## 4. Veri Modeli (çekirdek şema)

```
countries        (code PK, name, name_tr, lat, lng)            -- globe merkezleri
leagues          (id, name, country_code→countries, tier,
                  strength_coef,                               -- lig kalite katsayısı (kaynak: ClubElo/UEFA)
                  api_football_id, fbref_id, transfermarkt_id) -- fbref_id = soccerdata anahtarı ("ENG-Premier League"),
                                                               -- transfermarkt_id = TM rekabet kodu ("GB1"); ETL-1
                                                               -- kulüpleri bu kodla lige bağlar (2026-08-18 eklendi)
clubs            (id, name, league_id→leagues, lat, lng,       -- globe noktaları
                  transfermarkt_id, api_football_id)
players          (id, full_name, birth_date, nationality_code,
                  position, sub_position, foot, height_cm,
                  current_club_id→clubs, market_value_eur, contract_until,
                  transfermarkt_id, fbref_id, api_football_id) -- kaynaklar arası eşleme anahtarları
player_season_stats
                 (id, player_id, season, league_id, club_id, source,
                  minutes, matches, goals, assists, xg, xa,
                  key_metrics JSONB,                           -- kaynağa göre değişen alanlar
                  UNIQUE(player_id, season, club_id, source))
matches          (id PK = transfermarkt game_id, league_id→leagues, season, round, date,
                  home_club_id→clubs, away_club_id→clubs, home_goals, away_goals,
                  home_formation, away_formation, stadium, attendance, referee)
player_match_stats
                  (player_id→players, match_id→matches, club_id→clubs, played_on,
                   minutes, goals, assists, yellow_cards, red_cards,
                   PK(player_id, match_id))                    -- maç granülaritesi (2026-08-19 eklendi)
shots            (id PK = understat shot_id, player_id→players, club_id→clubs,
                  league_id→leagues, match_id→matches (eşleşirse), season, played_on,
                  minute, xg, location_x, location_y, body_part, situation, result,
                  is_goal)                                     -- şut haritası (2026-08-19 eklendi)
player_vectors   (player_id, season, position_group,
                  embedding vector(64))                        -- pgvector, per-90 normalize edilmiş
transfers        (id, player_id, from_club_id, to_club_id,
                  transfer_date, fee_eur, season)              -- globe'daki arc'lar
market_value_history (player_id, date, value_eur)              -- future-star momentum sinyali
shortlists       (id, name, criteria JSONB, created_at)
shortlist_players(shortlist_id, player_id, note)
ingest_runs      (id, source, started_at, finished_at, status,
                  rows_written, notes)                         -- veri soyağacı/provenance
```

**Maç granülaritesi neden gerekli (2026-08-19):** Sezon toplamı bir oyuncunun *gidişatını*
gösteremez — scouting'in asıl sorusu "yükseliyor mu, dakikaları artıyor mu, son 10 maçta ilk 11 mi".
`matches` + `player_match_stats` bu soruyu yanıtlar ve form eğrilerinin temelidir. Veri Kaggle
Transfermarkt setinde zaten mevcut (31 lig, 2012-2026, ~89 bin maç / ~1,9 M satır), ek ağ isteği
gerektirmez. Kapsam bilinçli olarak *tam*: Faz C'deki backtest ("2019'la eğit, 2022'yi doğrula")
tarihsel derinlik olmadan yapılamaz.

**Lig kapsamı (2026-08-19):** `leagues` artık Big-5 + Süper Lig ile sınırlı değil; Transfermarkt'ın
31 birinci ligi (Brezilya, Arjantin, Eredivisie, Portekiz, Belçika, İskandinavya, MLS, J1...) içeri
alınır. Gerekçe: scout'un para kazandırdığı ligler oyuncuların *vardığı* değil *çıktığı* liglerdir.
`strength_coef`, `api_football_id`, `fbref_id` küratörlü kalır (`data/reference/leagues.csv`);
ETL yalnızca ad/ülke/tier/transfermarkt_id yazar, küratörlü alanları ezmez.

**Şut olayları neden ayrı tablo (2026-08-19):** Understat şutları x/y koordinatıyla verir
(0-1 normalize). Bu, ücretsiz veriyle ulaşılabilen en yakın "konum" katmanıdır: tam saha ısı
haritası için gereken *tüm dokunuşların* pozisyonu hiçbir açık kaynakta yok. Şut haritası ve
"ceza sahası içi şut" trendi bu tablodan çıkar. Kapsam Understat'ın sınırıdır: Big-5.
`match_id` en iyi çaba ile doldurulur (tarih + iki kulüp); eşleşmezse NULL kalır, şut yine de
oyuncuya bağlıdır.

**Kimlik eşleme (en kritik veri problemi):** Aynı oyuncu FBref'te, Transfermarkt'ta ve API-Football'da
farklı ID'lerle var. Eşleme stratejisi: (isim normalize + doğum tarihi + kulüp) fuzzy match →
eşleşmeyenler `data/reference/manual_mappings.csv` ile elle çözülür. Bu iş küçümsenmemeli;
Faz 1'de ayrı görev.

## 5. API Yüzeyi (FastAPI)

```
GET  /globe/summary                 # ülkeler + lig düğümleri + toplu transfer arc'ları (tek istek, cache'li)
GET  /leagues                       # filtre: country, tier
GET  /leagues/{id}                  # lig detay + kulüpler
GET  /clubs/{id}                    # kulüp + kadro
GET  /players/{id}                  # profil + sezon istatistikleri + değer geçmişi
GET  /players/search                # q, position, age_min/max, league_tier, value_max, minutes_min...
GET  /players/{id}/similar          # pgvector cosine + filtreler (yaş, bütçe, lig)
POST /discover/recommendations     # kulüp ihtiyaç kriterleri JSON → sıralı aday listesi + gerekçe skorları
GET  /discover/rising               # future-star v0 skoruna göre yükselenler
```

- OpenAPI şemasından `packages/core` içine TS client üretilir (`openapi-typescript`).
- Ağır endpoint'ler (globe/summary) sunucuda cache'lenir (basit TTL, in-process).

## 6. Keşif Motoru

**Benzerlik (Faz B):**
1. Sezon istatistikleri → per-90 normalize (min. 900 dk eşiği).
2. Pozisyon grubu içinde (GK / DF / MF / FW alt grupları) z-score.
3. Rol ağırlık profilleri (ör. "oyun kurucu bek" ≠ "stoper") ile ağırlıklı vektör → `player_vectors`.
4. pgvector cosine similarity + SQL filtreleri (yaş, sözleşme, piyasa değeri, lig katsayısı).
5. Çıktıda **gerekçe**: hangi metriklerde benzer/üstün olduğu (kulübe satılabilir içgörü budur).

**Future Star v0 (sezgisel skor, Faz C başı):**
`skor = f(yaş≤21, dakika payı trendi, lig katsayısına göre per-90 persentil, piyasa değeri momentumu)`
— tamamen açıklanabilir; her bileşen UI'da gösterilir.

**Future Star v1 (ML, Faz C):** Transfermarkt tarihsel verisiyle etiket: "N yıl içinde piyasa değeri
X kat arttı / üst-5 lige transfer oldu". Gradient boosting (LightGBM) ile başla; sınıf dengesizliğine
ve survivorship bias'a dikkat. Backtest defteri zorunlu (2019 verisiyle eğit, 2022'yi tahmin et, doğrula).

## 7. Globe Mimarisi (apps/web/features/globe)

- **Sahne:** karanlık uzay arka planı (yıldız partikülleri), özel koyu dünya dokusu, atmosfer glow.
- **Katmanlar (react-globe.gl):**
  - `polygonsData` → ülkeler (hover highlight, tıkla → kamera zoom `pointOfView`)
  - `pointsData` → lig/kulüp düğümleri (boyut = lig gücü veya oyuncu sayısı)
  - `arcsData` → transfer akışları (sezon filtresiyle, animasyonlu dash)
  - `htmlElementsData` → seçili öğe etiketi (ihtiyaç halinde)
- **Etkileşim akışı:** Dünya → ülkeye tıkla → zoom + sağda cam panel (ligler) → lig → oyuncu listesi
  → oyuncu → profil sayfası. Globe hiçbir zaman "kaybolmaz", panel üstüne gelir.
- **Performans bütçesi:** ilk yüklemede ≤ ~250 nokta; `pauseAnimation()` panel açıkken;
  doku ≤ 4K; mobil viewport'ta `rendererConfig.antialias=false` + nokta sayısı düşür.
- Globe bileşeni `next/dynamic` ile **ssr:false** yüklenir (WebGL).

## 8. Mobil Hazırlık Kuralları (bugünden geçerli)

1. `packages/core` platform-bağımsız kalır: fetch tabanlı API client, zod şemaları, saf fonksiyonlar.
2. İş mantığı React bileşenlerine değil core'a yazılır; bileşenler "aptal" kalır.
3. Responsive tasarım day-1 (globe dahil — dar viewport davranışı DESIGN.md'de).
4. Faz D'de iki yol, karar o gün verilecek (TODO'da karar görevi var):
   - **Expo (React Native):** core'u aynen kullanır; globe için expo-gl + three ya da mobilde
     basitleştirilmiş 2D harita fallback.
   - **Capacitor:** web'i sarmalar, en hızlı yol; globe WebView'da çalışır, perf ayarı gerekir.

## 9. Ortamlar ve Sırlar

- `.env.example` her serviste tutulur; gerçek `.env` asla commit edilmez.
- Gerekli anahtarlar: `API_FOOTBALL_KEY`, `DATABASE_URL`, `KAGGLE_USERNAME/KEY` (opsiyonel, dataset indirme için).
- Ücretsiz kota disiplini: API-Football free tier ~100 istek/gün → tüm yanıtlar `data/raw/` altına
  kaydedilir, ETL önce cache'e bakar. Kota bütçesi kodda sabit olarak tanımlanır.
