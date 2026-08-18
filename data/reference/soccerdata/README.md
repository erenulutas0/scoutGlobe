# soccerdata lig tanımları

soccerdata FBref için yalnızca Big-5'i ve büyük turnuvaları hazır tanıyor
(`ENG-Premier League`, `ESP-La Liga`, `FRA-Ligue 1`, `GER-Bundesliga`, `ITA-Serie A`).
Bizim ihtiyacımız olan keşif ligleri — Eredivisie, Primeira Liga, Süper Lig,
Brasileirão, Belçika, Arjantin... — kütüphanede tanımlı değil.

`config/league_dict.json` bu ligleri **ekler**. Kütüphanenin desteklediği yol budur
(`{**LEAGUE_DICT, **custom}`), ve dosya repoda durduğu için CI ile başka geliştiricinin
makinesi aynı sonucu verir.

## Kurallar

- **Sadece ekleme yapılır, mevcut giriş ezilmez.** Örneğin `GER-Bundesliga`'yı buradan
  düzeltmeye kalkmak `read_leagues()` yolunu bozar; Big-5 birleşik sayfasındaki
  Bundesliga etiket hatası kod tarafında (`jobs/common/fbref.py` →
  `BIG_FIVE_LABEL_FIXES`) düzeltilir.
- `FBref` alanı, FBref'in rekabet sayfasındaki **birebir** adı olmalı
  (ör. `Campeonato Brasileiro Série A`, `Süper Lig`).
- Buraya eklenen her lig anahtarı, `data/reference/leagues.csv` içindeki `fbref_id`
  ile aynı olmalı — ETL-2 lig eşlemesini bu anahtar üzerinden yapar.

`SOCCERDATA_DIR` bu klasöre `services/etl/jobs/__init__.py` içinde işaret edilir;
soccerdata import edilmeden önce ayarlanması şart.
