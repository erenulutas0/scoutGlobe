# DATA_SOURCES.md — Veri Kaynakçası

> ETL yazarken önce buraya bak. Her kaynak için: ne verir, limit ne, nasıl erişilir, dikkat notu.
> Kural: **her ham yanıt `data/raw/<kaynak>/` altına kaydedilir** — aynı veri iki kez istenmez.

## Katman 1 — Ücretsiz API'ler (yapılandırılmış, güvenilir)

| Kaynak | Ne verir | Limit / Erişim | Not |
|---|---|---|---|
| **API-Football** (api-sports.io) | 1200+ lig: kadrolar, oyuncu sezon istatistikleri, fikstür, transferler, sakatlıklar | Free: **100 istek/gün + 10 istek/dakika** | Ölçülen plan kısıtları aşağıda. |

> **2026-08-19 saha notu (ETL-3):** Ücretsiz planda **sezon parametreli uç noktalar yalnızca
> 2022-2024**'e erişiyor (`"Free plans do not have access to this season"`). Yani sezon
> istatistiği için API-Football free, elimizdeki Kaggle verisinden (2026) **daha eski** —
> istatistik oraya bağlanmaz.
> Buna karşılık **`players/squads` sezon parametresi almıyor ve GÜNCEL kadroyu döndürüyor**.
> Bu, projedeki tek gerçek zamanlı sinyaldir; ETL-3 sadece bunu alır.
> Dakikada 10 istek sınırı var → istekler arası 6,5 sn bekleme, 429 durumunda 65 sn geri çekilme.
> Kota bütçesi `jobs/common/apifootball.py` içinde koda gömülü; istemci bütçeyi aşmayı reddeder.
| **football-data.org** | Üst turnuvalar: fikstür, puan durumu, kadrolar | Üst ligler ücretsiz (kalıcı), 10 istek/dk | Oyuncu bazlı derin istatistik zayıf; fikstür/kadro iskeleti için iyi. |
| **ClubElo API** (clubelo.com/API) | Kulüp Elo puanları (tarihsel) | Ücretsiz, CSV | `strength_coef` (lig/kulüp katsayısı) için birincil kaynak. |

## Katman 2 — Açık Veri (indir ve kullan)

| Kaynak | Ne verir | Erişim | Not |
|---|---|---|---|
| **StatsBomb Open Data** | Profesyonel event verisi (paslar, şutlar, konumlar) + 360 verisi; seçili turnuvalar | GitHub: `statsbomb/open-data`; Python: `statsbombpy` | Model geliştirme/öğrenme altını. Canlı scouting için değil (kapsam sınırlı). Atıf şartına uy. |
| **Kaggle: Transfermarkt "player-scores"** (davidcariboo/player-scores) | Oyuncular, kulüpler, piyasa değeri GEÇMİŞİ, transferler, maç görünümleri | Kaggle API ile indir; düzenli güncelleniyor | **Faz 1'in bel kemiği.** `market_value_history` ve `transfers` tabloları buradan. |
| **openfootball / football.db** | Tarihsel fikstür, takım, turnuva verisi (public domain) | GitHub repoları | Tarihsel iskelet; istatistik yok. |
| **Wyscout açık veri (2017/18)** | Big-5 + EURO2016 + WC2018 event verisi (akademik yayın eki) | figshare "A public data set of spatio-temporal match events" | ML deneyleri için ek eğitim verisi. |

## Katman 3 — Scraping Sarmalayıcıları (Python)

