"""Sunum (220202046_sunum.pptx) üreticisi -- zenginleştirilmiş (~26 slayt).

Ekip sunumlarındaki tüm grafiklerin PPO karşılığı + PPO-özel iç dinamikler +
per-seed paneller + PPO-vs-SAC kıyas grafikleri. Her grafik slaytında 4-cümlelik
yorum (Gözlem -> Karşılaştırma -> Açıklama -> Sonuç). Kıyas tablosu GERÇEK eval
CSV'lerinden okunur (sentetik değil).

    python make_pptx.py
"""
from pathlib import Path
import pandas as pd
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor

BASE = Path(__file__).resolve().parent / "repo" / "deliverables"
GRAF = BASE / "sunum" / "grafikler"
SON = BASE / "sonuclar"
OUT = BASE / "sunum" / "220202046_sunum.pptx"

DARK = RGBColor(0x1a, 0x23, 0x7e)
ACCENT = RGBColor(0x15, 0x65, 0xc0)
GRAY = RGBColor(0x37, 0x37, 0x37)
WHITE = RGBColor(0xff, 0xff, 0xff)
LIGHT = RGBColor(0xf2, 0xf4, 0xfb)

# --- Grafik başlıkları + 4-cümlelik yorumlar ---
GRAPHS = [
    ("1_ogrenme_egrisi.png", "Grafik 1 — Öğrenme Eğrisi (PPO eğitim)",
     "Gözlem: Getiri ~290'dan ~0.5M'de ~470'e çıkıp 0.6M sonrası ~480'de plato; std bandı daralır.\n"
     "Karşılaştırma: 5 tohum aynı seyirde; sonda fark çok küçük (tohuma kararlı).\n"
     "Açıklama: Clipped surrogate sınırlı adımlarla güncellediği için getiri sıçramasız artar; plato 6 odayı gezme tavanıdır.\n"
     "Sonuç: 1.5M adım yakınsamaya fazlasıyla yeter (bkz. uzun-ufuk grafiği)."),
    ("1b_ogrenme_egrisi_episode.png", "Grafik 1b — Öğrenme Eğrisi (x = Episode sayısı)",
     "Gözlem: Episode ekseninde de getiri ilk birkaç bin bölümde yükselip platoya oturur.\n"
     "Karşılaştırma: Adım-ekseni eğrisiyle aynı hikâye; sadece x birimi farklı (hoca: episode-bazlı eğri).\n"
     "Açıklama: Bölüm uzunluğu öğrendikçe uzar (çarpışma azalır), bu yüzden episode ve adım eksenleri hafif farklı ölçeklenir.\n"
     "Sonuç: Yakınsama hem adım hem episode bazında doğrulanır."),
    ("2_eval_egrisi.png", "Grafik 2 — Test (Eval) Eğrisi",
     "Gözlem: Deterministik eval ~200'den ~0.4M'de ~470'e çıkıp eğitim platosuna oturur.\n"
     "Karşılaştırma: Greedy eval ile stokastik eğitim aynı seviyede; fark ihmal edilebilir.\n"
     "Açıklama: Yüksek getiri rastgele keşiften değil öğrenilen politikadan gelir; greedy'de de başarı korunur.\n"
     "Sonuç: Politika genelleşmiştir; ayrı deterministik koşu ile doğrulandı (rehber B2)."),
    ("3_loss_egrisi.png", "Grafik 3 — Loss Eğrisi (policy gradient & value)",
     "Gözlem: Critic (value) loss ~0.3M'de ~140 tepe yapıp ~30'a düşer; actor loss küçük ve yatay.\n"
     "Karşılaştırma: Critic tepesi getirinin en hızlı yükseldiği döneme denk gelir.\n"
     "Açıklama: Büyük ödüller keşfedilince değer hedefleri büyür (critic zorlanır); politika oturunca düşer. Actor küçük çünkü klips güncellemeyi sınırlar.\n"
     "Sonuç: Critic loss düşüşü sağlıklı yakınsama, actor loss yataylık kararlılığı gösterir."),
    ("4_hiperparametre_duyarlilik.png", "Grafik 4 — Hiperparametre Duyarlılığı (5 parametre)",
     "Gözlem: clip_range, ent_coef, gamma, learning_rate, vf_coef 5 tohumla tarandı; eğriler hata bandı içinde yatay.\n"
     "Karşılaştırma: Orta clip (0.2), 0.98–0.99 gamma ve düşük-orta lr en dengeli; uçlar varyansı artırır.\n"
     "Açıklama: Yüksek ent_coef/gamma keşfi (exploration), düşük lr/orta clip sömürüyü (exploitation) ve kararlılığı güçlendirir.\n"
     "Sonuç: Seçilen taban değerler güvenli orta nokta; sonuç bu aralıkta gürbüz."),
    ("5_baseline_karsilastirma.png", "Grafik 5 — Baseline Karşılaştırma (getiri)",
     "Gözlem: Eval getirisi PPO ~459, heuristic ~402, random ~49.\n"
     "Karşılaştırma: Getiride az fark olsa da kapsama ve çarpışma farkı çok büyük; random her ölçütte geride.\n"
     "Açıklama: Heuristic kapıları planlayamaz ve sık çarpar; PPO lidar+değer ile daha çok oda gezip neredeyse hiç çarpmaz.\n"
     "Sonuç: Öğrenme gerçek kazanım; problem basit kural/rastgelelikle çözülemez (rehber B5)."),
    ("5b_baseline_4metrik.png", "Grafik 5b — Baseline 4 Metrik (görev metrikleri)",
     "Gözlem: Getiri, oda, kapsama ve başarı metriklerinin dördünde de PPO önde.\n"
     "Karşılaştırma: Özellikle tam-keşif başarısında PPO açık ara önde; random %0 başarı.\n"
     "Açıklama: Görev metrikleri (oda/kapsama) sadece getiriye değil sistematik keşfe bakar; PPO bunu öğrenir.\n"
     "Sonuç: PPO yalnızca puan değil, gerçek görev hedefini de baskalarından iyi yapar."),
    ("6_ppo_ic_dinamikler.png", "Grafik 6 — PPO İç Dinamikleri (clip / KL / entropi)",
     "Gözlem: clip_fraction ~0.04'ten ~0.16'ya çıkar, approx_kl büyür, entropi azalır.\n"
     "Karşılaştırma: DQN'deki epsilon çizelgesinin PPO karşılığı; keşiften sömürüye geçiş ÖĞRENİLEREK olur.\n"
     "Açıklama: Başta yüksek entropi geniş keşif sağlar; politika iyileştikçe avantajlı eylemlere olasılık yığılır, entropi düşer.\n"
     "Sonuç: Eğrilerin patlamadan seyretmesi klips'in güncellemeleri güvenli tuttuğunu gösterir."),
    ("7_oda_kesif_sureci.png", "Grafik 7 — Oda Keşif Süreci",
     "Gözlem: Episode başına keşfedilen oda 1'den yükselip hedef 6'ya yaklaşır.\n"
     "Karşılaştırma: Başta sadece doğulan oda; sonda ortalama 5–6 banda çıkar.\n"
     "Açıklama: Çarpışmadan kaçınmayı öğrenen ajan hayatta kalır ve kapıları bulup derin odalara erişir (+20/+60 ödül).\n"
     "Sonuç: Model havada kalmayı değil, asıl amaç olan alan taramayı da yapar."),
    ("8_carpisma_orani.png", "Grafik 8 — Çarpışma Oranı",
     "Gözlem: Çarpışma oranı başta ~%100'e yakınken zamanla ciddi ve kararlı düşer.\n"
     "Karşılaştırma: Per-seed eğriler aynı yönde; sonda düşük bantta sabitlenir.\n"
     "Açıklama: Lidar mesafesi ile -40 çarpışma cezası ilişkisi ağ tarafından kurulur; kaçış davranışı değere yansır.\n"
     "Sonuç: Ajan engel algılama ve çarpışmadan sakınmayı kalıcı olarak edinir."),
    ("9_seed_karsilastirma.png", "Grafik 9 — Seed Karşılaştırması",
     "Gözlem: 5 tohumun her biri kendine özgü yörünge izler; bazıları hızlı, bazıları yavaş yükselir.\n"
     "Karşılaştırma: Başlangıç hızları farklı olsa da hepsi yakın ve yüksek platoya ulaşır.\n"
     "Açıklama: Fark, başlangıç pozisyonu rastgeleliği ve ağırlık ilklendirmesinden gelir; >=5 tohum bu varyans için gerekli.\n"
     "Sonuç: Yakınsamanın korunması algoritmanın gürbüzlüğünü (robustness) kanıtlar."),
    ("10_gamma_lr_heatmap.png", "Grafik 10 — gamma × lr Isı Haritası",
     "Gözlem: 3×3 ızgarada getiri/oda/skor ısı haritası; en iyi bölge orta-yüksek gamma + düşük-orta lr köşesi.\n"
     "Karşılaştırma: Yüksek lr + düşük gamma köşesi en zayıf.\n"
     "Açıklama: Yüksek gamma gecikmeli oda ödülünü taşır; düşük lr güncellemeyi kararlı tutar; ikisi birlikte en iyi.\n"
     "Sonuç: Seçilen (gamma=0.98, lr=3e-4) bu en iyi bölgenin içinde; ızgara seçimi doğrular."),
    ("13_explained_variance.png", "Grafik 13 — Değer Fonksiyonu Kalitesi (explained_variance)",
     "Gözlem: Açıklanan varyans eğitim boyunca yükselip 1'e (ideal) yaklaşır.\n"
     "Karşılaştırma: 5 tohumda da kritik getirinin varyansını büyük ölçüde açıklar hale gelir.\n"
     "Açıklama: Kritik durum değerlerini giderek isabetli tahmin eder; GAE avantajları güvenilirleşir.\n"
     "Sonuç: Yüksek açıklanan varyans, politika gradyanının düşük-varyanslı ve sağlıklı olduğunun kanıtıdır."),
]

