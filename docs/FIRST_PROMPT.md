# FIRST_PROMPT.md
> Aşağıdaki bloğu olduğu gibi kopyala ve proje klasöründe Claude'a ilk mesaj olarak ver.
> ÖN KOŞUL: 6 md dosyasını (CLAUDE.md kökte; ARCHITECTURE, TODO, DATA_SOURCES, DESIGN docs/ altında)
> repoya koymuş ol. Node 20+, pnpm, Docker ve Python 3.12 + uv kurulu olsun.

---

Merhaba! **ScoutGlobe** projesini birlikte inşa edeceğiz: futbolcu istatistiklerini toplayan,
kulüplere ihtiyaç bazlı transfer önerisi üreten ve "future star" adaylarını erken tespit etmeyi
hedefleyen bir platform. Arayüzün kalbi, Three.js ile uzaydan görünen interaktif bir dünya —
ülkeye tıkla → lige in → oyuncuları keşfet.

## Önce oku (sırayla)
1. `CLAUDE.md` — çalışma sözleşmemiz ve kuralların
2. `docs/ARCHITECTURE.md` — tüm mimari kararlar (stack, monorepo yapısı, DB şeması, API yüzeyi)
3. `docs/TODO.md` — görev listesi ve görev takip kuralların
4. `docs/DATA_SOURCES.md` — veri kaynakları, kotalar, scraping disiplini
5. `docs/DESIGN.md` — görsel yön; UI'da bunun dışına çıkma

Bu dosyalar tartışıldı ve karara bağlandı. Onlarla çelişen bir şey yapma; mimariyi değiştirmek
gerekirse önce bana gerekçesiyle sor, onaylarsam ARCHITECTURE.md'yi güncelleyip öyle devam et.

## Bu oturumun görevi
**Faz 0'ın tamamı + Faz 1'e giriş + görünür bir globe.** Somut olarak:

1. **Monorepo iskeleti** (ARCHITECTURE.md §3'teki yapı birebir): pnpm + Turborepo;
   `apps/web` (Next.js + TS + Tailwind + shadcn/ui), `packages/core`, `packages/config`,
   `services/api` (FastAPI + uv, `/health` çalışır), `services/etl`, `db/`, `docs/`.
2. **Veritabanı:** `db/docker-compose.yml` ile Postgres 16 + pgvector ayakta;
   Alembic kurulu ve ARCHITECTURE.md §4'teki **tam şema** ilk migration olarak uygulanmış.
3. **Seed:** `data/reference/countries.csv` (ülke kodu, isim, lat/lng) + Big-5 ligleri ve
   Süper Lig `leagues` tablosunda.
4. **Globe hello-world:** Ana sayfada react-globe.gl sahnesi (`next/dynamic`, ssr:false) —
   DESIGN.md'deki uzay zemini, atmosfer, ülke polygon katmanı (world-atlas TopoJSON),
   hover'da ülke highlight + isim etiketi. Henüz veri bağlamak zorunda değilsin; sahne dursun.
5. **ETL-1 başlangıcı:** Kaggle Transfermarkt "player-scores" datasetini indirip
   `players`, `clubs`, `transfers`, `market_value_history` tablolarına yükleyen job'ın
   iskeleti + en az `clubs` ve `players` importunun çalışır hali. (Kaggle kimliği gerekiyorsa
   `.env.example`'a ekle ve benden iste.)
6. **Hijyen:** kök `README.md` (kurulum adımları), `.env.example` dosyaları, `.gitignore`
   (`data/raw/`, `.env`), `pnpm lint` ve `pnpm typecheck` yeşil, git init + anlamlı commitler.

## Kabul kriterleri (kendin doğrula, bana kanıtla)
- [ ] `docker compose up` + `alembic upgrade head` temiz makinede sorunsuz (README'deki adımlarla)
- [ ] `pnpm dev` → localhost'ta dönen globe görüyorum, ülke hover çalışıyor
- [ ] `GET /health` 200 dönüyor; API ve web aynı komutla kalkıyor
- [ ] `psql`'de `SELECT count(*) FROM leagues;` ≥ 6, countries dolu
- [ ] ETL-1 çalıştırıldığında `players` tablosuna satır yazıyor ve `ingest_runs`'a log düşüyor
- [ ] `docs/TODO.md` güncellendi: bitenler ✓ + tarih, keşfedilenler Backlog'da

## Çalışma tarzı
- Küçük adımlar, her mantıksal adımda commit. Uzun sessizlik yok: ne yaptığını kısaca anlat.
- Bir kütüphane/versiyon seçiminde tereddüt edersen güncel dokümantasyonuna bak, uydurma.
- Bloke olursan (ör. Kaggle anahtarı, ağ erişimi) o görevi atla, TODO'ya not düş, devam et.
- Oturum sonunda rapor ver: **ne bitti / ne yarım / önümüzdeki oturumun ilk 3 görevi.**

Hazırsan `CLAUDE.md`'yi ve `docs/` klasörünü okuyarak başla; kısa bir plan özeti verip Faz 0'a gir.
