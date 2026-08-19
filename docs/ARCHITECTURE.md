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
                  api_football_id, fbref_id, transfermarkt_id,
                  logo_url)                                    -- fbref_id = soccerdata anahtarı ("ENG-Premier League"),
                                                               -- transfermarkt_id = TM rekabet kodu ("GB1"); ETL-1
                                                               -- kulüpleri bu kodla lige bağlar (2026-08-18 eklendi)
clubs            (id, name, league_id→leagues, lat, lng,       -- globe noktaları
                  transfermarkt_id, api_football_id, logo_url)
players          (id, full_name, birth_date, nationality_code,
                  position, sub_position, foot, height_cm,
                  current_club_id→clubs, market_value_eur, contract_until,
                  transfermarkt_id, fbref_id, api_football_id, -- kaynaklar arası eşleme anahtarları
                  image_url)
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
player_season_metrics
                 (player_id, season, position_group PK, league_id, club_id, minutes,
                  per90 JSONB, zscore JSONB, percentile JSONB,
                  sample_size, metric_coverage)                -- keşif motorunun tabanı (2026-08-19)
player_vectors   (player_id, season, position_group,
                  embedding vector(7))                         -- pgvector, persentil uzayında rol vektörü
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

**Görseller neden URL, neden indirilmiyor (2026-08-19):** Oyuncu portresi Transfermarkt
dataset'inde `image_url` olarak geliyor; kulüp arması ve lig logosu ise TM'in kararlı URL
deseninden türetiliyor (`.../wappen/head/{club_id}.png`, `.../logo/header/{competition_id}.png`).
Görseller **indirilip yeniden yayınlanmıyor**: 46 bin portreyi kendi sunucumuzdan servis etmek,
ziyaretçinin tarayıcısının kaynağından çekmesine göre hukuken daha riskli bir yeniden yayın olur
(bkz. DATA_SOURCES.md ticari kullanım notu). Bedeli kırılganlık: kaynak referrer engellerse
görseller düşer, bu yüzden arayüzde her görselin baş-harf yedeği vardır ve hiçbir ekran görsele
bağımlı değildir. Ticarileşmede lisanslı görsel kaynağına geçilir.

**Persentil neden ayrı tabloda (2026-08-19):** "0.63 gol/90" tek başına bir şey söylemez;
anlam, aynı pozisyon grubundaki diğerlerine göre nerede durduğundadır. `player_season_metrics`
per-90 değerleri, pozisyon grubu içi z-score ve persentilleri materyalize eder. Materyalize
edilmesinin sebebi: FBref ile Understat aynı oyuncu-sezon için **ayrı satırlar** tutar ve
birleştirme kuralı (hacim FBref'ten, beklenen gol Understat'tan, dakika ikisinin azamisi)
sorgu içinde tekrarlanacak kadar önemsiz değildir. `sample_size` her metriğin kaç oyuncuya
karşı sıralandığını taşır — xG yalnızca Understat'ın 5 liginde var, hacim metrikleri 12 ligde;
persentili örneklem büyüklüğünü söylemeden vermek yanıltıcı olur.

**Rol vektörü ve benzerlik (2026-08-19):** `player_vectors.embedding` yedi eksenli
(`ROLE_AXES`: penaltısız gol, asist, şut, isabet oranı, şut başına gol, faul, sarı kart).
İskeletteki `vector(64)` metrik envanteri bilinmeden seçilmiş bir yer tutucuydu; yedi gerçek
sayıyı altmış dört sıfıra yaymak şemanın veride olmayan bir zenginliği iddia etmesi olurdu
(migration 0008, tablo boştu).

Üç karar:

1. **Neden yalnızca bu yedi eksen:** Oyuncu-sezonların ~%99'unda ve on iki ligin hepsinde
   bulunan tek metrikler bunlar. Beklenen gol metrikleri rolü çok daha iyi anlatırdı ama
   yalnızca beş ligde var (%24); karışıma katmak Süper Lig oyuncusunu sahip olmadığı eksenlerde
   karşılaştırmak olurdu. **Dürüst sınır:** bu eksenler şut, üretim ve disiplini ölçer —
   bir forveti iyi, bir stoperi çok zayıf tanımlar. FBref okuyucumuz pas/defans tablolarını
   vermiyor (DATA_SOURCES.md), yani defansif rol benzerliği bilinen bir kör nokta.
2. **Neden persentil uzayı, ham per-90 değil:** Değerler `(persentil − 0,5) × 2` ile [-1, 1]
   aralığına taşınır; sıfır "bu pozisyon ve sezonda medyan" demektir. Haaland'ın şut hacmi gibi
   tek bir aykırı değer geometriye hâkim olamaz.