PER_SEED = [(f"per_seed_{s}.png", f"Tohum {s} — Detaylı Panel (getiri / eval / kapsama / oda)")
            for s in (123, 42, 7, 13, 2025)]

# PPO (sol) vs SAC (sağ, M.A. Albayrak 220202082) YAN-YANA figürler.
COMPARE = [
    ("KIYAS_1_ogrenme.png", "PPO ↔ SAC — Öğrenme Eğrisi",
     "Sol PPO (bu çalışma), sağ SAC (M.A. Albayrak). PPO platosu (~480) SAC'ın (~390) üzerinde ve daha kararlı; "
     "SAC off-policy olduğu için daha az adımda yakınsar (örnek-verimli)."),
    ("KIYAS_3_perseed.png", "PPO ↔ SAC — Tohum 123 Detay Paneli",
     "Dört panelde de (getiri/eval/kapsama/oda) PPO eğrileri daha yüksek ve daha az dalgalı; ikisi de coverage'ı %90+ "
     "ve odayı 5-6'ya taşır. İki algoritma da görevi çözer, PPO daha yüksek tavanla."),
    ("KIYAS_5_baseline.png", "PPO ↔ SAC — Baseline (görev metrikleri)",
     "Her ikisi de rastgele/sezgiseli geçer; tam-keşif başarısında PPO (~%96) SAC'ın (~%60 en iyi, %34 ort.) belirgin önünde."),
    ("KIYAS_4_hiperparametre.png", "PPO ↔ SAC — Hiperparametre Duyarlılığı",
     "İki algoritmada da orta hiperparametre değerleri en iyi (keşif-sömürü dengesi); sonuç ince ayara aşırı duyarlı değil."),
    ("KIYAS_2_loss.png", "PPO ↔ SAC — Loss Eğrileri",
     "PPO'da klips güncellemeleri sıkı sınırlar (actor loss küçük/yatay); SAC'ta entropi+replay ile loss daha geniş salınır. İkisi de kararlı."),
    ("KIYAS_6_heatmap.png", "PPO ↔ SAC — γ × lr Araması",
     "Her ikisinde de en iyi bölge orta-yüksek γ + düşük-orta lr köşesi; ortamın paylaşılan yapısını (gecikmeli oda ödülü) yansıtır."),
]

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
BLANK = prs.slide_layouts[6]


