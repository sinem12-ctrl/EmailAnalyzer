from flask import Flask, render_template, request, redirect, flash
from pathlib import Path
from datetime import datetime
import json
import pandas as pd

# Kendi veri işleme modüllerin
from veri_isleyiciler.ham_veri import epostalari_getir
from veri_isleyiciler.temizlenmis_icerige_gore import zincirli_eposta_olustur
from veri_isleyiciler.spamli_temizleme import spamli_eposta_isle

import matplotlib.pyplot as plt
import numpy as np


# Aynı isimde dosya varsa numaralandırarak yeni isim oluşturur
def benzersiz_dosya_adi(dosya_yolu: Path) -> Path:
    if not dosya_yolu.exists():
        return dosya_yolu
    stem, suffix, parent = dosya_yolu.stem, dosya_yolu.suffix, dosya_yolu.parent
    i = 2
    while True:
        yeni_adi = f"{stem}_{i}{suffix}"
        yeni_dosya = parent / yeni_adi
        if not yeni_dosya.exists():
            return yeni_dosya
        i += 1


# Dosya adı oluşturur: veri türü, bugünün tarihi ve tarih filtresine göre
def dosya_adi_olustur(veri_turu, bugun_dt, tarih_tipi, tarih_baslangic, tarih_bitis):
    def tarih_str(dt):
        return dt.strftime("%d%m%Y") if dt else ""
    bugun_str = tarih_str(bugun_dt)
    bas_str = tarih_str(tarih_baslangic)
    bit_str = tarih_str(tarih_bitis)

    # Spam için özel prefix
    if veri_turu == "spam":
        prefix = "spam_mail"
    else:
        prefix = f"{veri_turu}_veri"

    if tarih_tipi == "aralik":
        return f"{prefix}_{bugun_str}_{bas_str}_{bit_str}_arasi"
    elif tarih_tipi == "tek":
        return f"{prefix}_{bugun_str}_{bas_str}_{bugun_str}_arasi"
    else:
        return f"{prefix}_{bugun_str}"


# Grafik oluşturur ve PNG olarak kaydeder
def grafik_olustur_ve_kaydet(veriler, veri_turu, tarih_str, ham_veri=None):
    kayitlar = []
    for i, v in enumerate(veriler):
        tarih_str_val = v.get("tarih")
        if not tarih_str_val and ham_veri and i < len(ham_veri):
            tarih_str_val = ham_veri[i].get("tarih")
        tarih = pd.to_datetime(tarih_str_val).date() if tarih_str_val else None
        cevap_var_mi = v.get("full_answer") and v.get("full_answer").strip() != ""
        if tarih:
            kayitlar.append({"Tarih": tarih, "Cevaplandi": cevap_var_mi})

    if not kayitlar:
        print(f"⚠️ {veri_turu} için grafik oluşturulamadı: veri yok.")
        return False

    df = pd.DataFrame(kayitlar)
    ozet = df.groupby("Tarih").agg(
        Soru_Sayisi=('Cevaplandi', 'count'),
        Cevap_Sayisi=('Cevaplandi', 'sum')
    ).reset_index()

    ozet = ozet[ozet["Soru_Sayisi"] != 0]
    if ozet.empty:
        print(f"⚠️ {veri_turu} için grafik oluşturulamadı: boş özet.")
        return False

    x = np.arange(len(ozet))
    width = 0.35
    plt.figure(figsize=(12, 7))
    plt.bar(x - width/2, ozet["Soru_Sayisi"], width, label="Soru Sayısı", color='royalblue')
    plt.bar(x + width/2, ozet["Cevap_Sayisi"], width, label="Cevap Sayısı", color='seagreen')
    oran = ozet["Cevap_Sayisi"] / ozet["Soru_Sayisi"]
    plt.plot(x, oran * ozet["Soru_Sayisi"].max(), color='orange', marker='o', label='Cevap Oranı')
    plt.xticks(x, ozet["Tarih"].astype(str), rotation=45)
    plt.title("Günlük Soru ve Cevap Sayısı")
    plt.legend()

    for i in x:
        plt.text(i - width/2, ozet["Soru_Sayisi"].iloc[i] + 0.1, str(ozet["Soru_Sayisi"].iloc[i]), ha='center')
        plt.text(i + width/2, ozet["Cevap_Sayisi"].iloc[i] + 0.1, str(ozet["Cevap_Sayisi"].iloc[i]), ha='center')
    plt.tight_layout()

    indirilenler = Path.home() / "Downloads"
    indirilenler.mkdir(exist_ok=True)
    dosya = benzersiz_dosya_adi(indirilenler / f"grafik_{veri_turu}_{tarih_str}.png")
    try:
        plt.savefig(dosya, dpi=300)
        print(f"✅ Grafik kaydedildi: {dosya}")
    except Exception as e:
        print("❌ Grafik hatası:", e)
        plt.close()
        return False
    plt.close()
    return True