3. **Neden kosinüs, neden ANN indeksi yok:** Kosinüs profilin *şekline* bakar, büyüklüğüne değil —
   scout'un asıl sorusu bu: aynı işi biraz daha az yapan ucuz oyuncu hâlâ benzerdir. Birkaç bin
   satır × yedi float taramak milisaniyelerle ölçülür ve kısa listeye girecek sonuçta kesin
   komşu, yaklaşığı yener.

**Kalecilerde persentil yok (2026-08-19):** Hiçbir kaynağımız kurtarış, gol yememe veya PSxG
yayımlamıyor. Kalecinin per-90 satırı gol ve şuttan ibaret, hepsi sıfır; bunları sıralamak
kimsenin ölçmediği bir niteliğe emin görünen bir persentil üretirdi. Satır yazılır (dakika ve
kulüp doğrudur) ama sıralama taşımaz ve API bunu boş liste yerine gerekçesiyle söyler.

**Gerekçesiz sonuç yok (2026-08-19):** Her keşif sonucu kendi kanıtını taşır. İki kural
metodolojiyi ayakta tutuyor:
- **Disiplin metrikleri "neden bu oyuncu" olamaz.** En güçlü yönü "faul yapmıyor" olan bir
  forvet, yaptığı bir şeyle değil bir faul sayısının yokluğuyla listeye girmiştir. Filtre ve
  zayıf yön olarak kalırlar, gerekçe olarak değil.
- **Oranların paydası olmalı.** Sezonda 20 şutun altında `goals_per_shot` ve
  `shots_on_target_pct` hiç hesaplanmaz: sekiz şutun beşini isabet ettiren stoper her forvetin
  önüne geçer ve herkesin sıralandığı dağılımı da bozar. O oyuncu artık o metriğin tepesinde
  değil, o metrikte yok.

**Bir ligde kim var: sezon söyler, canlı kadro söyleyemez (2026-08-20):** `/leagues/{id}`
her kulübü listeliyordu — Süper Lig 43 satır döndürüyor, 25'i on yıl önce küme düşmüş
(Kardemir Karabükspor, Orduspor). Bunları listenin dibine göndermek yetmez: **ligde olmayan
kulübü listeleyen bir lig tablosu yanlış sıralanmış değil, yanlıştır.**

Düzeltme iki soruyu ayırıyor:
- **Kim ligde?** Oynanan sezon karar verir; FBref'in lig sayfası çıkma-düşmenin otoritesidir.
  Canlı kadro bunu yanıtlayamaz — ETL-3 en son koştuğunda güncel olan kulüp kümesine göre
  toplanmıştır, bu yüzden yazdan sonra hâlâ düşen takımları taşır.
- **Kadro kaç kişi?** Canlı kaynak daha iyi bilir, özellikle ağustosta: sezonun ikinci
  haftasında yalnızca 15 oyuncu sahaya çıkmıştır, bu bir kadro değil bir forma sayısıdır.

Hiç sezon verisi olmayan lig için kayıtlı kadro tek cevaptır ve `squadSource` bunu söyler.

**Transferlerde iki kaynak, tek satır (2026-08-20):** Transfermarkt bonservisi taşıyor ama
tarihi dönem başına yuvarlıyor ve anlaşma sürerken hedefi boş bırakıyor; API-Football günü
veriyor, hedefi biliyor ve kiralık/bonservis ayrımını yapıyor, ama ücret yayımlamıyor.
Bu yüzden satırlar **çoğaltılmaz, birleştirilir**: aynı oyuncu ve aynı kulüpler için ±150 gün
içindeki kayıt aynı olaydır. Ölçüm: Vlahović Transfermarkt'ta "1 Temmuz'da Juventus'tan
ayrıldı, kimseye" olarak duruyordu; API-Football 11 Ağustos'ta Beşiktaş'a serbest transfer
diyordu. `sources` hangi kaynakların hemfikir olduğunu yazar.

Üç kural bu tabloyu dürüst tutuyor:
1. **`date_is_exact`.** Transfermarkt dört güne yığıyor — 1 Temmuz 47.599 · 30 Haziran 14.275 ·
   1 Ocak 11.744 · 31 Aralık 3.810, ortalama gün ise 219 (156.826 satır üzerinden ölçüldü).
   Bu 17-217 kat; futbol değil, dosyalama. O günlerdeki tarih "o dönem" demektir ve arayüz
   gün gibi yazmaz. En yoğun normal gün 1 Şubat (2.536) gerçek bir deadline'dır, dokunulmaz.
2. **Gelecek tarihli satır tahtaya girmez.** Transfermarkt kiralığın *bitiş* tarihini de
   transfer satırı olarak yazıyor; bu yüzden bugünün tahtasının en üstünde Haziran 2027 vardı.
