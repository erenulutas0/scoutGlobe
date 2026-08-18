# DATA_SOURCES.md — Veri Kaynakçası

> ETL yazarken önce buraya bak. Her kaynak için: ne verir, limit ne, nasıl erişilir, dikkat notu.
> Kural: **her ham yanıt `data/raw/<kaynak>/` altına kaydedilir** — aynı veri iki kez istenmez.

## Katman 1 — Ücretsiz API'ler (yapılandırılmış, güvenilir)

| Kaynak | Ne verir | Limit / Erişim | Not |
|---|---|---|---|
| **API-Football** (api-sports.io) | 1200+ lig: kadrolar, oyuncu sezon istatistikleri, fikstür, transferler, sakatlıklar | Free: ~100 istek/gün; ücretli ~$25+/ay | Süper Lig dahil geniş kapsam. Kota bütçesi kodda sabit; agresif cache şart. |
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

| Araç | Kapsadığı kaynaklar | Not |
|---|---|---|
| **soccerdata** (probberechts) | FBref, Understat, Sofascore, SoFIFA, WhoScored, ClubElo, ESPN, Football-Data.co.uk | Birincil tercih: tek API, pandas çıktı, yerel cache. FBref = sezonluk gelişmiş istatistik (xG, progressive, defansif). |
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
player_season_stats (Big-5)                      ← soccerdata/FBref (ETL-2)
player_season_stats (Süper Lig) + kadrolar       ← API-Football (ETL-3)
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