> **2026-08-18 saha notu (ETL-2):** FBref'in Big-5 birleşik sayfası yalnızca
> `standard`, `keeper`, `shooting`, `playing_time`, `misc` tablolarını veriyor;
> `passing`/`defense`/`possession` sadece lig bazlı okumada var. Ayrıca soccerdata'nın
> `BIG_FIVE_DICT` tablosu Almanya ligini `Fußball-Bundesliga` sanıyor, FBref ise
> `Bundesliga` yazıyor → düzeltilmezse **tüm Bundesliga satırları sessizce `NaN` lige düşer**
> (2025-26'da 507 oyuncu). Düzeltme ve koruma: `services/etl/jobs/common/fbref.py`.

| Araç | Kapsadığı kaynaklar | Not |
|---|---|---|
| **soccerdata** (probberechts) | FBref, Understat, Sofascore, SoFIFA, WhoScored, ClubElo, ESPN, Football-Data.co.uk | Birincil tercih: tek API, pandas çıktı, yerel cache. ⚠️ **FBref artık xG yayınlamıyor** (2026-08-18'de 2024-25 ve 2025-26 sayfalarında tek bir xG sütunu yok) → xG/xAG için Understat kullanılacak. |
| **ScraperFC** | Transfermarkt, Capology (maaş!), FBref, Understat | Capology maaş verisi bütçe filtresi için değerli. |
| **statsbombpy** | StatsBomb open data | Resmi kütüphane. |
| **understatapi** | Understat xG (6 büyük lig) | soccerdata alternatifi. |

**Scraping disiplini (zorunlu):** istekler arası bekleme (FBref için ≥3-6 sn), tek thread, cache-first,
User-Agent düzgün, gece saatleri tercih. Site engellerse ısrar etme — kaynağı değiştir.
**Hukuki not:** Scraping ile toplanan veri kişisel/araştırma kullanımı için makul gri alan; **ticari üründe
yeniden yayınlamadan önce** kaynak ToS'ları gözden geçirilmeli, uzun vadede lisanslı veriye (API-Football
ücretli tier gibi) geçiş planlanmalı. Transfermarkt/FBref verisini "ham tablo olarak yeniden satmak" yapılmaz;
türetilmiş analiz/skor sunmak farklı ve savunulabilir konumdur (yine de hukuki tavsiye değildir).

## Katman 4 — Türkiye Nişi (rekabet avantajı burada)

| Kaynak | Ne verir | Not |
|---|---|---|
| **TFF resmi site** (tff.org) | Süper Lig'den 3. Lig'e + altyapı ligleri: fikstür, kadrolar, temel istatistik | Yapılandırılmış API yok → özel scraper görevi (Backlog'da). Büyük sağlayıcıların zayıf olduğu alan. |
| **Mackolik / Sahadan** | Türk ligleri canlı skor, kadro, temel istatistik | Unofficial; sadece keşif amaçlı incele. |
| API-Football | Süper Lig + 1. Lig kapsamı mevcut | Alt ligler için kapsamı doğrula (görev). |

## Katman 5 — Farkında Ol (ücretli / kurumsal — MVP'de KULLANMA)

Wyscout, StatsBomb (ücretli), Opta/Stats Perform, SkillCorner, TransferRoom, InStat.
→ Kulüplerin ne kullandığını bilmek satış konuşması için gerekli; fiyatları kurumsal seviyede.

## Kaynak → Tablo Eşlemesi (özet)

```
players, clubs, transfers, market_value_history  ← Kaggle Transfermarkt (ETL-1)
player_season_stats (Big-5) hacim metrikleri     ← soccerdata/FBref (ETL-2)
player_season_stats (xg/xa dahil, ayrı satır)    ← Understat (ETL-2b) — source='understat'
güncel kadrolar (canlı)                          ← API-Football players/squads (ETL-3)
player_season_stats (Süper Lig)                  ← FBref (ETL-2, ücretsiz planda API-Football'dan taze)
leagues.strength_coef                            ← ClubElo (+ elle UEFA katsayısı)
countries (koordinatlar)                         ← data/reference/countries.csv (statik)
(ileri faz) event verisi / radar grafikler       ← StatsBomb open data
```

## Bağlantılar
- https://github.com/statsbomb/open-data
- https://www.kaggle.com/datasets/davidcariboo/player-scores
- https://github.com/probberechts/soccerdata · https://soccerdata.readthedocs.io
- https://github.com/oseymour/ScraperFC
- https://www.api-football.com · https://www.football-data.org · http://clubelo.com/API
- https://github.com/openfootball
- https://fbref.com · https://www.transfermarkt.com · https://understat.com
- https://www.tff.org