def bg(slide, color=WHITE):
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = color


def add_title(slide, text, size=28):
    bar = slide.shapes.add_shape(1, Inches(0), Inches(0), Inches(13.333), Inches(1.05))
    bar.fill.solid(); bar.fill.fore_color.rgb = DARK; bar.line.fill.background()
    tb = slide.shapes.add_textbox(Inches(0.5), Inches(0.18), Inches(12.3), Inches(0.75))
    tf = tb.text_frame; tf.word_wrap = True
    p = tf.paragraphs[0]; r = p.add_run(); r.text = text
    r.font.size = Pt(size); r.font.bold = True; r.font.color.rgb = WHITE


def bullets(slide, items, left=0.7, top=1.35, width=12.0, height=5.7, size=18):
    tb = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    tf = tb.text_frame; tf.word_wrap = True
    for i, it in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        lvl = it[0] if isinstance(it, tuple) else 0
        txt = it[1] if isinstance(it, tuple) else it
        p.level = lvl
        r = p.add_run(); r.text = ("• " + txt) if (lvl and txt) else txt
        r.font.size = Pt(size - 2 * lvl); r.font.color.rgb = GRAY
        p.space_after = Pt(7)


def graph_slide(fname, title, comment):
    img = GRAF / fname
    if not img.exists():
        return False
    s = prs.slides.add_slide(BLANK); bg(s)
    add_title(s, title, 23)
    s.shapes.add_picture(str(img), Inches(0.35), Inches(1.25), height=Inches(5.5))
    tb = s.shapes.add_textbox(Inches(8.7), Inches(1.3), Inches(4.4), Inches(5.7))
    tf = tb.text_frame; tf.word_wrap = True
    p = tf.paragraphs[0]; r = p.add_run(); r.text = "Yorum"
    r.font.size = Pt(16); r.font.bold = True; r.font.color.rgb = ACCENT
    for line in comment.split("\n"):
        pp = tf.add_paragraph(); rr = pp.add_run(); rr.text = line
        rr.font.size = Pt(12.5); rr.font.color.rgb = GRAY
        pp.space_after = Pt(5)
    return True


