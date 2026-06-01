# 🎬 Video Konuşma Metni — PPO ile GPS'siz Drone Keşfi

> Sözlü anlatım için yazıldı (Berker, birinci ağız). **[EKRAN: ...]** = o an göstereceğin şey.
> Tahmini süre ~9-11 dk. İstersen bölümleri kes/birleştir. Rahat, anlatır gibi oku.

---

## 0. Açılış (≈30 sn)
**[EKRAN: başlık / harita görseli — `figurler/03_v4_8_GUVENLI_kapsama.png`]**

"Merhaba. Bu projede, GPS'i olmayan bir drone'un kapalı bir binayı yalnızca lidar ve odometri
kullanarak keşfetmesini, pekiştirmeli öğrenme — yani PPO algoritması — ile çözdüm. Amaç basit
ama zor: drone, **çarpışmadan**, binadaki **mümkün olduğunca çok alanı** dolaşacak. Ortamda
hareketli engeller de var, yani durağan değil. Şimdi bu hedefe nasıl ulaştığımı, yol boyunca
neyi denediğimi ve neyi öğrendiğimi anlatacağım."

---

## 1. Problem ve Ortam (≈45 sn)
**[EKRAN: harita figürü — odalar R0–R5 etiketli]**

"Ortamım tek katlı, **6 odalı** sabit bir bina. Drone her zaman aynı noktadan, sol alttaki
R0 odasından başlıyor. Haritada 3 tane hareketli engel sürekli gidip geliyor. Drone'un yaptığı
hareket iki boyutlu: ileri-geri hız ve dönüş hızı; irtifa sabit, yani havada asılı kalıyor.

Ödülü şöyle tasarladım — felsefe çok net: **toplam ödül, gezilen voxel — yani yeni hücre —
sayısına eşit olsun.** Her yeni hücre +1, yeni bir odaya geçince bonus, çarpışınca büyük ceza.
Harita 1024 hücreye bölünüyor; 'kapsama' dediğim şey bu hücrelerin yüzde kaçını gezdiğimiz."

---

## 2. Yolculuğun Üç Fazı — Genel Bakış (≈40 sn)
**[EKRAN: RAPOR.md §2 'Üç Faz' tablosu]**

"Proje üç fazdan geçti. Birinci faz: Gazebo simülatöründe, daha karmaşık 3 katlı bir haritada
ilk kurulum. İkinci faz: problemi basitleştirip yine Gazebo'da temiz bir tasarım. Üçüncü faz —
ki asıl sonuçlar burada — aynı ortamı numpy ile çok daha hızlı bir simülatöre taşıdım. Şimdi
sırayla gidelim, çünkü her fazda kritik bir ders var."

---

## 3. Faz 1 — İlk Kurulum ve İlk Ders (≈40 sn)
**[EKRAN: RAPOR.md §3 — v1–v8 tablosu]**

"İlk denemelerde drone 3 katlı, 12 odalı bir haritada, üç boyutlu hareketle eğitiliyordu.
Sekiz versiyon denedim. Sorun şuydu: ödül bir tepe yapıp sonra **geri düşüyordu** — politika
kararlı yakınsamıyordu. VecNormalize ile en iyi tepeyi yakaladım ama yine de istikrar yoktu.
Buradan çıkan ders şuydu: **problem fazla karmaşık.** O yüzden her şeyi basitleştirmeye karar
verdim — tek kat, daha az boyut. Bu, ikinci fazı doğurdu."

---

## 4. Faz 2 — Temiz Tasarım ve EN ÖNEMLİ Ders (≈1 dk)
**[EKRAN: RAPOR.md §4 — v2.0/v2.1/v2.2 tablosu; `figurler/10_gazebo_v2_0_kapsama.png`]**

"İkinci fazda sıfırdan başladım: tek kat, 6 oda, iki boyutlu hareket, sade bir ödül. Burada
**çok öğretici bir şey** oldu. Drone'un asıl problemi çarpışmaydı — özellikle hareketli engellere.
Ben de mantıken 'ödüle daha akıllı çarpışma cezaları ekleyeyim' dedim. Mesela 'sadece önünde
engel varsa cezalandır' gibi yön-duyarlı cezalar.

**Ama tam tersi oldu.** v2.0'da sade ceza ile çarpışma %70'ti; akıllı saydığım v2.1'de %79'a,
v2.2'de %88'e **çıktı.** Yani ödülü karmaşıklaştırmak işi kötüleştirdi. En sade versiyon en iyiydi.
Buradan çıkan ders: **bu problem bir ödül-şekillendirme problemi değil.** Asıl sorun başka yerdeydi
— drone, engelin **hareket ettiğini görmüyordu**, sadece o anki uzaklığı görüyordu."

---

