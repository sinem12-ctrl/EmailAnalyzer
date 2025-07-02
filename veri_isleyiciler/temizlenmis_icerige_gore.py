import re
from datetime import datetime

# 📅 Bugünün tarihini "ggaaYYYY" formatında string olarak döner
def bugun_tarih_str():
    return datetime.now().strftime("%d%m%Y")


# 🧹 Metinden [image:...], HTML etiketlerini ve fazla boşlukları temizler
def temizle_metin(text):
    if not isinstance(text, str):
        return ""
    text = re.sub(r"\[image:.*?\]", "", text)
    text = re.sub(r"<.*?>", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# 🔚 "On ... wrote:" kalıbından sonrasını siler (gelen e-postadaki alıntıyı temizlemek için)
def temizle_alinti_satiri(text):
    if not text:
        return text
    pattern = r"on\s+\w{3},?\s+\w+\s+\d{1,2},?\s+\d{4}\s+at\s+\d{1,2}:\d{2}.*?wrote:.*"
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return text[:match.start()].strip()
    return text


# ⚙️ Sistem maillerini tespit etmek için konu başlığı anahtar kelimeleri
SISTEM_KONU_ANAHTARLARI = [
    "Güvenlik uyarısı",
    "İki Adımlı Doğrulama",
    # Yeni anahtarlar buraya eklenebilir
]

# 🎯 Konunun sistem mesajı olup olmadığını belirler
def konu_sistem_mi(konu):
    if not konu:
        return False
    konu_lower = konu.lower()
    for anahtar in SISTEM_KONU_ANAHTARLARI:
        if anahtar.lower() in konu_lower:
            return True
    return False


# 🔗 Metindeki linkleri çıkarır ve standart hale getirir
def extract_links(text):
    pattern = r"https?://[^\s<>\)\"']+"
    raw_links = re.findall(pattern, text or "")
    temiz_links = [link.rstrip('.,;:!?)]\'"') for link in raw_links]
    temiz_links = [link.lower().rstrip('/') for link in temiz_links]
    return list(set(temiz_links))


# 🔄 Zincirli e-posta listesi oluşturur (temizlenmiş soru-cevap eşleştirmeleri)
def zincirli_eposta_olustur(mailler):
    zincirler = []
    kullanilanlar = set()

    for i, m1 in enumerate(mailler):
        if i in kullanilanlar:
            continue

        kimden = m1.get("kimden", "").lower()
        if "google" in kimden:
            continue  # Google sistem mailleri atlanır

        konu = m1.get("konu", "")
        if konu_sistem_mi(konu):
            continue  # Sistem mailleri atlanır

        # İlk mailin cevap ve soru metni temizlenir
        cevap1_raw = m1.get("full_answer", "")
        cevap1 = temizle_metin(cevap1_raw)
        cevap1 = temizle_alinti_satiri(cevap1)

        soru1_raw = m1.get("base_questions", "")
        soru1 = temizle_metin(soru1_raw)
        if not soru1:
            continue  # Boş sorular atlanır

        # İlk zincir yapısı oluşturulur
        zincir = {
            "base_questions": soru1,
            "full_answer": cevap1 or None
        }

        # İlk sorudan ve cevaptan linkler çıkarılır
        tum_linkler = extract_links(soru1_raw) + extract_links(cevap1_raw)

        # Zincire ek olabilecek devam mailleri aranır
        for j, m2 in enumerate(mailler[i+1:], start=i+1):
            if j in kullanilanlar:
                continue

            soru2_raw = m2.get("base_questions", "")
            soru2 = temizle_metin(soru2_raw)

            cevap2_raw = m2.get("full_answer", "")
            cevap2 = temizle_metin(cevap2_raw)
            cevap2 = temizle_alinti_satiri(cevap2)

            # İkinci soru, ilk cevabı içeriyorsa zincirin devamı sayılır
            if cevap1 and cevap1[:50] in soru2:
                zincir["soru_2"] = soru2

                # "soru cevap" ifadesinden sonrası silinir
                if "soru cevap" in soru2.lower():
                    index = soru2.lower().find("soru cevap")
                    zincir["soru_2"] = soru2[:index].strip()

                zincir["cevap_2"] = cevap2
                if "soru cevap" in cevap2.lower():
                    index = cevap2.lower().find("soru cevap")
                    zincir["cevap_2"] = cevap2[:index].strip()

                # Linkler zincire eklenir
                tum_linkler += extract_links(soru2_raw) + extract_links(cevap2_raw)

                kullanilanlar.add(j)
                break

        # Linkler eklendiyse zincire yaz
        if tum_linkler:
            zincir["linkler"] = ", ".join(sorted(set(tum_linkler)))

        zincirler.append(zincir)
        kullanilanlar.add(i)

    return zincirler