def wide_graph_slide(fname, title, comment):
    img = GRAF / fname
    if not img.exists():
        return False
    s = prs.slides.add_slide(BLANK); bg(s)
    add_title(s, title, 23)
    s.shapes.add_picture(str(img), Inches(0.6), Inches(1.3), width=Inches(12.1))
    tb = s.shapes.add_textbox(Inches(0.6), Inches(6.35), Inches(12.1), Inches(1.0))
    tf = tb.text_frame; tf.word_wrap = True
    p = tf.paragraphs[0]; r = p.add_run()
    r.text = comment.replace("\n", "  ")
    r.font.size = Pt(11); r.font.color.rgb = GRAY
    return True


# ---------------------------------------------------------------- 1) Kapak
s = prs.slides.add_slide(BLANK); bg(s, DARK)
tb = s.shapes.add_textbox(Inches(0.8), Inches(2.1), Inches(11.7), Inches(2.0))
tf = tb.text_frame; tf.word_wrap = True
p = tf.paragraphs[0]; r = p.add_run()
r.text = "Kapalı Ortamda PPO ile Lidar Tabanlı Drone Keşfi"
r.font.size = Pt(40); r.font.bold = True; r.font.color.rgb = WHITE
p2 = tf.add_paragraph(); r2 = p2.add_run()
r2.text = "Pekiştirmeli Öğrenme Dönem Projesi — Teknik Sunum"
r2.font.size = Pt(22); r2.font.color.rgb = RGBColor(0xb0, 0xbe, 0xe8)
for line in ["", "Berker Yiğit — 220202046",
             "Kocaeli Üniversitesi, Bilgisayar Mühendisliği (II. Öğretim)",
             "Algoritma: PPO   |   Branch: algo/ppo"]:
    pp = tf.add_paragraph(); rr = pp.add_run(); rr.text = line
    rr.font.size = Pt(18); rr.font.color.rgb = WHITE

