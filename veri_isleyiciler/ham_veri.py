import imaplib
import email
from email.header import decode_header
from email.utils import parseaddr, parsedate_to_datetime
import ssl
from datetime import datetime, timezone

def temizle_metin(metin):
    # Metindeki \r ve \n karakterlerini temizle, boşlukları düzenle
    if not metin:
        return ""
    if isinstance(metin, bytes):
        metin = metin.decode(errors="ignore")
    return metin.replace("\r", "").replace("\n", " ").strip()

def decode_konu(konu_raw):
    # E-posta konusunu decode eder (başlık kodlaması varsa çözümle)
    if not konu_raw:
        return ""
    decoded = decode_header(konu_raw)
    konu, encoding = decoded[0]
    if isinstance(konu, bytes):
        return konu.decode(encoding or "utf-8", errors="ignore")
    return konu

def mail_icerigi_al(mail):
    # Mailin text/plain veya text/html içeriğini alır ve temizler
    for part in mail.walk() if mail.is_multipart() else [mail]:
        if part.get_content_type() in ["text/plain", "text/html"]:
            payload = part.get_payload(decode=True)
            if payload:
                return temizle_metin(payload)
    return ""

def tarih_str_to_datetime(tarih_str):
    # "YYYY-MM-DD" formatındaki stringi datetime objesine çevirir
    if tarih_str:
        try:
            return datetime.strptime(tarih_str, "%Y-%m-%d")
        except Exception as e:
            print("Tarih parse edilemedi:", e)
            return None
    return None

def to_naive_utc(dt):
    # Zaman dilimi bilgisi varsa UTC'ye çevirip naive datetime yapar
    if dt is None:
        return None
    if dt.tzinfo:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt

def epostalari_getir(kullanici, sifre, baslangic=None, bitis=None):
    # Gmail IMAP'e SSL ile bağlanır ve giriş yapar
    context = ssl.create_default_context()
    imap = imaplib.IMAP4_SSL("imap.gmail.com", port=993, ssl_context=context)
    imap.login(kullanici, sifre)

    msgid_to_mail = {}

    # INBOX klasöründeki tüm mail ID'lerini alır
    gelen_ids = mail_listesi_al(imap, "INBOX")
    print(f"📥 INBOX'tan gelen {len(gelen_ids)} e-posta bulundu.")

    for eposta_id in gelen_ids:
        try:
            # E-posta içeriğini ham olarak alır
            _, data = imap.fetch(eposta_id, "(RFC822)")
            mail = email.message_from_bytes(data[0][1])

            # Mailin tarih bilgisini parse eder
            tarih_raw = mail.get("Date")
            try:
                tarih = parsedate_to_datetime(tarih_raw)
            except:
                tarih = None

            # Tarihi naive UTC datetime objesine çevirir
            tarih = to_naive_utc(tarih)

            print("📨 E-posta ID:", eposta_id)
            print("🕒 Tarih raw:", tarih_raw)
            print("🕒 Tarih parsed (naive UTC):", tarih)

            # Tarih filtrelerine göre mailleri atlar
            if baslangic and tarih and tarih < baslangic:
                print("⛔ Atlandı (tarih erken):", tarih)
                continue
            if bitis and tarih and tarih > bitis:
                print("⛔ Atlandı (tarih geç):", tarih)
                continue

            # Mesaj ID al, yoksa atla
            msg_id = mail.get("Message-ID")
            if not msg_id:
                continue

            # Mesaj verilerini dict'e kaydet
            msgid_to_mail[msg_id] = {
                "msg_id": msg_id,
                "in_reply_to": mail.get("In-Reply-To"),
                "references": mail.get("References"),
                "kimden": parseaddr(mail.get("From"))[1],
                "konu": decode_konu(mail.get("Subject")),
                "tarih": tarih.isoformat() if tarih else None,
                "base_questions": mail_icerigi_al(mail),
                "full_answer": None
            }
        except Exception as e:
            print("⚠️ E-posta işlenemedi:", str(e))
            continue

    print(f"📤 Gönderilmiş klasörü taranıyor...")

    # Gönderilen mail klasöründeki tüm mail ID'lerini alır
    gonderilen_ids = mail_listesi_al(imap, '"[Gmail]/Sent Mail"')
    print(f"📨 Gönderilen kutusunda {len(gonderilen_ids)} mail var.")

    for eposta_id in gonderilen_ids:
        try:
            # Gönderilen mailleri alır
            _, data = imap.fetch(eposta_id, "(RFC822)")
            mail = email.message_from_bytes(data[0][1])

            # Tarihi parse eder ve naive UTC'ye çevirir
            tarih_raw = mail.get("Date")
            try:
                tarih = parsedate_to_datetime(tarih_raw)
            except:
                tarih = None

            tarih = to_naive_utc(tarih)

            # Tarih aralığına göre filtrele
            if baslangic and tarih and tarih < baslangic:
                continue
            if bitis and tarih and tarih > bitis:
                continue

            # Eğer bu mail, inbox'daki bir mesaja yanıt ise, cevabı kaydet
            in_reply_to = mail.get("In-Reply-To")
            if in_reply_to and in_reply_to in msgid_to_mail:
                msgid_to_mail[in_reply_to]["full_answer"] = mail_icerigi_al(mail)
        except Exception as e:
            print("⚠️ Gönderilen mail işlenemedi:", str(e))
            continue

    # Bağlantıyı kapat
    imap.logout()
    print(f"✅ Toplam alınan e-posta:", len(msgid_to_mail))

    # Sonuçları liste olarak döner
    return list(msgid_to_mail.values())

def mail_listesi_al(imap, klasor_adi):
    # Belirtilen klasörü seçer ve içindeki tüm mesaj ID'lerini listeler
    status, _ = imap.select(klasor_adi)
    if status != "OK":
        return []
    status, mesajlar = imap.search(None, "ALL")
    if status != "OK":
        return []
    return mesajlar[0].split()
