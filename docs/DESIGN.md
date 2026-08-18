# DESIGN.md — Görsel Yön ve Tasarım Sistemi

> Konsept: **"Gece maçı, uzaydan izleniyor."** Yayın grafiği telemetrisi + scouting radarı.
> Bu bir dashboard şablonu değil; kahraman öğe her zaman **globe**. UI onun etrafında sessiz durur.
> Her renk/tip kararı buradan türetilir; keyfi renk eklenmez.

## 1. İmza Öğe (tek cesaret noktası)

Dünya üzerinde **animasyonlu transfer arc'ları**: satış yönünde akan, lig gücüne göre kalınlaşan
ışık iplikleri. Ülkeye zoom yapınca arc'lar o ülkeye filtrelenir. Sitenin hatırlanacağı görüntü budur;
geri kalan her şey disiplinli ve sakin kalır.

## 2. Renk Tokenları

Renk süsleme değil, **anlam** taşır. Tek neon aksanlı jenerik koyu tema YASAK; renkler işlevle eşleşir.

```css
:root {
  --bg-space:      #060B1A;  /* uzay zemini — saf siyah değil, gece mavisi */
  --bg-panel:      rgba(13, 20, 38, 0.72);  /* cam panel (backdrop-blur ile) */
  --stroke-panel:  rgba(148, 163, 199, 0.14);
  --text-primary:  #E9EDF6;  /* projektör beyazı */
  --text-muted:    #8A96B5;

  --grass:         #35D98B;  /* çim — SADECE veri pozitifi: form artışı, uygun aday, ✓ */
  --scout-amber:   #F5B241;  /* keşif ambeni — SADECE future-star / potansiyel sinyali */
  --alert-coral:   #F26D6D;  /* düşüş, sözleşme riski, negatif trend */
  --arc-out:       #5B8CFF;  /* transfer arc başlangıcı (satan) → --grass'a gradient (alan) */
}
```

- Pozisyon grupları için veri rampası: GK `#8A96B5` · DF `#5B8CFF` · MF `#35D98B` · FW `#F5B241`
  (globe noktaları ve grafiklerde tutarlı kullanılır → renk okumayı öğretir).
- Kural: bir ekranda `--grass` ve `--scout-amber` aynı anda büyük alan kaplayamaz.

## 3. Tipografi

| Rol | Font | Kullanım |
|---|---|---|
| Display | **Clash Display** (Fontshare, ücretsiz) | Sayfa başlıkları, ülke/lig adları globe panelinde. Weight 500-600, tracking -0.02em. Az ve büyük kullan. |
| Body | **Instrument Sans** (Google Fonts) | Paragraf, form, liste. 15-16px, satır 1.6. |
| Data | **IBM Plex Mono** | TÜM istatistik rakamları, tablolar, skorlar, per-90 değerler. `font-variant-numeric: tabular-nums`. Yayın telemetrisi hissi buradan gelir. |

İstatistik asla body fontuyla yazılmaz — rakam gördüğün yerde mono görürsün.

## 4. Yerleşim

```
┌──────────────────────────────────────────────┐
│ ◉ ScoutGlobe        arama(⌘K)      [Keşfet]  │  ← ince üst bar, cam
│                                              │
│                                    ┌────────┐│
│              🌍 GLOBE              │ PANEL  ││  ← sağ cam panel: drill-down
│         (her zaman görünür)        │ ülke → ││     ülke→lig→oyuncu
│                                    │ lig →  ││
│                                    │ oyuncu ││
│                                    └────────┘│
└──────────────────────────────────────────────┘
```

- Panel `backdrop-blur` cam; globe'un %35'inden fazlasını kapatmaz (desktop).
- **Mobil:** panel bottom-sheet olur (yarım aç/tam aç); globe üstte kalır, nokta sayısı düşürülür.
- Oyuncu profili ayrı sayfa: solda kimlik kartı + değer grafiği, sağda mono istatistik tabloları,
  radar grafik pozisyon rampası renginde.
- Boşluk ölçeği 4px taban; kart radius 14px; gölge yok, ışık var (ince stroke + glow sadece globe'da).

## 5. Hareket (disiplinli)

- Sayfa açılışı: globe hafif scale+rotate ile yerleşir (three-globe'un kendi init animasyonu yeter).
- Arc'lar: sürekli dash animasyonu — sahnenin "canlı" tek öğesi.
- Panel geçişleri: 180-220ms ease-out slide+fade. Liste öğelerinde stagger YOK (veri ciddiyeti).
- Hover: satır arka planı %4 açılır, o kadar. `prefers-reduced-motion` → arc animasyonu durur, kamera anlık atlar.

## 6. Arayüz Dili (copy)

- Türkçe, sade fiiller, cümle düzeni kısa: "Kısa listeye ekle", "Benzerlerini bul", "Filtrele".
- Skorlar açıklanır, pazarlanmaz: "Potansiyel 78 — dakika trendi + lig-ayarlı üretim" gibi.
- Boş ekran yönlendirir: "Bir ülkeye tıklayarak başla."
- Hata net: "API-Football günlük kotası doldu. Yarın 03:00'te yenilenir."

## 7. Kalite Tabanı (pazarlıksız)

- Klavye ile tüm drill-down gezilebilir; görünür focus ring (`--grass` %60 opak).
- Kontrast: metin/muted AA'yı geçer (koyu zeminde test et).
- Globe yüklenirken iskelet: karanlık küre + "Veri yükleniyor" mono etiketi — spinner değil.
- Lighthouse perf ≥ 85 hedefi (globe sayfası hariç diğer sayfalar ≥ 95).