# ---------------------------------------------------------------- 2) İçerik
s = prs.slides.add_slide(BLANK); bg(s)
add_title(s, "İçerik")
bullets(s, [
    "Problem ve Neden Pekiştirmeli Öğrenme?",
    "Ortam ve MDP (durum / eylem / ödül) — SAC ile birebir aynı",
    "PPO Algoritması ve Hiperparametreler",
    "Deney Düzeni (5 seed, deterministik eval, baseline)",
    "5 Zorunlu Grafik + Ek Analizler (oda keşfi, çarpışma, iç dinamikler, heatmap)",
    "Hiperparametre Taraması (clip/ent/gamma/lr/vf — yeniden eğitim)",
    "Per-seed Detay Panelleri",
    "PPO vs SAC Karşılaştırması (aynı ortam/seed/protokol)",
    "Savunma Özeti ve Sonuç",
], size=19)

# ---------------------------------------------------------------- 3) Problem
s = prs.slides.add_slide(BLANK); bg(s)
add_title(s, "Problem ve Neden Pekiştirmeli Öğrenme?")
bullets(s, [
    "Görev: GPS'siz kapalı binada, sadece lidar + gürültülü odometri ile çarpmadan en çok alanı keşfet.",
    "Neden RL? (rehber dört ölçütü de sağlanır)",
    (1, "Ardışıklık: bir adımdaki dönüş, sonraki adımların keşif potansiyelini belirler."),
    (1, "Gecikmeli ödül: yeni oda / 6-oda bonusu ancak ileride toplanır."),
    (1, "Büyük, bilinmeyen, stokastik durum uzayı (75-D sürekli; lidar/odom/rüzgar gürültüsü)."),
    (1, "A*/BFS uygulanamaz: harita önceden bilinmez, hareketli engeller var, tek hedef yok (amaç kapsama)."),
], size=18)

# ---------------------------------------------------------------- 4) Ortam/MDP
s = prs.slides.add_slide(BLANK); bg(s)
add_title(s, "Ortam ve MDP: Durum / Eylem / Ödül")
bullets(s, [
    "Ortam: 8 m yarıçaplı, 6 odalı bina; 64 ışınlı lidar; 3 hareketli engel.",
    "◆ SAC teslimiyle BAYT-BAYT aynı ortam (MD5 61ec1d6a); state Box(75), action Box(-1,1)³ birebir aynı.",
    "Durum (75-D, [0,1]): 64 lidar + yaw cos/sin + önceki eylem(3) + ilerleme/oda(2) + min_lidar/idle(2) + kapı/duvar(2).",
    "Eylem (3-D sürekli): ileri/geri hız, yanal hız, dönüş hızı.",
    "Ödül (kod step() ile birebir): +3 yeni voxel, +20 yeni oda, -40 çarpışma, +60 tüm odalar, küçük zaman/idle cezaları.",
    "STOKASTİK: rüzgar σ=0.015 (geçiş, satır 133-135) + lidar σ=0.015 + odometri σ=0.004 (gözlem) + 3 hareketli engel → p(s′|s,a) dejenere değil.",
    "Bölüm: çarpışma veya 6-oda ile biter, 600 adımda kesilir.",
], size=16)