app = Flask(__name__)
app.secret_key = "gizli_key"  # Flash mesajları için


def parse_tarih(t):
    try:
        return datetime.strptime(t, "%Y-%m-%d") if t else None
    except:
        return None


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        email = request.form.get("email")
        sifre = request.form.get("sifre")
        veri_turleri = request.form.getlist("veri_turu")
        formatlar = request.form.getlist("format")
        tarih_tipi = request.form.get("tarih_tipi")
        tarih1_raw = request.form.get("tek_tarih") if tarih_tipi == "tek" else request.form.get("aralik_baslangic")
        tarih2_raw = None if tarih_tipi == "tek" else request.form.get("tarih_bitis")
        grafik_kaydet = request.form.get("grafik_kaydet") == "evet"

        if not email or not sifre or not veri_turleri or not formatlar:
            flash("Tüm alanları eksiksiz doldurun!", "danger")
            return redirect("/")

        bugun = datetime.now()
        tarih1 = parse_tarih(tarih1_raw)
        tarih2 = parse_tarih(tarih2_raw)
        downloads = Path.home() / "Downloads"
        downloads.mkdir(exist_ok=True)

        try:
            for veri_turu in veri_turleri:
                dosya_adi = dosya_adi_olustur(veri_turu, bugun, tarih_tipi, tarih1, tarih2)

                if veri_turu == "ham":
                    ham = epostalari_getir(email, sifre, tarih1, tarih2)
                    if not ham:
                        flash("❗ Ham veri bulunamadı, dosya oluşturulmadı.", "warning")
                        continue

                    if "json" in formatlar:
                        dosya_json = benzersiz_dosya_adi(downloads / f"{dosya_adi}.json")
                        with open(dosya_json, "w", encoding="utf-8") as f:
                            json.dump(ham, f, ensure_ascii=False, indent=2)

                    if "csv" in formatlar:
                        dosya_csv = benzersiz_dosya_adi(downloads / f"{dosya_adi}.csv")
                        pd.DataFrame(ham).to_csv(dosya_csv, index=False)

                    if grafik_kaydet:
                        grafik_olustur_ve_kaydet(ham, "ham", bugun.strftime("%d%m%Y"))
                    flash("✅ Ham veriler başarıyla kaydedildi.", "success")

                elif veri_turu == "temiz":
                    ham = epostalari_getir(email, sifre, tarih1, tarih2)
                    temiz = zincirli_eposta_olustur(ham)
                    if not temiz:
                        flash("❗ Temizlenmiş veri bulunamadı, dosya oluşturulmadı.", "warning")
                        continue

                    if "json" in formatlar:
                        dosya_json = benzersiz_dosya_adi(downloads / f"{dosya_adi}.json")
                        with open(dosya_json, "w", encoding="utf-8") as f:
                            json.dump(temiz, f, ensure_ascii=False, indent=2)

                    if "csv" in formatlar:
                        dosya_csv = benzersiz_dosya_adi(downloads / f"{dosya_adi}.csv")
                        pd.DataFrame(temiz).to_csv(dosya_csv, index=False)

                    if grafik_kaydet:
                        grafik_olustur_ve_kaydet(temiz, "temiz", bugun.strftime("%d%m%Y"), ham_veri=ham)
                    flash("✅ Temizlenmiş veriler başarıyla kaydedildi.", "success")

                elif veri_turu == "spam":
                    spam = spamli_eposta_isle(email, sifre, tarih1, tarih2)
                    if not spam:
                        flash("❗ Spam veri bulunamadı, dosya oluşturulmadı.", "warning")
                        continue

                    if "json" in formatlar:
                        dosya_json = benzersiz_dosya_adi(downloads / f"{dosya_adi}.json")
                        with open(dosya_json, "w", encoding="utf-8") as f:
                            json.dump(spam, f, ensure_ascii=False, indent=2)

                    if "csv" in formatlar:
                        dosya_csv = benzersiz_dosya_adi(downloads / f"{dosya_adi}.csv")
                        pd.DataFrame(spam).to_csv(dosya_csv, index=False)

                    if grafik_kaydet:
                        grafik_olustur_ve_kaydet(spam, "spam", bugun.strftime("%d%m%Y"))
                    flash("✅ Spam veriler başarıyla kaydedildi.", "success")

        except Exception as e:
            flash(f"❌ Hata oluştu: {e}", "danger")

        return redirect("/")
    
    return render_template("index.html")

if __name__ == "__main__":
    app.run(debug=True)
