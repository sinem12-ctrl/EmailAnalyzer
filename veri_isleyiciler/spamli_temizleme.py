import imaplib
import email
from email.header import decode_header
from email.utils import parsedate_to_datetime
import json
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline

# -- Spam modeli eğitimi --
df = pd.read_csv("https://raw.githubusercontent.com/Apaulgithub/oibsip_taskno4/main/spam.csv", encoding="ISO-8859-1")
df = df.rename(columns={"v1": "Category", "v2": "Message"})  # Kolon isimlerini anlamlı yap
df = df[["Category", "Message"]]  # İlgili kolonları seç
df["Spam"] = df["Category"].apply(lambda x: 1 if x == "spam" else 0)  # Spam için 1, değilse 0 etiketi oluştur

# Spam tespiti için Naive Bayes pipeline modeli kur
spam_model = Pipeline([
    ("vectorizer", CountVectorizer()),
    ("nb", MultinomialNB())
])
spam_model.fit(df["Message"], df["Spam"])  # Modeli eğit

def temizle(metin):
    # Gelen metni temizle: None veya bytes ise uygun şekilde stringe dönüştür, satır sonlarını temizle
    if not metin:
        return ""
    if isinstance(metin, bytes):
        metin = metin.decode(errors="ignore")
    return metin.replace("\r", "").replace("\n", " ").strip()

# Sistem tarafından gönderilen e-postalarda geçen önemli konu anahtarları
SISTEM_KONU_ANAHTARLARI = [
    "Güvenlik uyarısı",
    "İki Adımlı Doğrulama",
]

def konu_sistem_mi(konu):
    # Konunun sistem e-postası içerip içermediğini kontrol et
    if not konu:
        return False
    konu_lower = konu.lower()
    for anahtar in SISTEM_KONU_ANAHTARLARI:
        if anahtar.lower() in konu_lower:
            return True
    return False

def detect_spam(text):
    # Metin spam mı değil mi tespit et (1: spam, 0: değil)
    return spam_model.predict([text])[0]

def naive_datetime(dt):
    # Tarihi timezone bilgisi olmadan naive datetime formatına çevir
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt

def spamli_eposta_isle(kullanici, sifre, baslangic=None, bitis=None):
    # Gmail IMAP sunucusuna bağlan, kullanıcının maillerini çek, spam ve sistem maillerini filtrele
    imap = imaplib.IMAP4_SSL("imap.gmail.com")
    imap.login(kullanici, sifre)

    spamlar = []
    sistem_konular = ["İki Adımlı Doğrulama", "Güvenlik uyarısı"]

    imap.select("INBOX")
    status, mesajlar = imap.search(None, "ALL")  # Tüm mailleri ara
    for eid in mesajlar[0].split():
        try:
            _, data = imap.fetch(eid, "(RFC822)")  # E-postayı al
            mail = email.message_from_bytes(data[0][1])

            # Tarih bilgisini al ve datetime formatına çevir
            tarih_raw = mail.get("Date")
            try:
                tarih = parsedate_to_datetime(tarih_raw)
            except:
                tarih = None

            tarih = naive_datetime(tarih)

            # Başlangıç ve bitiş tarihine göre filtre uygula
            if baslangic and tarih and tarih < baslangic:
                continue
            if bitis and tarih and tarih > bitis:
                continue

            # Konu satırını al ve decode et
            konu_raw = mail.get("Subject")
            konu = ""
            if konu_raw:
                decoded = decode_header(konu_raw)
                subject, enc = decoded[0]
                konu = subject.decode(enc or "utf-8", errors="ignore") if isinstance(subject, bytes) else subject

            kimden = mail.get("From", "").lower()

            # E-postanın içerik kısmını al (text/plain veya text/html)
            icerik = ""
            for part in mail.walk() if mail.is_multipart() else [mail]:
                if part.get_content_type() in ["text/plain", "text/html"] and part.get_payload(decode=True):
                    icerik = part.get_payload(decode=True)
                    break

            temiz_icerik = temizle(icerik)
            if not temiz_icerik:
                continue

            # İçeriği spam olarak tespit et, sistem konularında mı veya google kaynaklı mı kontrol et
            is_spam = detect_spam(temiz_icerik) == 1
            is_sistem = any(k in konu for k in sistem_konular)
            is_google = "google" in kimden

            if is_spam or is_sistem or is_google:
                spamlar.append({
                    "tarih": tarih.isoformat() if tarih else None,
                    "konu": konu,
                    "icerik": temiz_icerik
                })

        except Exception as e:
            print(f"⚠️ Hata: {str(e)}")  # Hata durumunda uyarı bas ve devam et
            continue

    imap.logout()

    print(f"📨 Toplam spam veya sistem mesajı: {len(spamlar)}")

    return spamlar