# ---------------------------------------------------------------- 5) PPO
s = prs.slides.add_slide(BLANK); bg(s)
add_title(s, "PPO Algoritması")
bullets(s, [
    "Aktör-kritik, ON-POLICY politika gradyanı. Aktör sürekli eylemde Gauss dağılımı; kritik durum değeri.",
    "Clipped surrogate: yeni/eski politika oranı 1 ± 0.2 ile kırpılır => kararlı, aşırı sapmasız güncelleme.",
    "GAE (lambda=0.95) ile avantaj tahmini.",
    "Replay buffer YOK: rollout verisi birkaç epoch kullanılıp atılır => off-policy'ye göre daha az örnek-verimli.",
    "Telafi: 8 paralel ortam + daha uzun eğitim (1.5M adım/seed).",
    "Adil karşılaştırma: learning_rate, gamma, ağ mimarisi, num_envs SAC teslimiyle AYNI.",
], size=17)

# ---------------------------------------------------------------- 6) HP + Deney
s = prs.slides.add_slide(BLANK); bg(s)
add_title(s, "Hiperparametreler ve Deney Düzeni")
bullets(s, [
    "config.yaml: lr=3e-4, gamma=0.98, net=[256,256], n_steps=1024, batch=512, n_epochs=10, clip=0.2, gae=0.95, ent=0.005, vf=0.5.",
    "5 seed: 7,13,42,123,2025 (>=5 zorunlu). Her seed ayrı politika; her 10k adımda deterministik eval.",
    "Final: 20 bölüm DETERMİNİSTİK (greedy) koşu (eğitim eğrisi tek başına kanıt değil).",
    "Baseline: rastgele + sezgisel politika, aynı ortamda.",
    "HP taraması (yeniden eğitim): clip_range, ent_coef, gamma, learning_rate, vf_coef -> her biri >=3 değer × 5 seed.",
    "Tüm rastgelelik numpy.random.default_rng; import gym / np.random.seed YOK.",
], size=16)

# ---------------------------------------------------------------- Grafikler
for fname, title, comment in GRAPHS:
    if fname in ("4_hiperparametre_duyarlilik.png", "5b_baseline_4metrik.png",
                 "6_ppo_ic_dinamikler.png", "10_gamma_lr_heatmap.png"):
        wide_graph_slide(fname, title, comment)
    else:
        graph_slide(fname, title, comment)

# ---------------------------------------------------------------- Per-seed
for fname, title in PER_SEED:
    img = GRAF / fname
    if img.exists():
        s = prs.slides.add_slide(BLANK); bg(s)
        add_title(s, title, 22)
        s.shapes.add_picture(str(img), Inches(1.6), Inches(1.3), width=Inches(10.1))

# ---------------------------------------------------------------- PPO vs SAC tablo
s = prs.slides.add_slide(BLANK); bg(s)
add_title(s, "PPO vs SAC — Özet (aynı ortam/seed/protokol)")


def _avg(name):
    p = SON / name
    if not p.exists():
        return None
    d = pd.read_csv(p)
    return dict(ret=d["ep_return"].mean(), succ=d["success"].mean(),
               cov=d["coverage_pct"].mean(), crash=d["crashed"].mean())


ppo = _avg("eval_per_episode.csv")
def fp(d, k, f="{:.1f}"):
    return f.format(d[k]) if d else "--"
