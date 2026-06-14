"""Sunum (220202046_sunum.pptx) ureticisi -- zenginlestirilmis (~22 slayt).

Ekip sunumlarindaki tum grafiklerin PPO karsiligi + PPO-ozel ic dinamikler +
per-seed paneller + PPO-vs-SAC kiyas grafikleri. Her grafik slaytinda 4-cumlelik
yorum (Gozlem -> Karsilastirma -> Aciklama -> Sonuc). Kiyas tablosu GERCEK eval
CSV'lerinden okunur (sentetik degil).

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

# --- Grafik basliklari + 4-cumlelik yorumlar ---
GRAPHS = [
    ("1_ogrenme_egrisi.png", "Grafik 1 - Ogrenme Egrisi (PPO egitim)",
     "Gozlem: Getiri ~290'dan ~0.5M'de ~470'e cikip 0.6M sonrasi ~480'de plato; std bandi daralir.\n"
     "Karsilastirma: 5 tohum ayni seyirde; sonda fark cok kucuk (tohuma kararli).\n"
     "Aciklama: Clipped surrogate sinirli adimlarla guncelledigi icin getiri sicramasiz artar; plato 6 odayi gezme tavanidir.\n"
     "Sonuc: 1.5M adim yakinsamaya fazlasiyla yeter (bkz. uzun-ufuk grafigi)."),
    ("1b_ogrenme_egrisi_episode.png", "Grafik 1b - Ogrenme Egrisi (x = Episode sayisi)",
     "Gozlem: Episode ekseninde de getiri ilk birkac bin bolumde yukselip platoya oturur.\n"
     "Karsilastirma: Adim-ekseni egrisiyle ayni hikaye; sadece x birimi farkli (hoca: episode-bazli egri).\n"
     "Aciklama: Bolum uzunlugu ogrendikce uzar (carpisma azalir), bu yuzden episode ve adim eksenleri hafif farkli olceklenir.\n"
     "Sonuc: Yakinsama hem adim hem episode bazinda dogrulanir."),
    ("2_eval_egrisi.png", "Grafik 2 - Test (Eval) Egrisi",
     "Gozlem: Deterministik eval ~200'den ~0.4M'de ~470'e cikip egitim platosuna oturur.\n"
     "Karsilastirma: Greedy eval ile stokastik egitim ayni seviyede; fark ihmal edilebilir.\n"
     "Aciklama: Yuksek getiri rastgele kesiften degil ogrenilen politikadan gelir; greedy'de de basari korunur.\n"
     "Sonuc: Politika genellesmistir; ayri deterministik koSu ile dogrulandi (rehber B2)."),
    ("3_loss_egrisi.png", "Grafik 3 - Loss Egrisi (policy gradient & value)",
     "Gozlem: Critic (value) loss ~0.3M'de ~140 tepe yapip ~30'a duser; actor loss kucuk ve yatay.\n"
     "Karsilastirma: Critic tepesi getirinin en hizli yukseldigi doneme denk gelir.\n"
     "Aciklama: Buyuk odullar kesfedilince deger hedefleri buyur (critic zorlanir); politika oturunca duser. Actor kucuk cunku klips guncellemeyi sinirlar.\n"
     "Sonuc: Critic loss dususu saglikli yakinsama, actor loss yataylik kararliligi gosterir."),
    ("4_hiperparametre_duyarlilik.png", "Grafik 4 - Hiperparametre Duyarliligi (5 parametre)",
     "Gozlem: clip_range, ent_coef, gamma, learning_rate, vf_coef 5 tohumla tarandi; egriler hata bandi icinde yatay.\n"
     "Karsilastirma: Orta clip (0.2), 0.98-0.99 gamma ve dusuk-orta lr en dengeli; uclar varyansi artirir.\n"
     "Aciklama: Yuksek ent_coef/gamma kesfi (exploration), dusuk lr/orta clip somuruyu (exploitation) ve kararliligi guclendirir.\n"
     "Sonuc: Secilen taban degerler guvenli orta nokta; sonuc bu aralikta gurbuz."),
    ("5_baseline_karsilastirma.png", "Grafik 5 - Baseline Karsilastirma (getiri)",
     "Gozlem: Eval getirisi PPO ~459, heuristic ~402, random ~49.\n"
     "Karsilastirma: Getiride az fark olsa da kapsama ve carpisma farki cok buyuk; random her olcutte geride.\n"
     "Aciklama: Heuristic kapilari planlayamaz ve sik carpar; PPO lidar+deger ile daha cok oda gezip neredeyse hic carpmaz.\n"
     "Sonuc: Ogrenme gercek kazanim; problem basit kural/rastgelelikle cozulemez (rehber B5)."),
    ("5b_baseline_4metrik.png", "Grafik 5b - Baseline 4 Metrik (gorev metrikleri)",
     "Gozlem: Getiri, oda, kapsama ve basari metriklerinin dordunde de PPO onde.\n"
     "Karsilastirma: Ozellikle tam-kesif basarisinda PPO acik ara onde; random %0 basari.\n"
     "Aciklama: Gorev metrikleri (oda/kapsama) sadece getiriye degil sistematik kesfe bakar; PPO bunu ogrenir.\n"
     "Sonuc: PPO yalnizca puan degil, gercek gorev hedefini de baskalarindan iyi yapar."),
    ("6_ppo_ic_dinamikler.png", "Grafik 6 - PPO Ic Dinamikleri (clip / KL / entropi)",
     "Gozlem: clip_fraction ~0.04'ten ~0.16'ya cikar, approx_kl buyur, entropi azalir.\n"
     "Karsilastirma: DQN'deki epsilon cizelgesinin PPO karsiligi; kesiften somuruye gecis OGRENILEREK olur.\n"
     "Aciklama: Basta yuksek entropi genis kesif saglar; politika iyilestikce avantajli eylemlere olasilik yigilir, entropi duser.\n"
     "Sonuc: Egrilerin patlamadan seyretmesi klips'in guncellemeleri guvenli tuttugunu gosterir."),
    ("7_oda_kesif_sureci.png", "Grafik 7 - Oda Kesif Sureci",
     "Gozlem: Episode basina kesfedilen oda 1'den yukselip hedef 6'ya yaklasir.\n"
     "Karsilastirma: Basta sadece dogulan oda; sonda ortalama 5-6 banda cikar.\n"
     "Aciklama: Carpismadan kacinmayi ogrenen ajan hayatta kalir ve kapilari bulup derin odalara erisir (+20/+60 odul).\n"
     "Sonuc: Model havada kalmayi degil, asil amac olan alan taramayi da yapar."),
    ("8_carpisma_orani.png", "Grafik 8 - Carpisma Orani",
     "Gozlem: Carpisma orani basta ~%100'e yakinken zamanla ciddi ve kararli duser.\n"
     "Karsilastirma: Per-seed egriler ayni yonde; sonda dusuk bantta sabitlenir.\n"
     "Aciklama: Lidar mesafesi ile -40 carpisma cezasi iliskisi ag tarafindan kurulur; kacis davranisi degere yansir.\n"
     "Sonuc: Ajan engel algilama ve carpismadan sakinmayi kalici olarak edinir."),
    ("9_seed_karsilastirma.png", "Grafik 9 - Seed Karsilastirmasi",
     "Gozlem: 5 tohumun her biri kendine ozgu yorunge izler; bazilari hizli, bazilari yavas yukselir.\n"
     "Karsilastirma: Baslangic hizlari farkli olsa da hepsi yakin ve yuksek platoya ulasir.\n"
     "Aciklama: Fark, baslangic pozisyonu rastgeleligi ve agirlik ilklendirmesinden gelir; >=5 tohum bu varyans icin gerekli.\n"
     "Sonuc: Yakinsamanin korunmasi algoritmanin gurbuzlugunu (robustness) kanitlar."),
    ("10_gamma_lr_heatmap.png", "Grafik 10 - gamma x lr Isi Haritasi",
     "Gozlem: 3x3 izgarada getiri/oda/skor isi haritasi; en iyi bolge orta-yuksek gamma + dusuk-orta lr kosesi.\n"
     "Karsilastirma: Yuksek lr + dusuk gamma kosesi en zayif.\n"
     "Aciklama: Yuksek gamma gecikmeli oda odulunu tasir; dusuk lr guncellemeyi kararli tutar; ikisi birlikte en iyi.\n"
     "Sonuc: Secilen (gamma=0.98, lr=3e-4) bu en iyi bolgenin icinde; izgara secimi dogrular."),
    ("13_explained_variance.png", "Grafik 13 - Deger Fonksiyonu Kalitesi (explained_variance)",
     "Gozlem: Aciklanan varyans egitim boyunca yukselip 1'e (ideal) yaklasir.\n"
     "Karsilastirma: 5 tohumda da kritik getirinin varyansini buyuk olcude aciklar hale gelir.\n"
     "Aciklama: Kritik durum degerlerini giderek isabetli tahmin eder; GAE avantajlari guvenilirlesir.\n"
     "Sonuc: Yuksek aciklanan varyans, politika gradyaninin dusuk-varyansli ve saglikli oldugunun kanitidir."),
]

PER_SEED = [(f"per_seed_{s}.png", f"Tohum {s} - Detayli Panel (getiri / eval / kapsama / oda)")
            for s in (123, 42, 7, 13, 2025)]

COMPARE = [
    ("C1_ogrenme_ppo_vs_sac.png", "PPO vs SAC - Ogrenme Egrisi",
     "Gozlem: SAC ilk birkac yuz bin adimda PPO'dan hizli yukselir; PPO daha cok adimla daha yuksek/kararli platoya ulasir.\n"
     "Karsilastirma: Tam ufukta PPO platosu daha yuksek.\n"
     "Aciklama: SAC off-policy (replay buffer => adim basina verimli); PPO on-policy (rollout bir kez kullanilir).\n"
     "Sonuc: Off-policy az adimda hizli, on-policy cok adimla yuksek nihai basari."),
    ("C2_ornek_verimliligi.png", "PPO vs SAC - Ornek Verimliligi",
     "Gozlem: Ayni env-adim penceresinde SAC ustte baslar.\n"
     "Karsilastirma: SAC erken avantajli; PPO sonradan yakalar/gecer.\n"
     "Aciklama: Replay buffer her deneyimi defalarca kullandigindan SAC ayni adimda daha cok ogrenir.\n"
     "Sonuc: Ornek-butcesi kisitli senaryolar icin SAC, butce bolca ise PPO avantajli."),
    ("C3_eval_ppo_vs_sac.png", "PPO vs SAC - Deterministik Eval",
     "Gozlem: Greedy eval egrisinde PPO platosu SAC'in uzerinde.\n"
     "Karsilastirma: Ikisi de stokastik egitimle tutarli; fark nihai seviyede.\n"
     "Aciklama: PPO'nun klips'i kararli/yuksek-tavanli politika ogrenir.\n"
     "Sonuc: Bu ortamda PPO nihai gorev basarisinda onde."),
    ("C5_oda_ppo_vs_sac.png", "PPO vs SAC - Oda Kesif Sureci",
     "Gozlem: PPO ortalama oda sayisinda 6'ya daha cok yaklasir.\n"
     "Karsilastirma: SAC hizli baslar ama nihai oda kapsamasi PPO'nun gerisinde.\n"
     "Aciklama: PPO'nun yuksek-tavanli politikasi sistematik oda-oda kesfi daha iyi yapar.\n"
     "Sonuc: Gorev metriginde (oda) PPO ustun."),
    ("C4_final_metrik_bar.png", "PPO vs SAC - Final Metrik Barlari",
     "Gozlem: Getiri, oda, kapsama, basari PPO'da yuksek; carpisma PPO'da dusuk.\n"
     "Karsilastirma: Dort kalite olcutunde PPO onde, guvenlikte (carpisma) de daha iyi.\n"
     "Aciklama: Ayni ortam/seed/protokolde fark yalnizca algoritmadan gelir.\n"
     "Sonuc: Bu cok-odali kesif gorevinde PPO nihai basari/guvenlikte ustun."),
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
        r = p.add_run(); r.text = ("- " + txt) if (lvl and txt) else txt
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
r.text = "Kapali Ortamda PPO ile Lidar Tabanli Drone Kesfi"
r.font.size = Pt(40); r.font.bold = True; r.font.color.rgb = WHITE
p2 = tf.add_paragraph(); r2 = p2.add_run()
r2.text = "Pekistirmeli Ogrenme Donem Projesi - Teknik Sunum"
r2.font.size = Pt(22); r2.font.color.rgb = RGBColor(0xb0, 0xbe, 0xe8)
for line in ["", "Berker Yigit - 220202046",
             "Kocaeli Universitesi, Bilgisayar Muhendisligi (II. Ogretim)",
             "Algoritma: PPO   |   Branch: algo/ppo"]:
    pp = tf.add_paragraph(); rr = pp.add_run(); rr.text = line
    rr.font.size = Pt(18); rr.font.color.rgb = WHITE

# ---------------------------------------------------------------- 2) Icerik
s = prs.slides.add_slide(BLANK); bg(s)
add_title(s, "Icerik")
bullets(s, [
    "Problem ve Neden Pekistirmeli Ogrenme?",
    "Ortam ve MDP (durum / eylem / odul) - SAC ile birebir ayni",
    "PPO Algoritmasi ve Hiperparametreler",
    "Deney Duzeni (5 seed, deterministik eval, baseline)",
    "5 Zorunlu Grafik + Ek Analizler (oda kesfi, carpisma, ic dinamikler, heatmap)",
    "Hiperparametre Taramasi (clip/ent/gamma/lr/vf - yeniden egitim)",
    "Per-seed Detay Panelleri",
    "PPO vs SAC Karsilastirmasi (ayni ortam/seed/protokol)",
    "Savunma Ozeti ve Sonuc",
], size=19)

# ---------------------------------------------------------------- 3) Problem
s = prs.slides.add_slide(BLANK); bg(s)
add_title(s, "Problem ve Neden Pekistirmeli Ogrenme?")
bullets(s, [
    "Gorev: GPS'siz kapali binada, sadece lidar + gurultulu odometri ile carpmadan en cok alani kesfet.",
    "Neden RL? (rehber dort olcutu de saglanir)",
    (1, "Ardisiklik: bir adimdaki donus, sonraki adimlarin kesif potansiyelini belirler."),
    (1, "Gecikmeli odul: yeni oda / 6-oda bonusu ancak ileride toplanir."),
    (1, "Buyuk, bilinmeyen, stokastik durum uzayi (75-D surekli; lidar/odom/ruzgar gurultusu)."),
    (1, "A*/BFS uygulanamaz: harita onceden bilinmez, hareketli engeller var, tek hedef yok (amac kapsama)."),
], size=18)

# ---------------------------------------------------------------- 4) Ortam/MDP
s = prs.slides.add_slide(BLANK); bg(s)
add_title(s, "Ortam ve MDP: Durum / Eylem / Odul")
bullets(s, [
    "Ortam: 8 m yaricapli, 6 odali bina; 64 isinli lidar; 3 hareketli engel.",
    "*** SAC teslimiyle BAYT-BAYT ayni ortam (MD5 61ec1d6a); state Box(75), action Box(-1,1)^3 birebir ayni. ***",
    "Durum (75-D, [0,1]): 64 lidar + yaw cos/sin + onceki eylem(3) + ilerleme/oda(2) + min_lidar/idle(2) + kapi/duvar(2).",
    "Eylem (3-D surekli): ileri/geri hiz, yanal hiz, donus hizi.",
    "Odul (kod step() ile birebir): +3 yeni voxel, +20 yeni oda, -40 carpisma, +60 tum odalar, kucuk zaman/idle cezalari.",
    "Bolum: carpisma veya 6-oda ile biter, 600 adimda kesilir.",
], size=17)

# ---------------------------------------------------------------- 5) PPO
s = prs.slides.add_slide(BLANK); bg(s)
add_title(s, "PPO Algoritmasi")
bullets(s, [
    "Aktor-kritik, ON-POLICY politika gradyani. Aktor surekli eylemde Gauss dagilimi; kritik durum degeri.",
    "Clipped surrogate: yeni/eski politika orani 1 +/- 0.2 ile kirpilir => kararli, asiri sapmasiz guncelleme.",
    "GAE (lambda=0.95) ile avantaj tahmini.",
    "Replay buffer YOK: rollout verisi birkac epoch kullanilip atilir => off-policy'ye gore daha az ornek-verimli.",
    "Telafi: 8 paralel ortam + daha uzun egitim (1.5M adim/seed).",
    "Adil karsilastirma: learning_rate, gamma, ag mimarisi, num_envs SAC teslimiyle AYNI.",
], size=17)

# ---------------------------------------------------------------- 6) HP + Deney
s = prs.slides.add_slide(BLANK); bg(s)
add_title(s, "Hiperparametreler ve Deney Duzeni")
bullets(s, [
    "config.yaml: lr=3e-4, gamma=0.98, net=[256,256], n_steps=1024, batch=512, n_epochs=10, clip=0.2, gae=0.95, ent=0.005, vf=0.5.",
    "5 seed: 7,13,42,123,2025 (>=5 zorunlu). Her seed ayri politika; her 10k adimda deterministik eval.",
    "Final: 20 bolum DETERMINISTIK (greedy) koSu (egitim egrisi tek basina kanit degil).",
    "Baseline: rastgele + sezgisel politika, ayni ortamda.",
    "HP taramasi (yeniden egitim): clip_range, ent_coef, gamma, learning_rate, vf_coef -> her biri >=3 deger x 5 seed.",
    "Tum rastgelelik numpy.random.default_rng; import gym / np.random.seed YOK.",
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
add_title(s, "PPO vs SAC - Ozet (ayni ortam/seed/protokol)")


def _avg(name):
    p = SON / name
    if not p.exists():
        return None
    d = pd.read_csv(p)
    return dict(ret=d["ep_return"].mean(), succ=d["success"].mean(),
               cov=d["coverage_pct"].mean(), crash=d["crashed"].mean())


ppo, sac = _avg("eval_per_episode.csv"), _avg("sac_eval_per_episode.csv")
def fmt(d, k, f="{:.1f}"):
    return f.format(d[k]) if d else "--"
rows = [
    ("Olcut", "PPO (bu calisma)", "SAC (ayni ortam)"),
    ("Aile", "on-policy", "off-policy"),
    ("Replay buffer", "yok", "var"),
    ("Ort. eval getirisi", fmt(ppo, "ret"), fmt(sac, "ret")),
    ("Basari orani (6 oda)", fmt(ppo, "succ", "{:.2f}"), fmt(sac, "succ", "{:.2f}")),
    ("Ort. kapsama %", fmt(ppo, "cov"), fmt(sac, "cov")),
    ("Eval carpisma orani", fmt(ppo, "crash", "{:.2f}"), fmt(sac, "crash", "{:.2f}")),
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
    "Ortam, durum/eylem uzayi, seed ve protokol birebir ayni -> fark yalnizca algoritmadan.",
    "SAC az adimda hizli oturur (off-policy, replay buffer); PPO daha cok adimla daha yuksek nihai basari.",
], top=5.8, size=15)

# ---------------------------------------------------------------- PPO vs SAC grafikleri
for fname, title, comment in COMPARE:
    if fname == "C4_final_metrik_bar.png":
        wide_graph_slide(fname, title, comment)
    else:
        graph_slide(fname, title, comment)

# ---------------------------------------------------------------- Savunma
s = prs.slides.add_slide(BLANK); bg(s)
add_title(s, "Savunma Ozeti (4 Kavram Alani)")
bullets(s, [
    "Stokastik mi? EVET. Kanit kod satiri: ruzgar (step), lidar (_compute_lidar), odom (_make_obs) gurultusu => p(s'|s,a) dejenere degil.",
    "On/Off-policy? ON-POLICY. Davranis = hedef politika; replay buffer yok; veri kullanilip atilir.",
    "Markov? Yaklasik saglanir: lidar + hiz (onceki eylem) + adim-deterministik engeller; gurultu/sinirli gorus ile yalnizca yaklasik.",
    "POMDP mi? EVET. Gercek durum != gozlem: odom gurultusu, gorus-disi duvarlar, engelin gelecek konumu gozlemde yok.",
], size=16)

# ---------------------------------------------------------------- Sonuc
s = prs.slides.add_slide(BLANK); bg(s)
add_title(s, "Sonuc")
bullets(s, [
    "PPO, on-policy ve replay buffer'siz olmasina ragmen rastgele ve sezgisel taban politikalarini belirgin gecti.",
    "5 hiperparametre (clip/ent/gamma/lr/vf) yeniden egitilerek tarandi; secilen taban degerler gurbuz orta nokta.",
    "Ayni ortamda egitilen SAC ile kiyas, on-policy/off-policy ayrimini gercek egrilerle gosterdi.",
    "Tum grafikler sonuclar/loglar/ altindaki ham loglardan yeniden uretilebilir.",
], size=18)

OUT.parent.mkdir(parents=True, exist_ok=True)
prs.save(str(OUT))
print(f"[pptx] kaydedildi -> {OUT} ({len(prs.slides._sldIdLst)} slayt)")