3. **Karşı tarafın adı saklanır.** Bir Süper Lig kulübünün penceresinin yarısı kapsamımızı
   aşıyor (Sakaryaspor, Al-Jazira); ad olmadan satır "hiçbir yere gitti" diye okunur.

Kaggle importer'ı oyuncu bazında sil-yeniden yaz yapıyor; bu silme artık **yalnızca kendi
kaynağını** hedefliyor. Aksi halde her yeniden koşu, API-Football'un doğruladığı her hareketi
silerdi — ETL-2'nin bir sezonun diğer liglerini silen hatasının aynısı.

**Alt ligler ve kayıt açma (2026-08-20):** Kaggle Transfermarkt seti yalnızca birinci
ligleri taşıyor, bu yüzden Championship'in 24 kulübünün hiçbiri `clubs` tablosunda yoktu ve
her satır "kulüp eşleşmedi" diye atlanıyordu. ETL-2'ye `--create-missing` eklendi: bir ligin
kendi FBref sayfasında adı geçen kulüp o ligdedir, belirsizlik yoktur. Bayrak açık olmadan
davranış değişmez — sessiz kayıt açma, kimlik eşlemesini bozma riskini taşır.

Oyuncularda dürüstlük kısıtı var: FBref doğum **yılı** veriyor, gün vermiyor. Boşluğu
1 Ocak ile doldurmak scouting raporuna uydurma bir doğum günü yazmak olurdu, o yüzden
`players.birth_year` eklendi ve yaş tam tarih yoksa ondan hesaplanıyor (±1 yıl şaşabilir,
ama "bilinmiyor"dan iyidir). Championship'te 379 oyuncunun 274'ü zaten tanındı; ince kayıt
yalnızca 105 tanesi için açıldı.

**Tek lig hepsini götürmemeli (2026-08-20):** soccerdata, sezonu başlamamış bir ligin
sayfasında istatistik tablosu bulamayınca hata fırlatıyor. Birleşik okuma bunu tüm koşuya
yayıyordu: beş liglik bir çalışma, biri başlamadığı için hiçbir şey döndürmedi. Artık her
lig tek tek okunuyor, hatası kendinde kalıyor ve atlananlar raporlanıyor — ETL-2'nin bir
ligin sorununu diğerinin verisine bulaştıran eski replace hatasıyla aynı sınıf.

**Kayıt açarken tekilliği kim korur (2026-08-20):** Eşleştiricilerin indeksleri koşunun
başında bir kez kuruluyor ve koşu sırasında açılan kayıtları bilmiyor. FBref bir oyuncuyu
**kulüp başına bir kez** yazdığı için sezon içinde takım değiştiren biri üç satır üretiyor;
`--create-missing` her satıra ayrı kayıt açınca Efe Ugiagbe veritabanına üç kez girdi
(Ceuta, Cádiz, Huesca). Artık koşu kendi açtıklarını `(normalize(ad), doğum yılı)` ile
hatırlıyor. Sezon satırlarının üçü de gerçek ve korunuyor — adam gerçekten üç kulüpte oynadı.

Geriye kalan kopyalar `merge_duplicate_players` işine yeni bir geçiş olarak eklendi: dış
kimliği olmayan ince kayıtlar ad + doğum yılı ile birleştirilir, `uq_player_season_source`
çakışması olursa fazla satır silinir. Dış kimliği (Transfermarkt/API-Football) olan kayıta
dokunulmaz — ad eşleşmesinden daha güçlü bir kimliği vardır.

**Persentil lig gücüne göre düzeltilmez (2026-08-20):** Sıralama tuttuğumuz bütün ligleri tek
havuza koyar. Ölçüm: ikinci lig oyuncuları en üst yüzde 10'un %8,5'i, birinci lig %10,8'i —
yani listeyi basmıyorlar, ama içinde ayırt edilemiyorlar. Segunda'dan Villalibre, Toney ve
Ronaldo'yla aynı "100" ile yan yana çıktı. Havuzu bölmedik (keşif için tek karşılaştırılabilir
ölçek gerekiyor) ve `strength_coef` hâlâ "provisional" olduğu için ondan düzeltme türetmedik;
bunun yerine **satır nereden geldiğini söylüyor**: lig adı ve 2. lig işareti kartta.

Sonuçtaki lig, oyuncunun *şu an* bulunduğu kulüpten değil, **istatistiği kazandığı sezondan**
geliyor. İkisi farklı sorular ve ikincisi birincisini yanıtlayamıyor: kulüpsüz bir oyuncunun
satırı hiç ligsiz kalıyordu. Ayrıca kart "West Ham United · Primeira Liga" diye okunuyordu;
kulüp kendi satırında, lig sezonun yanında.

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