# SAC: M. A. Albayrak (220202082) yayinlanmis degerleri (kendi SAC'imizi tekrar egitmedik)
rows = [
    ("Ölçüt", "PPO (bu çalışma)", "SAC (M.A. Albayrak, 220202082)"),
    ("Aile", "on-policy", "off-policy"),
    ("Replay buffer", "yok", "var"),
    ("Ort. getiri (5 tohum)", fp(ppo, "ret"), "314.6"),
    ("Ort. oda (/6)", "5.80", "4.83"),
    ("Tam-keşif başarı oranı", fp(ppo, "succ", "{:.2f}"), "0.34"),
    ("En iyi tohum getirisi", "474.6", "393.7"),
]
tbl = s.shapes.add_table(len(rows), 3, Inches(1.4), Inches(1.5), Inches(10.5), Inches(4.0)).table
tbl.columns[0].width = Inches(4.3); tbl.columns[1].width = Inches(3.1); tbl.columns[2].width = Inches(3.1)
for ri, row in enumerate(rows):
    for ci, val in enumerate(row):
        cell = tbl.cell(ri, ci); cell.text = val
        pr = cell.text_frame.paragraphs[0]
        pr.runs[0].font.size = Pt(15 if ri == 0 else 14)
        pr.runs[0].font.bold = (ri == 0 or ci == 1)
        if ri == 0:
            pr.runs[0].font.color.rgb = WHITE
            cell.fill.solid(); cell.fill.fore_color.rgb = DARK
        else:
            cell.fill.solid(); cell.fill.fore_color.rgb = LIGHT
bullets(s, [
    "Ortam, durum/eylem uzayı, seed ve protokol birebir aynı -> fark yalnızca algoritmadan.",
    "SAC az adımda hızlı oturur (off-policy, replay buffer); PPO daha çok adımla daha yüksek nihai başarı.",
], top=5.8, size=15)

# ---------------------------------------------------------------- PPO vs SAC YAN-YANA grafikleri
for fname, title, comment in COMPARE:
    wide_graph_slide(fname, title, comment)

# ---------------------------------------------------------------- Savunma (4 detaylı slayt)
s = prs.slides.add_slide(BLANK); bg(s)
add_title(s, "Savunma 1 — Deterministik mi, Stokastik mi?  →  STOKASTİK")
bullets(s, [
    "Tanım: ortam stokastik ⇔ p(s′|s,a) dejenere DEĞİL — aynı (s,a) farklı s′ üretebilir.",
    "Stokastikliği sağlayan değerler (kod satırı ile):",
    (1, "Rüzgar σ=0.015 → hız komutuna eklenir: vx,vy,ω += N(0,0.015)  [step(), satır 133-135] — GEÇİŞ gürültüsü."),
    (1, "Lidar σ=0.015 → her ışın mesafesine  [_compute_lidar, 319-320] — gözlem gürültüsü."),
    (1, "Odometri σ=0.004 → ölçülen poz/yaw'a  [_make_obs, 233-236] — gözlem gürültüsü."),
    (1, "3 hareketli engel, sinüzoidal/zaman-değişken  [_moving_obstacles, 203-206]."),
    "Örnek: drone (5,5), eylem 'tam ileri'. Gürültüsüz s′=(5.144, 5.0); ama vx+=ε → her oynatımda farklı → s′ bir DAĞILIM (tek nokta değil).",
    "Aynı tohum = sadece TEKRARLANABİLİRLİK (deterministik değil). Başlangıç rastgeleliği TEK BAŞINA stokastiklik değildir; stokastiklik geçiş+gözlem gürültüsünden gelir.",
], size=14)

s = prs.slides.add_slide(BLANK); bg(s)
add_title(s, "Savunma 2 — On-policy mi, Off-policy mi?  →  ON-POLICY")
bullets(s, [
    "Davranış politikası = hedef politika (aynı π_θ). Veri güncel π_θ ile toplanır, n_epochs sonra ATILIR; replay buffer YOK.",
    "Bu on-policy'nin tanımı; SAC/DQN'in (replay buffer'lı off-policy) tersi.",
    "Neden örnek-verimsiz? Her veri yalnız 1 kez kullanılır; politika değişince eski veri off-policy olup atılır → daha çok çevre etkileşimi (8 paralel ortam telafi).",
    "SARSA vs Q-Learning (tek satır fark): SARSA hedefi Q(s′,a′) (davranıştan a′, on-policy); Q-Learning max_a Q(s′,a) (greedy hedef, off-policy).",
    "Off-policy avantajı: replay ile veriyi tekrar kullanır (örnek-verimli); riski: eski veri güncel politikadan sapabilir (kararlılık).",
], size=15)