## 5. Pivot — Neden Hızlı Simülatöre Geçtim (≈40 sn)
**[EKRAN: §2 notu — '~100× hızlı, 4000 fps']**

"Bu noktada önemli bir karar verdim. Gazebo gerçekçi ama **çok yavaş** — saniyede ~40 adım.
Tek bir 1.5 milyonluk eğitim saatler sürüyordu. Hâlbuki Gazebo bu proje için bir zorunluluk değildi.
Aynı ortamı numpy ile, iki boyutlu ışın-tarama mantığıyla yeniden yazdım — neredeyse **yüz kat
hızlı**, saniyede ~4000 adım. Böylece bir gecede 14 farklı deney yapabildim. Önemli not: **Gazebo
sonuçlarını silmedim** — onları da rapora koydum, çünkü 'Gazebo'da şu çıktı, numpy'de bu çıktı'
diye iki ayaklı bir kanıt sunuyor."

---

## 6. Çarpışmanın Çözümü — Projenin Kalbi (≈1 dk)
**[EKRAN: `figurler/07_fast_v2_carpisma_cozuldu_kapsama.png`]**

"Şimdi projenin en kritik bulgusu. Çarpışmayı ödülle çözemediğimizi görmüştüm. Çözüm
**gözlemdeydi**. Drone'a tek bir lidar karesi yerine **son iki lidar karesini** verdim. Tek kare
ile drone sadece 'engel şu an şurada' bilgisini görüyor. İki kare ile **engelin hangi yöne, ne
hızla gittiğini** çıkarabiliyor — ve önünden çekilebiliyor.

Sonuç inanılmazdı: çarpışma oranı **%80'den %1'e** düştü. Aylarca ödül ayarıyla çözemediğim şeyi,
doğru gözlem tasarımı bir hamlede çözdü. Bu, projenin en güçlü mesajı: **bazen çözüm ödülde değil,
ajana ne gösterdiğindedir.**"

---

## 7. Yeni Problem ve Trade-off Çalışması (≈1 dk)
**[EKRAN: RAPOR.md §5.2 — v4.0→v5.0 büyük tablo]**

"Ama çarpışmayı çözünce yeni bir sorun çıktı: drone artık o kadar temkinli oldu ki **sadece 2 odaya
sıkışıp** kaldı, 'riske girmeyeyim' diye yeni odalara gitmiyordu. Yani güvenli ama dar.

Bunun üzerine 14 deneylik bir seri yaptım — v4.0'dan v5.0'a. Dört farklı kaldıracı tek tek denedim:
ödül parametreleri, eğitim süresi, önceki modelden devam etme, ve gözlem zenginliği. Amacım hem
**geniş** hem **güvenli** bir politika bulmaktı. Şimdi en kritik birkaç versiyonu göstereyim."

---

## 8. v4.1 — Yanıltıcı 'İyi' Sonuç / TUZAK (≈50 sn)
**[EKRAN: `figurler/13_v4_1_YOGUN_kapsama.png` — ısı haritasında sadece 2 oda parlak]**

"Önce bir uyarı niteliğinde örnek. Şu v4.1 versiyonu ilk bakışta harika görünüyor: çarpışma sadece
%2, ve bölüm başına 150 voxel — bu rakam diğerlerinden bile yüksek. Ama figüre dikkatlice bakın:
**sadece 2 oda parlıyor.** Drone yeni odalara hiç gitmemiş; başladığı bölgedeki 2 odayı defalarca,
çok yoğun taramış. Yani yüksek voxel sayısı **yanıltıcı** — aynı yeri tekrar tekrar geziyor.

Bizim hedefimiz binanın **tamamını** dolaşmaktı; v4.1 bunu yapmıyor. Bu yüzden bunu bir başarı
değil, kaçmamız gereken bir **yerel optimum tuzağı** olarak sunuyorum. Bu örnek şunu öğretti:
asıl mesele voxel sayısı değil, **kaç farklı odaya yayıldığın.**"

---

## 9. v4.8 — ASIL CEVAP (≈1 dk)
**[EKRAN: `figurler/03_v4_8_GUVENLI_kapsama.png` ve `04_v4_8_GUVENLI_yorunge.png`]**

"İşte aradığım denge: v4.8. Burada çok ilginç, sezgiye aykırı bir bulgu var. Çarpışma cezasının
'tatlı noktasını' aradım. Cezayı çok yükseltince drone aşırı tedirgin olup hatalar yapıyordu.
Cezayı 30'dan **25'e düşürünce** çarpışma %8'den **tam %0'a** indi. Yani daha az ceza, daha güvenli
sonuç — çünkü ajan artık panik yapmıyor.

