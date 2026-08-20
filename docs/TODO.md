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
- [x] ETL-3: API-Football → **canlı kadro** (günlük kota bütçesi kodda) (✓ 2026-08-19)
      — Kapsam bilerek daraltıldı: ücretsiz planda sezon parametreli uç noktalar yalnızca
      **2022-2024**'e erişiyor, yani sezon istatistiği için elimizdeki Kaggle verisinden *daha eski*.
      Buna karşılık `players/squads` sezon parametresi almıyor ve **güncel kadroyu** veriyor —
      projedeki tek gerçek zamanlı sinyal. İstatistik FBref'te kalıyor.
      Kısıtlar: 100 istek/gün + **10 istek/dakika** → 6,5 sn bekleme, 429'da 65 sn geri çekilme;
      istemci bütçeyi aşmayı reddediyor. `clubs.api_football_id` bir kez çözülüp saklanıyor.
      **Sonuç:** 18 Süper Lig kulübü canlı doğrulandı; Beşiktaş kadrosu API ile birebir 31 kişi
      (Vlahović, Trossard, Nübel, Ouattara — Kaggle'da olmayan gerçek transferler).
      Kadroda tanımadığımız oyuncu için ince kayıt açılıyor (isim/mevki/fotoğraf; değer uydurulmuyor).
      **Panel düzeltmesi:** `/clubs/{id}` kadroyu `current_club_id`'den değil sezon
      istatistiklerinden türetiyordu, bu yüzden Ocak'ta ayrılan oyuncu (Abraham) sezon
      sonuna kadar kadroda kalıyordu. Canlı doğrulanmış kulüpte artık canlı kadro
      gösteriliyor; yanıtta `squadSource` (`live`/`season`/`registered`) var ve panel
      "güncel kadro" · "2025-26 sezonunda oynayanlar" diye açıkça etiketliyor. Testle kilitlendi.
- [ ] (keşif) Canlı kadro şu an yalnızca Süper Lig'e uygulandı. Diğer 30 lig için kulüp başına
      1 istek gerekiyor (~600 istek = 6+ gün kota). Öncelikli ligler seçilip sırayla koşturulmalı.
- [ ] (keşif) Belirsiz kalan 13 ince kayıt var (aynı soyadı + aynı mevki, ör. "Kone" → üç Koné).
      `manual_mappings.csv` akışıyla elle çözülebilir.
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
- [x] Çok sezonlu backfill: FBref Big-5 için 2023-24 ve 2024-25 (✓ 2026-08-19)
      — 2023-24: 2.767 satır · 2024-25: 2.793 satır · 2025-26: 6.250 satır (12 lig).
      Toplam `player_season_stats` **14.422**. Üç sezonluk ilerleme sorgusu artık çalışıyor
      (Yamal 0.41 → 0.69 → 1.07 g+a/90).
      Kalan: yeni 7 lig için geçmiş sezonlar ve Understat'ın geçmiş xG'si (Backlog'da).
- [ ] (keşif) Geçmiş sezon kapsamı asimetrik: 2025-26'da 12 lig, önceki iki sezonda yalnızca Big-5.
      Lig karşılaştırmalı trend analizinde bu farkı hesaba kat.
- [ ] (keşif) Understat xG'si yalnızca 2025-26 için var; geçmiş sezon xG'si için ETL-2c
      `--season` ile geriye koşturulmalı (maç başına istek, lig-sezon ~2,5 dk).
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

- [x] Görseller: oyuncu fotoğrafı, kulüp arması, lig logosu (✓ 2026-08-19)
      — `players.image_url` dataset'ten, kulüp/lig logoları Transfermarkt'ın kararlı URL deseninden
      türetiliyor. **46.357 portre · 776 arma · 31 lig logosu.**
      Görseller indirilip yeniden yayınlanmıyor (gerekçe: ARCHITECTURE §4); tek `RemoteImage`
      bileşeni kullanılıyor ve baş harfler görselin **altında** duruyor, böylece yavaş ya da
      engellenmiş yükleme boş daire bırakmıyor.
      `image_url` bilerek zorunlu sütun değil: portre kozmetiktir, kaynak bırakırsa import çökmemeli.

- [x] Güncel kadro doğruluğu + veri tazeliği şeffaflığı (✓ 2026-08-19)
      — **Kullanıcı tespiti:** Beşiktaş kadrosunda ayrılan oyuncular görünüyordu.
      Kök neden: Transfermarkt dataset'inin oyuncu profili ile transfer listesi farklı
      zamanlarda taranıyor; biz profildeki `current_club_id`'ye güveniyorduk.
      `jobs/refresh_current_clubs.py` güncel kulübü kanıt sırasına göre çözüyor:
      **son maçını oynadığı kulüp → o maçtan sonraki transfer → profil.**
      1.446 oyuncunun kulübü düzeldi (Abraham→Aston Villa, Rafa Silva→Benfica,
      Muci→Trabzonspor, Asllani→Inter, Touré→Atalanta; Kökçü kalıcı transferle doğru şekilde kaldı).
      `GET /meta/freshness` + üst barda "VERİ <tarih> · <n> gün" rozeti: anlık görüntü
      tarihsiz gösterilmiyor. Dataset'in son transferi 2026-08-16 — kaynak taze, bayat olan
      bizim türetmemizdi.
      **İkinci tur düzeltme:** ilk kural fazla açtı — kadro 98'e çıktı çünkü 2016'da Beşiktaş'ta
      oynayıp izlemediğimiz bir lige giden oyuncu sonsuza dek Beşiktaş'ta kalıyordu. İki koruma
      eklendi: (1) kanıt yalnızca **son ~14 ay** içindeyse geçerli, (2) dataset'in
      `current_club_id` alanı "güncel kadro" değil "onu en son burada gördük" demek
      (Beşiktaş'a 112 oyuncu atanmış, `last_season` 2012'ye kadar iniyor) → `last_season`
      alanı içeri alındı ve profil ancak son sezona aitse geçerli sayılıyor.
      Sonuç: Beşiktaş kadrosu **42** (gerçekçi), kulübü bilinmeyen 28.220 oyuncu artık
      bir kulüp iddia etmiyor.
- [ ] (keşif) Tavan: veri, Kaggle dataset'inin yayın sıklığı kadar taze. Ölçüldü: bugün
      yeniden indirmek bir şey kazandırmıyor (sürüm 677 de 2026-08-16'da bitiyor).
      Gerçek zamanlı kadro için API-Football (anahtar gerekli) veya Transfermarkt kulüp
      sayfası scraping'i (gri alan, onay gerekli) gerekir — **kullanıcı kararı bekliyor**.
- [ ] (keşif) 28.220 oyuncunun `current_club_id`'si NULL → lig filtreli aramada çıkmıyorlar.
      Doğru davranış (kulüplerini bilmiyoruz) ama arşiv oyuncularını arayabilmek için
      "son bilinen kulüp" ayrı bir alan olarak tutulabilir.
- [ ] (keşif) `refresh_current_clubs` maç verisine bağlı; `import:transfermarkt` sırası
      (varlıklar → maçlar → tazeleme) bozulursa en güçlü sinyal kaybolur.

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

## Faz 6 — Lig kapsamı ve düzeltmeler
- [x] 38 ligin hepsine FBref anahtarı verildi (✓ 2026-08-20)
      — Önceden 13 lig (Danimarka, İsveç, Norveç, Yunanistan, İsviçre, Rusya, Ukrayna, Çekya,
      Hırvatistan, Sırbistan, Romanya, Kore, Avustralya) Kaggle'dan gelmiş ama `fbref_id`'si
      yoktu, yani hiç istatistikleri olamazdı. FBref hepsini yayımlıyor (kendi lig indeksinden
      doğrulandı). Seed `transfermarkt_id` üzerinden upsert ettiği için kopya lig oluşmadı.
- [x] Takvim yılı sezon anahtarı düzeltildi (✓ 2026-08-20)
      — `season_label("2026")` **"2020-26"** üretiyordu: altı yıllık bir sezon. soccerdata
      iki tür dört haneli anahtar yazıyor ve birbirlerine benziyorlar — "2526" iki yıla yayılır,
      "2026" tek takvim yılıdır (Brezilya, Arjantin, MLS, Japonya, Kore, Norveç, İsveç).
      Ayrım artık yarıların ardışık yıl olup olmadığına bakıyor.
- [x] `manual_mappings.csv` olay günlüğü olmaktan çıktı (✓ 2026-08-20)
      — Understat eşleşmeyen oyuncuyu **her şut için** bir kez bildiriyor; tek oyuncu bir koşuda
      28 satır yazmıştı. Dosyaya karşı tekilleştirme vardı, partinin kendi içinde yoktu.
      1.666 → 1.567 satır; çözülmüş eşlemeler korundu.
- [x] Veri kalite raporu temiz (✓ 2026-08-20)
      — Tek ihlal "gol > şut": Spertsyan 89 dakika, 1 gol, 0 şut. FBref'in standart ve şut
      tabloları sezon başında birbirini tutmuyor; 900 dakika kapısının çok altında olduğu için
      hiçbir persentile girmiyor. Gerekçesiyle toleransa alındı (5), sistemik bozulma bunu aşar.
- [x] Aynı oyuncu için birden çok kayıt açılması durduruldu (✓ 2026-08-20)
      — FBref oyuncuyu **kulüp başına bir kez** yazıyor; sezon içinde takım değiştiren
      Efe Ugiagbe üç kayıt açtırmıştı (Ceuta, Cádiz, Huesca). Eşleştirici indeksleri koşu
      başında kuruluyor ve koşu sırasında açılanları bilmiyordu. Artık koşu kendi açtıklarını
      hatırlıyor; üç sezon satırı korunuyor çünkü üçü de gerçek.
- [x] Kalan kopyalar birleştirildi (✓ 2026-08-20)
      — `merge_duplicate_players`'a ikinci geçiş eklendi: dış kimliği olmayan ince kayıtlar
      ad + doğum yılı ile birleşiyor, `uq_player_season_source` çakışmasında fazla satır
      siliniyor. **46 kayıt birleşti, kopya grubu kalmadı.** Belirsiz 17 kayıt (A. Cisse →
      iki farklı Cissé gibi) bilinçli olarak bırakıldı.
- [x] Persentilin hangi ligde kazanıldığı görünür oldu (✓ 2026-08-20)
      — Segunda'dan Villalibre, Toney ve Ronaldo ile aynı "100"le yan yana çıkıyordu.
      Ölçüm: 2. lig oyuncuları en üst yüzde 10'un %8,5'i (1. lig %10,8) — listeyi basmıyorlar
      ama ayırt edilemiyorlar. Havuz bölünmedi, `strength_coef` "provisional" olduğu için
      ondan düzeltme türetilmedi; bunun yerine kartta lig adı ve "2. lig" işareti var.
      Ayrıca lig artık oyuncunun şu anki kulübünden değil **istatistiği kazandığı sezondan**
      geliyor: kulüpsüz oyuncunun satırı ligsiz kalıyordu ve kart "West Ham · Primeira Liga"
      diye okunuyordu.
- [x] 9 yeni lig yüklendi (✓ 2026-08-20)
      — Sırbistan 580 · Çekya 561 · Romanya 559 · Ukrayna 528 · Rusya 489 · İsviçre 387 ·
      Danimarka 369 · Hırvatistan 347 · Avustralya 334 satır (2025-26).
      Yunanistan'ın tablo şekli farklı (KeyError); izolasyon sayesinde diğer 9'u kurtardı.
- [x] Takvim yılı ligleri yüklendi (✓ 2026-08-20)
      — Arjantin 1.011 · MLS 796 · Brezilya A 694 · Brezilya B 691 · İsveç 424 · Norveç 420 ·
      Japonya 375 · Kore 342 satır, **"2026" sezonu** olarak. Sezon anahtarı düzeltmesi
      sayesinde doğru etiketlendi ve kopya oluşmadı.
- [x] Uyruk boşluğu kapatıldı: %5,69 → **%0,79** (✓ 2026-08-20)
      — ETL-2 FBref'in `nation` alanını `key_metrics`'e yazıyor ama oyuncuya hiç geçirmiyordu;
      `--create-missing` ile açılan 2.394 kayıt uyruksuz kalmıştı. FBref FIFA üç harfli kod
      kullanıyor, bizim kolon ISO alpha-2. Eşleme `data/reference/fifa_country_codes.csv`
      dosyasında — koda gömülmedi, çünkü yanlış uyruk (çalışma izni, kota) hiç yoktan kötüdür
      ve gözden geçirilebilir olmalı. 2.391 oyuncu yazıldı; sezonları farklı uyruk söyleyen
      3 oyuncuya dokunulmadı. Emin olunmayan tek kod (TCH) bilinçli olarak dışarıda.
- [x] Kalite raporu iki kontrolü doğru şeyi ölçüyor (✓ 2026-08-20)
      — `players.birth_date` yerine `players.yas bilgisi`: FBref gün vermediği için ikinci lig
      oyuncuları meşru olarak yalnızca `birth_year` taşıyor; eskisi bilgimizi değil depolama
      biçimimizi ölçüyordu (%5,24 → gerçek boşluk %0,38).
      `gol > şut` toleransı 5 → 50: 38 lig ve ~26 bin satırda 19 ihlal (binde 0,7), yalnızca
      2'si 900 dakika üstünde. Kaynak gürültüsü olduğu şöyle doğrulandı: sıfır şutlu satır
      oranı köklü liglerde de aynı (Premier Lig %7,7, La Liga %6,6) ve çoğu kaleci.
- [x] `/discover` varsayılan sezonu düzeltildi (✓ 2026-08-20)
      — Sezon etiketleri tek biçimde değil ("2026" takvim ligi, "2025-26" Avrupa) ve "2026"
      sözlük sırasında öne geçtiği için sayfa 8 ligin 303 forvetine düşmüştü; 25 ligin 1.818
      forveti bir seçim ötedeydi. Varsayılan artık **en kalabalık** sezon.
- [ ] (keşif) Yunanistan Super League FBref'te farklı kolon şemasıyla geliyor, ayrı okuma
      gerekiyor.
- [ ] (keşif) İskoçya ve İngiltere aynı ISO kodunda (GB): Birleşik Krallık'a tıklayınca 4 lig
      birden çıkıyor. Futbolda ayrı federasyonlar; ayırmak ISO 3166-2 alt bölüm kodları ve
      globe için ayrı centroid gerektirir.

## Faz 5 — Güncel sezon ve transfer tahtası
- [x] 2026-27 sezonu yüklendi (✓ 2026-08-20)
      — FBref yeni sezonu **bedava ve şu an** veriyor: 10 lig, 2.216 satır. Sezon 14 Ağustos'ta
      başladığı için maksimum dakika 90-360; 900 dakika kapısı sayesinde persentiller
      kendiliğinden 2025-26'da kalıyor, `/discover` bozulmuyor.
      Big-5'ten yalnızca La Liga başlamış (119 satır); diğerleri henüz oynamadı.
- [x] Lig kulüp listesi güncel sezona bağlandı (✓ 2026-08-20)
      — Süper Lig **43 → 18 kulüp**. Kardemir Karabükspor, Orduspor, Bursaspor gibi on yıl önce
      düşmüş takımlar listeden çıktı. Üyeliği sezon belirliyor, kadro büyüklüğünü canlı kaynak.
      Doğrulama: panel artık Amedspor / Yeni Çorumspor / Erzurumspor FK gösteriyor, Kayserispor /
      Karagümrük / Antalyaspor göstermiyor — Wikipedia'nın 2026-27 listesiyle birebir.
- [x] Yeni çıkan kulüpler `manual_mappings.csv` akışıyla çözüldü (✓ 2026-08-20)
      — ETL sessizce atlamadı, 13 kulübü eşleşmedi diye bildirdi. Erzurum BB → mevcut
      Erzurumspor FK (143); Amedspor ve Yeni Çorumspor yeni kayıt olarak açıldı.
- [x] ETL-4 `apifootball_transfers`: canlı transfer akışı (✓ 2026-08-20)
      — `transfers` ucu ücretsiz planda çalışıyor ve sezon parametresi almıyor, yani **güncel**.
      Süper Lig: 15 kulüp, 123 satır birleştirildi, 246 yeni satır. Kulüp başına 1 istek.
      Üç gürültü kaynağı filtrelendi: "Raise" (sözleşme yenileme), "End of career", ve serbest
      kalanlar için üretilen sahte takım ("Beşiktaş → Ucan Salih").
- [x] `GET /transfers` + web `/transfers` tahtası (✓ 2026-08-20)
      — Dönem / lig / yön / bonservis filtresi. Her satır kaynağını ve tarihin gün mü dönem mi
      olduğunu söyler. Üst bara "Transferler" bağlantısı eklendi.
- [x] Yeni çıkan 3 kulübün canlı kadrosu bağlandı (✓ 2026-08-20)
      — Süper Lig'in 18 kulübünün hepsi artık gerçek kadro büyüklüğüyle (23-41), forma
      sayısıyla değil. 521 oyuncu eşleşti, 3 istek harcandı.
      Yol boyunca iki gerçek hata çıktı ve düzeltildi:
      **(a) Ayırt edici olmayan arama terimi.** "Yeni Çorumspor" ilk uzun tokenıyla ("yeni")
      aranıyordu; uç nokta **Yeni Malatyaspor**'u döndürdü ve kimlik körlemesine yazılınca
      `uq_clubs_api_football_id` ihlaliyle koşu yarıda öldü. Artık genel kelimeler atılıyor,
      en uzun token önce geliyor, ve alınmış bir kimlik asla ikinci kulübe verilmiyor.
      **(b) Gençlik takımı A takım sanılıyordu.** "amedspor" araması yalnızca
      **"Amedspor U19"** döndürdü; adı tamamen içerdiği için eşleşti. `is_youth_team`
      artık U17-U23 / B / II / Reserves / Academy işaretlilerini reddediyor.
      Doğru kimlikler API'nin kendi şehir alanıyla doğrulandı: Amed → Diyarbakır (3579),
      Çorum FK → Çorum (6343).
- [ ] (keşif) `same_club` kapsama ilişkisidir, kimlik değil: "Çaykur Rizespor" ile "Rizespor"
      aynı kulüp, "Darıca Gençlerbirliği" ile "Gençlerbirliği" değil — ikisi de kapsama.
      Güvenliği sağlayan şey çağıranın "tek hayatta kalan" kuralı. Tek başına kullanılmamalı.
- [ ] (keşif) Transfer eşleşmesinde 80 oyuncu tanınmadı (alt lig / altyapı). manual_mappings'te.
- [ ] (keşif) Kulüplerin çoğunda `api_football_id` yok — ETL-3 yalnızca Süper Lig'e koştu.
      Bu yüzden transfer birleştirmesi kulüp *adına* düşüyor. Diğer ligler için ETL-3 gerekli.
- [ ] (keşif) Brezilya, MLS, J1, Arjantin'in hiç sezon verisi yok: takvim yılı ligleri
      "2627" anahtarıyla okunmuyor, ayrı bir koşu gerekiyor.
- [x] Alt ligler: 7 ikinci lig eklendi, 5'i yüklendi (✓ 2026-08-20)
      — **Championship 24 kulüp/379 · Segunda 22/350 · Ligue 2 18/315 · 2. Bundesliga 18/315 ·
      Scottish Championship 10/175.** İngiltere'ye tıklayınca artık 4 lig çıkıyor.
      Kaggle seti yalnızca birinci ligleri taşıdığı için kulüplerin hiçbiri eşleşmiyordu;
      ETL-2'ye `--create-missing` eklendi. Championship'te oyuncuların 274'ü zaten
      tanındı (Premier Lig'den düşen/kiralık), yalnızca 105'i yeni kayıt.
      İtalya Serie B henüz başlamamış; Brezilya Série B takvim yılı ligi, ayrı koşu gerekiyor.
- [ ] **TFF 1. Lig hâlâ yok ve bedava yolu da yok.** FBref'in yayımladığı yedi ikinci lig
      arasında Türkiye yok (ölçüm: FBref lig indeksinde 92 erkek kulüp yarışması).
      API-Football 1. Lig'i tanıyor (id=204) ama ücretsiz plan 2026 sezonunu kapatıyor.
      Yani Türkiye'nin alt ligi ücretli plan gerektiriyor.
- [ ] (keşif) Açılan ince oyuncu kayıtlarında `birth_date` yok, `birth_year` var — FBref gün
      vermiyor. Yaş bundan hesaplanıyor ve ±1 yıl şaşabilir. Transfermarkt bu oyuncuları
      kapsarsa `merge_duplicate_players` akışıyla birleştirilmeli.
- [ ] (keşif) İkinci lig kulüplerinin logosu ve oyuncu fotoğrafı yok (FBref yayımlamıyor).

## Faz 4 — Keşif Motoru (transfer önerisi)
- [x] Per-90 + pozisyon grubu z-score/persentil pipeline (`jobs/compute_metrics.py`) (✓ 2026-08-19)
      — **6.417 oyuncu-sezon** (900 dk üstü), `(sezon, pozisyon grubu)` içinde sıralanıyor.
      2025-26: DF 1.224 · MF 1.004 · FW 822 · GK 260. Kaynak birleştirme: hacim FBref'ten,
      beklenen gol Understat'tan, dakika ikisinin azamisi. `sample_size` her metrikle taşınıyor.
      Doğrulama: Haaland gol %98 / xG %99, Yamal gol %94 fakat kilit pas %99, Ndidi gol %53.
- [x] Rol vektörü üretimi → `player_vectors` (✓ 2026-08-19)
      — 7 eksen (`ROLE_AXES`), persentil uzayında [-1, 1]. **5.922 vektör**; dışarıda kalan 495
      tam olarak kaleciler. `vector(64)` yer tutucusu gerçek boyuta çekildi (migration 0008).
- [x] `/discover/similar/{id}` endpoint (pgvector kosinüs + bütçe/yaş/lig filtresi) (✓ 2026-08-19)
      — Yamal'a en yakınlar: Florucz (€4M, Belçika), Pagis (€15M), Ezzalzouli, Doué.
      Bütçe 25M + 23 yaş altı filtresi doğrulandı.
- [x] `GET /discover` + `/discover/options`: kriter → sıralı liste + gerekçe (✓ 2026-08-19)
      — `options` her metriğin kapsamını söylüyor (xG 1.404, gol 5.922 oyuncu-sezon) ki form
      sessizce aramayı 12 ligden 5'e daraltmasın.
- [x] Web `/discover` sayfası: pozisyon, sezon, metrik, bütçe, yaş, lig formu (✓ 2026-08-19)
      — Üst bara "Keşfet" bağlantısı eklendi (DESIGN.md §4). İlk liste sunucuda render ediliyor.
      Ekran görüntüsüyle doğrulandı: 24 kart, konsol temiz.
- [x] Transfer arc katmanı globe'a eklendi (sezon filtresi ile) (✓ 2026-08-19)
      — Ülke→ülke toplanmış akışlar, kalınlık transfer sayısına bağlı, `--arc-out` → `--grass`
      gradyanı ve dash animasyonu. `prefers-reduced-motion` altında animasyon duruyor.
      API sezon filtresini destekliyor; UI'da sezon seçici Faz 4'te.
- [x] Sonuç kartlarında "neden bu oyuncu" açıklaması (✓ 2026-08-19)
      — En güçlü 3 metrik + zayıf 2 yön + referanstan en geniş 3 persentil farkı. Her satırda
      persentil, per-90 değeri ve `n=` örneklem sayısı. Persentil aşağı yuvarlanıyor: 822 içinde
      en iyi olan 0,9994'tür ve bunu "100" diye yazmak kendisi dahil herkesin önünde demek olurdu.
- [x] Oyuncu profiline "Benzer profiller" bölümü (✓ 2026-08-19)
- [x] Radar grafiği (✓ 2026-08-20)
      — `GET /discover/radar/{id}`, pozisyona göre sabit eksenler, DESIGN.md pozisyon rampası
      rengiyle. Yanında per-90 tablosu, altında hangi popülasyona göre sıralandığı.
      Ölçülmemiş eksen çizilmiyor.
- [x] Kaleci metrikleri: FBref `keeper` tablosu ETL-2'ye eklendi (✓ 2026-08-20)
      — Kurtarış, kurtarış oranı, yenen gol, gol yememe, penaltı kurtarışı.
      `/discover?position_group=GK` artık boş dönmüyor. PSxG olmadığı için karşılaştığı şutun
      zorluğunu ölçemediğimiz her yanıtta yazılı.
- [x] Kaleci verisi 21 lige yüklendi, **553 kaleci sıralanıyor** (✓ 2026-08-20)
      — Yol boyunca üç hata çıktı ve üçü de veriye bakınca görüldü:
      **(a) Sahte kaleciler.** `players.position` "Goalkeeper" diyen beş oyuncu gol atıyordu;
      FBref onlara MF/FW diyor. Kariyer etiketi başka kaynaktan gelen bir özet ve yanılabiliyor.
      **(b) İlk token yanılgısı.** Sezon etiketini öne alınca bu sefer Ansu Fati (0.91 gol/90)
      orta sahaya düştü, çünkü FBref "MF,FW" yazıyor ve ilk tokenı alıyorduk.
      Kural artık **sezon daraltır, kariyer seçer** (`resolve_position_group`).
      **(c) Savunmanın notu kaleciye yazılıyordu.** Bazı ligler kurtarış vermeden yalnızca
      yenen gol ve gol yememe veriyor; bu ikisi kalecinin değil önündeki savunmanın hikâyesi.
      Listenin başındaki kaleci böyle biriydi. Kurtarış verisi olmayan kaleci artık sıralanmıyor.
- [ ] (keşif) Kaleci benzerliği kendi vektör uzayını istiyor: rol vektörünün yedi ekseni de
      şut ve üretim, kaleciye uygulanamaz.
- [ ] (keşif) İskoç Championship ve Ukrayna Premier Lig FBref'te kaleci tablosu sunmuyor;
      Polonya Ekstraklasa ve Yunanistan farklı kolon şemasıyla geliyor (KeyError).
      Koşu notları artık bunları isimleriyle bildiriyor, sessiz kalmıyor.
- [ ] Shortlist CRUD + karşılaştırma + PDF rapor

### Faz 4'te düzeltilen iki metodoloji hatası (2026-08-19)
İlk çalışan sürüm scout'a yanlış oyuncu gösteriyordu; ekran görüntüsünde yakalandı:
- **Disiplin metrikleri gerekçe olamaz.** 4. sıradaki forvetin "neden bu oyuncu"su
  "Az faul %99, Az sarı kart %94" idi — şutu %1, golü %2. `CONTEXT_METRICS` artık en güçlü
  yönlerin dışında; filtre ve zayıf yön olarak kalıyor.
- **Oranlara hacim kapısı.** 90 dakikada 1 şut atan bir oyuncu "İsabet oranı %99" ile listedeydi.
  Sezonda 20 şutun altında oran metrikleri hiç hesaplanmıyor (`MIN_SHOTS_FOR_RATIO`); oran
  taşıyan satır 5.922 → 2.998. Düzeltme sonrası ilk beş: Kane, Dybala, Osimhen, Pablo, Olise.

- [ ] (keşif) Kaleci metrikleri **alınabilir**: `soccerdata` FBref okuyucusu `stat_type="keeper"`
      destekliyor (kurtarış, gol yememe, PSxG). ETL-2'ye eklenirse kalecilerin persentili gerçek
      olur ve `/discover?position_group=GK` boş dönmeyi bırakır. Şu an bilinçli olarak boş.
- [ ] (keşif) Defansif rol benzerliği kör nokta: rol vektörünün yedi ekseni de şut/üretim/disiplin.
      FBref okuyucumuz pas ve defans tablolarını vermiyor; stoperler için benzerlik zayıf.
      Alternatif kaynak bulunmadan DF sonuçlarına scout gibi güvenilmemeli.

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
- [x] ~~(keşif) Belçika/İskoçya/Avusturya'da 307 satır kulüp eşleşmedi~~ → 10 kulüp elle eşlendi
      (✓ 2026-08-19). Sezon satırı 2.728 → **2.901**, eşleşmeyen oyuncu 109 → 60.
      Dikkat edilen tuzak: Club Brugge ile Cercle Brugge farklı kulüpler.
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