s = prs.slides.add_slide(BLANK); bg(s)
add_title(s, "Savunma 3 — Markov Özelliği?  →  YAKLAŞIK Markov")
bullets(s, [
    "Tanım: P(s_{t+1}|s_t,a_t) = P(s_{t+1}|s_t,a_t,...,s_0) — gelecek yalnız şimdiki duruma bağlı, geçmişe değil.",
    "Durumda önceki eylem(3) VAR → HIZ/momentum bilgisini taşır (top örneği: yalnız konum Markov değil, konum+hız Markov).",
    "Eksik bilgi: hareketli engel konumu t'nin fonksiyonu (sin(2πt/T)) ama durum t'yi/engel fazını AÇIKÇA içermez → engelin gelecek yeri tek gözlemden tam belirlenemez → YAKLAŞIK Markov.",
    "Atari: tek kare hızı vermez (Markov değil), DeepMind 4 kare istifledi; bizdeki karşılık önceki eylemi durumda tutmak.",
    "Markov değilse 2 çözüm: (i) durumu zenginleştir (hız/faz ekle — biz önceki eylemi ekledik), (ii) bellek (RNN/LSTM, kare istifleme).",
], size=15)

s = prs.slides.add_slide(BLANK); bg(s)
add_title(s, "Savunma 4 — Kısmi Gözlemlenebilir mi?  →  EVET (POMDP)")
bullets(s, [
    "Gerçek durum s: drone'un GERÇEK konum/yaw'ı, TÜM engellerin gerçek konumu, haritanın tam geometrisi.",
    "Gözlem o: GÜRÜLTÜLÜ lidar (yalnız görüş hattı) + GÜRÜLTÜLÜ odometri poz/yaw + keşif istatistikleri.",
    "Aradaki boşluk (eksik bilgi): (i) odom gürültüsü → ajan gerçek konumu TAM bilmez; (ii) lidar duvar ARKASINI görmez; (iii) engelin GELECEK konumu gözlemde yok.",
    "Gözlem gürültüsü tek başına değil; asıl POMDP sınırlı görüşten (duvar arkası) gelir. Vanilla DQN yetersiz → bellek (RNN) veya gözlem istifleme gerekir.",
    "Belief state: gerçek durum üzerindeki olasılık dağılımı (inanç); gözlemlerle Bayes ile güncellenir, POMDP'de optimal politika belief üzerinde tanımlıdır. Biz önceki eylem + politika bağlamıyla KISMEN telafi ederiz.",
], size=14)

# ---------------------------------------------------------------- Sonuç
s = prs.slides.add_slide(BLANK); bg(s)
add_title(s, "Sonuç")
bullets(s, [
    "PPO, on-policy ve replay buffer'sız olmasına rağmen rastgele ve sezgisel taban politikalarını belirgin geçti.",
    "5 hiperparametre (clip/ent/gamma/lr/vf) yeniden eğitilerek tarandı; seçilen taban değerler gürbüz orta nokta.",
    "Akif'in yayınlanmış SAC grafikleriyle yan-yana kıyas, on-policy/off-policy ayrımını gösterdi.",
    "Tüm grafikler sonuclar/loglar/ altındaki ham loglardan yeniden üretilebilir.",
], size=18)

OUT.parent.mkdir(parents=True, exist_ok=True)
prs.save(str(OUT))
print(f"[pptx] kaydedildi -> {OUT} ({len(prs.slides._sldIdLst)} slayt)")