Sonuç: v4.8'de **100 denemenin 100'ünde de hiç çarpmadı**, her bölümde 6 odanın 5'ine yayıldı, ve
tam süre boyunca hayatta kaldı. Voxel sayısı 117 — v4.1'den düşük, ama bu sefer voxeller **5 farklı
odaya** dağılmış, sadece 2 odada değil. İşte 'çarpışmadan, geniş alanı keşfet' hedefinin gerçek
cevabı **bu.** Teslim ettiğim ana modelim v4.8."

---

## 10. v4.10 — Kapasite Tavanı (≈45 sn)
**[EKRAN: `figurler/05_v4_10_KAPSAM_kapsama.png` — neredeyse tüm harita parlak]**

"Bir de modelin sınırını görmek istedim. v4.8'in aynı ayarını alıp **çok daha uzun** eğittim — 5
milyon adım. Sonuç: voxel 117'den **281'e** fırladı, **6 odanın hepsini** gezdi, kapsama %44.5'e
çıktı — haritanın neredeyse yarısı. Bakın, figürde nerdeyse her yer parlak.

**Ama** bunun bedeli: çarpışma %54'e çıktı. Yani drone çok şey keşfediyor ama yarı yarıya çarpıyor.
Gerçek bir görevde bu kabul edilemez. O yüzden bunu 'en iyi model' değil, **modelin keşif kapasitesi
ne kadar yüksek olabilir' tavanını** gösteren bir kanıt olarak sunuyorum. v4.8 güvenli cevap, v4.10
tavan."

---

## 11. Pareto Cephesi — Hepsini Tek Resimde (≈45 sn)
**[EKRAN: `figurler/01_pareto_cephesi.png`]**

"Bütün bu deneyleri tek bir grafikte topladım: yatay eksen çarpışma oranı, dikey eksen kapsama.
Burada gördüğümüz şey bir **Pareto cephesi** — yani temel bir ödünleşim. Sol üstte 'hem geniş hem
güvenli' olmak isterdik ama o bölge boş; ulaşılamıyor. Yeşil nokta v4.8 — düşük çarpışma tarafında.
Kırmızı nokta v4.10 — yüksek kapsama ama yüksek çarpışma tarafında.

14 deneyin sonucu net: bu ortamda, bu ödülle, **kapsama-genişliği ile güvenlik arasında temel bir
ödünleşim var.** Dört farklı yöntemle denedim, hiçbiri bu cepheyi kıramadı. Yani bu bir
başarısızlık değil — bilimsel olarak **kanıtlanmış bir sınır.**"

---

## 12. Gazebo vs numpy — İki Ayaklı Kanıt (≈30 sn)
**[EKRAN: yan yana — `11_gazebo_v2_0_yorunge.png` ve `04_v4_8_GUVENLI_yorunge.png`]**

"Son olarak iki simülatörü kıyaslayayım. Yavaş ama gerçekçi Gazebo'da en iyi sonucum çarpışma %70,
kapsama %36'ydı. Hızlı numpy simülatöründe ise v4.8 ile **%0 çarpışma** ve 5 oda elde ettim. Aynı
ortam, iki farklı motor — sonuçlar birbirini doğruluyor ve hızlı sürüm çok daha derin deney yapmamı
sağladı."

---

## 13. Kapanış + Ekip (≈30 sn)
**[EKRAN: RAPOR.md §8 'Gelecek İş' + ekip tablosu]**

"Özetle: Çarpışmayı **doğru gözlem tasarımıyla** çözdüm. Ardından kapsama ile güvenlik arasındaki
temel ödünleşimi 14 deneyle haritaladım ve iki model teslim ettim — güvenli cevap v4.8, kapasite
tavanı v4.10. Bu cepheyi daha da iyiye taşımak için gelecekte LSTM tabanlı politika ya da SAC gibi
yöntemler denenebilir.

Bu, dört kişilik bir ekip projesi; ben PPO ile çalıştım, takım arkadaşlarım aynı ortamda A3C, TD3
ve DQN ile çalışıp karşılaştırma yapıyor. Beni dinlediğiniz için teşekkürler."

---

### 🎯 Anlatırken hatırla (kısa notlar)
- **En vurucu 3 cümle:** (1) Çarpışmayı ödül değil GÖZLEM çözdü (%80→%1). (2) Sezgiye aykırı: cezayı
  DÜŞÜRÜNCE çarpışma %0'a indi (v4.8). (3) v4.1 tuzak: çok voxel ama 2 oda — hedef genişlik.
- **v4.1'i mutlaka 'tuzak' diye anlat**, başarı gibi değil.
- Rakamları ezberlemene gerek yok; figürdeki ısı haritası (kaç oda parlıyor) hikâyeyi tek başına anlatır.
- Sıralama: problem → çarpışma çözümü → trade-off → v4.1 tuzak → v4.8 cevap → v4.10 tavan → Pareto.
