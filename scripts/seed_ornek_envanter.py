# 40 kayitlik ornek veri envanteri. Kurgusal kurum; gercek kurum verisinin yerine gecer.
# Bir kismi bilerek eksik birakilir ki denetim motoru (ENV-001..006) gosterilebilsin.
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kvkk_rag.inventory import audit, store, taxonomy  # noqa: E402

KURUM = "ÖRNEK TEKNOLOJİ A.Ş."

# Kanonik taksonomiden kisa adlar
S_RIZA = "İlgili Kişinin Açık Rızasının Varlığı"
S_KANUN = "Kanunlarda Açıkça Öngörülmesi"
S_SOZLESME = ("Bir Sözleşmenin Kurulması veya İfasıyla Doğrudan Doğruya İlgili Olması "
              "Kaydıyla Sözleşmenin Taraflarına Ait Kişisel Verilerin İşlenmesinin Gerekli Olması")
S_HUKUKI = "Veri Sorumlusunun Hukuki Yükümlülüğünü Yerine Getirebilmesi İçin Zorunlu Olması"
S_MESRU = ("İlgili Kişinin Temel Hak ve Özgürlüklerine Zarar Vermemek Kaydıyla, "
           "Veri Sorumlusunun Meşru Menfaatleri İçin Veri İşlenmesinin Zorunlu Olması")
S_HAK = "Bir Hakkın Tesisi, Kullanılması veya Korunması İçin Veri İşlemenin Zorunlu Olması"
S_ISTIHDAM = ("İstihdam, İş Sağlığı ve Güvenliği, Sosyal Güvenlik, Sosyal Hizmetler ve "
              "Sosyal Yardım Alanındaki Yükümlülüklerin Yerine Getirilmesi")

TEK = {
    "ag": "Ağ güvenliği ve uygulama güvenliği sağlanmaktadır.",
    "yetki": "Erişim logları düzenli olarak tutulmaktadır.",
    "sifre": "Şifreleme yapılmaktadır.",
    "yedek": "Kişisel veriler yedeklenmektedir.",
    "anahtar": "Anahtar yönetimi uygulanmaktadır.",
}
IDA = {
    "egitim": "Çalışanlar için veri güvenliği konusunda belli aralıklarla eğitim ve farkındalık çalışmaları yapılmaktadır.",
    "politika": "Erişim, bilgi güvenliği, kullanım, saklama ve imha konularında kurumsal politikalar hazırlanmış ve uygulamaya başlanmıştır.",
    "disiplin": "Çalışanlar için veri güvenliği hükümleri içeren disiplin düzenlemeleri mevcuttur.",
    "gizlilik": "Gizlilik taahhütnameleri yapılmaktadır.",
}

ELEKTRONIK = "Elektronik ortam (ERP, veri tabanı, e-posta sunucusu)"
FIZIKSEL = "Fiziksel ortam (birim arşivi, kilitli dolap)"
KARMA = "Elektronik ve fiziksel ortam"
PERIYODIK = "6 ay (periyodik imha)"
IMHA_SIL = "Veri tabanından güvenli silme; fiziksel evrakta kağıt kırpma"
IMHA_YOK = "Fiziksel yok etme ve güvenli silme"
IMHA_ANON = "Anonim hale getirme (maskeleme)"


def tedbir(*anahtarlar: str, idari: bool = False) -> str:
    kaynak = IDA if idari else TEK
    return "\n".join(kaynak[a] for a in anahtarlar)


# (birim, faaliyet, kategori, kisisel_veri, ozel_nitelikli, kisi_grubu, amac, sebep,
#  saklama, alici, yurt_disi, ulke, teknik, idari, imha, periyodik, ortam, isleyen)
K = [
 # --- İNSAN KAYNAKLARI (tam dolu, uyumlu) ---
 ("İNSAN KAYNAKLARI MÜDÜRLÜĞÜ", "Çalışan Özlük Dosyası Yönetimi", "Kimlik",
  "Ad soyad, T.C. kimlik numarası, doğum tarihi", "", "Çalışan",
  "Çalışanlar İçin İş Akdi Ve Mevzuattan Kaynaklı Yükümlülüklerin Yerine Getirilmesi", S_HUKUKI,
  "İş akdinin sona ermesinden itibaren 10 yıl", "Yetkili Kamu Kurum ve Kuruluşları", "Hayır", "",
  tedbir("ag", "yetki", "sifre"), tedbir("egitim", "politika", idari=True), IMHA_SIL, PERIYODIK, KARMA, ""),

 ("İNSAN KAYNAKLARI MÜDÜRLÜĞÜ", "Çalışan Özlük Dosyası Yönetimi", "İletişim",
  "Cep telefonu, e-posta adresi, ikametgâh adresi", "", "Çalışan",
  "Çalışanlar İçin İş Akdi Ve Mevzuattan Kaynaklı Yükümlülüklerin Yerine Getirilmesi", S_HUKUKI,
  "İş akdinin sona ermesinden itibaren 10 yıl", "Yetkili Kamu Kurum ve Kuruluşları", "Hayır", "",
  tedbir("ag", "yetki"), tedbir("egitim", "politika", idari=True), IMHA_SIL, PERIYODIK, KARMA, ""),

 ("İNSAN KAYNAKLARI MÜDÜRLÜĞÜ", "İşe Alım ve Aday Değerlendirme", "Mesleki Deneyim",
  "Özgeçmiş, diploma, sertifika, referans bilgisi", "", "Çalışan Adayı",
  "Çalışan Adayı / Stajyer / Öğrenci Seçme Ve Yerleştirme Süreçlerinin Yürütülmesi", S_MESRU,
  "Başvuru tarihinden itibaren 2 yıl", "Yetkili Kamu Kurum ve Kuruluşları", "Hayır", "",
  tedbir("ag", "yetki"), tedbir("politika", "gizlilik", idari=True), IMHA_SIL, PERIYODIK, ELEKTRONIK, ""),

 ("İNSAN KAYNAKLARI MÜDÜRLÜĞÜ", "İş Sağlığı ve Güvenliği Süreçleri", "Sağlık Bilgileri",
  "İşe giriş sağlık raporu, periyodik muayene sonucu", "İşe giriş ve periyodik muayene bulguları", "Çalışan",
  "İş Sağlığı / Güvenliği Faaliyetlerinin Yürütülmesi", S_ISTIHDAM,
  "İş akdinin sona ermesinden itibaren 15 yıl", "Yetkili Kamu Kurum ve Kuruluşları", "Hayır", "",
  tedbir("sifre", "yetki", "anahtar"), tedbir("egitim", "gizlilik", "disiplin", idari=True),
  IMHA_YOK, PERIYODIK, KARMA, "İşyeri hekimliği hizmeti sağlayıcısı"),

 ("İNSAN KAYNAKLARI MÜDÜRLÜĞÜ", "Bordro ve Ücret Yönetimi", "Finans",
  "Banka hesap numarası (IBAN), ücret bilgisi, icra kesintisi", "", "Çalışan",
  "Finans Ve Muhasebe İşlerinin Yürütülmesi", S_HUKUKI,
  "İş akdinin sona ermesinden itibaren 10 yıl", "Yetkili Kamu Kurum ve Kuruluşları", "Hayır", "",
  tedbir("sifre", "yetki", "yedek"), tedbir("politika", "disiplin", idari=True), IMHA_SIL, PERIYODIK, ELEKTRONIK, ""),

 ("İNSAN KAYNAKLARI MÜDÜRLÜĞÜ", "Bordro ve Ücret Yönetimi", "Özlük",
  "SGK sicil numarası, işe giriş-çıkış bildirgesi", "", "Çalışan",
  "Çalışanlar İçin Yan Haklar Ve Menfaatleri Süreçlerinin Yürütülmesi", S_HUKUKI,
  "İş akdinin sona ermesinden itibaren 10 yıl", "Yetkili Kamu Kurum ve Kuruluşları", "Hayır", "",
  tedbir("yetki", "yedek"), tedbir("politika", idari=True), IMHA_SIL, PERIYODIK, ELEKTRONIK, ""),

 # ENV-004 ornegi: ozel nitelikli veri m.5 sebebine baglanmis
 ("İNSAN KAYNAKLARI MÜDÜRLÜĞÜ", "Engelli Çalışan Kotası Takibi", "Sağlık Bilgileri",
  "Engellilik oranı raporu", "Engellilik durumu ve oranı", "Çalışan",
  "İş Sağlığı / Güvenliği Faaliyetlerinin Yürütülmesi", S_MESRU,
  "İş akdinin sona ermesinden itibaren 15 yıl", "Yetkili Kamu Kurum ve Kuruluşları", "Hayır", "",
  tedbir("sifre", "yetki"), tedbir("gizlilik", idari=True), IMHA_YOK, PERIYODIK, KARMA, ""),

 ("İNSAN KAYNAKLARI MÜDÜRLÜĞÜ", "Sendika İlişkileri Yönetimi", "Sendika Üyeliği",
  "Sendika üyelik ve aidat kesinti bilgisi", "Sendika üyeliği", "Çalışan",
  "Çalışanlar İçin İş Akdi Ve Mevzuattan Kaynaklı Yükümlülüklerin Yerine Getirilmesi", S_KANUN,
  "Üyeliğin sona ermesinden itibaren 10 yıl", "Yetkili Kamu Kurum ve Kuruluşları", "Hayır", "",
  tedbir("sifre", "yetki"), tedbir("gizlilik", "disiplin", idari=True), IMHA_YOK, PERIYODIK, KARMA, ""),

 # ENV-001/002/003 ornegi: eksik birakilmis
 ("İNSAN KAYNAKLARI MÜDÜRLÜĞÜ", "Çalışan Memnuniyet Anketi", "Diğer(Anket Yanıtı)",
  "Anket cevapları, departman bilgisi", "", "Çalışan",
  "İç Denetim/ Soruşturma / İstihbarat Faaliyetlerinin Yürütülmesi", S_RIZA,
  "", "Yetkili Kamu Kurum ve Kuruluşları", "Hayır", "", "", "", "", "", ELEKTRONIK, ""),

 ("İNSAN KAYNAKLARI MÜDÜRLÜĞÜ", "Eğitim ve Gelişim Yönetimi", "Mesleki Deneyim",
  "Katılım kaydı, eğitim sonucu, sertifika", "", "Çalışan",
  "Çalışanlar İçin İş Akdi Ve Mevzuattan Kaynaklı Yükümlülüklerin Yerine Getirilmesi", S_MESRU,
  "İş akdinin sona ermesinden itibaren 5 yıl", "Yetkili Kamu Kurum ve Kuruluşları", "Hayır", "",
  tedbir("yetki"), tedbir("egitim", idari=True), IMHA_SIL, PERIYODIK, ELEKTRONIK, ""),

 # --- BİLGİ İŞLEM ---
 ("BİLGİ İŞLEM MÜDÜRLÜĞÜ", "Kurumsal Ağ ve Log Yönetimi", "İşlem Güvenliği",
  "IP adresi, oturum kayıtları, erişim logları", "", "Çalışan",
  "Bilgi Güvenliği Süreçlerinin Yürütülmesi", S_HUKUKI,
  "2 yıl (5651 sayılı Kanun)", "Yetkili Kamu Kurum ve Kuruluşları", "Hayır", "",
  tedbir("ag", "yetki", "sifre", "yedek"), tedbir("politika", "disiplin", idari=True),
  IMHA_SIL, PERIYODIK, ELEKTRONIK, ""),

 ("BİLGİ İŞLEM MÜDÜRLÜĞÜ", "Kurumsal E-posta Yönetimi", "İletişim",
  "Kurumsal e-posta adresi, yazışma üstverisi", "", "Çalışan",
  "Bilgi Güvenliği Süreçlerinin Yürütülmesi", S_MESRU,
  "İş akdinin sona ermesinden itibaren 2 yıl", "Yetkili Kamu Kurum ve Kuruluşları", "Hayır", "",
  tedbir("ag", "sifre", "yedek"), tedbir("politika", idari=True), IMHA_SIL, PERIYODIK, ELEKTRONIK, ""),

 # Yurt disi aktarim ornegi (ENV-005)
 ("BİLGİ İŞLEM MÜDÜRLÜĞÜ", "Bulut Depolama ve Yedekleme", "Kimlik",
  "Kullanıcı hesap bilgileri, ad soyad", "", "Çalışan",
  "Bilgi Güvenliği Süreçlerinin Yürütülmesi", S_MESRU,
  "Hizmet sözleşmesi süresince", "Gerçek kişiler veya özel hukuk tüzel kişileri", "Evet",
  "İrlanda (AB)", tedbir("sifre", "anahtar", "yedek"), tedbir("politika", "gizlilik", idari=True),
  IMHA_SIL, PERIYODIK, ELEKTRONIK, "Bulut altyapı hizmet sağlayıcısı"),

 ("BİLGİ İŞLEM MÜDÜRLÜĞÜ", "Yardım Masası ve Destek Talepleri", "Diğer(Destek Talebi)",
  "Talep içeriği, çağrı kaydı, kullanıcı adı", "", "Çalışan",
  "Talep / Şikayetlerin Takibi", S_MESRU,
  "Talebin kapanmasından itibaren 3 yıl", "Yetkili Kamu Kurum ve Kuruluşları", "Hayır", "",
  tedbir("ag", "yetki"), tedbir("egitim", idari=True), IMHA_SIL, PERIYODIK, ELEKTRONIK, ""),

 ("BİLGİ İŞLEM MÜDÜRLÜĞÜ", "Kimlik ve Erişim Yönetimi", "İşlem Güvenliği",
  "Kullanıcı adı, parola özeti, yetki matrisi kaydı", "", "Çalışan",
  "Bilgi Güvenliği Süreçlerinin Yürütülmesi", S_HUKUKI,
  "Yetkinin sona ermesinden itibaren 2 yıl", "Yetkili Kamu Kurum ve Kuruluşları", "Hayır", "",
  tedbir("sifre", "anahtar", "yetki"), tedbir("politika", "disiplin", idari=True),
  IMHA_SIL, PERIYODIK, ELEKTRONIK, ""),

 # Biyometrik - ozel nitelikli, dogru sebeple
 ("BİLGİ İŞLEM MÜDÜRLÜĞÜ", "Veri Merkezi Fiziksel Erişim Kontrolü", "Diğer(Biyometrik Veri)",
  "Parmak izi şablonu", "Biyometrik veri (parmak izi)", "Çalışan",
  "Fiziksel Mekan Güvenliğinin Temini", S_RIZA,
  "Yetkinin sona ermesinden itibaren 1 yıl", "Yetkili Kamu Kurum ve Kuruluşları", "Hayır", "",
  tedbir("sifre", "anahtar", "yetki"), tedbir("gizlilik", "politika", idari=True),
  IMHA_YOK, PERIYODIK, ELEKTRONIK, ""),

 # --- MUHASEBE / FİNANS ---
 ("MALİ İŞLER MÜDÜRLÜĞÜ", "Tedarikçi Cari Hesap Yönetimi", "Finans",
  "Vergi numarası, banka hesap bilgisi, fatura kayıtları", "", "Tedarikçi Yetkilisi",
  "Finans Ve Muhasebe İşlerinin Yürütülmesi", S_SOZLESME,
  "Sözleşmenin sona ermesinden itibaren 10 yıl", "Yetkili Kamu Kurum ve Kuruluşları", "Hayır", "",
  tedbir("yetki", "yedek"), tedbir("politika", idari=True), IMHA_SIL, PERIYODIK, KARMA, ""),

 ("MALİ İŞLER MÜDÜRLÜĞÜ", "Müşteri Faturalandırma", "Finans",
  "Fatura bilgileri, ödeme geçmişi", "", "Müşteri",
  "Finans Ve Muhasebe İşlerinin Yürütülmesi", S_HUKUKI,
  "10 yıl (Vergi Usul Kanunu)", "Yetkili Kamu Kurum ve Kuruluşları", "Hayır", "",
  tedbir("yetki", "yedek", "sifre"), tedbir("politika", idari=True), IMHA_SIL, PERIYODIK, KARMA, ""),

 ("MALİ İŞLER MÜDÜRLÜĞÜ", "Masraf ve Avans Yönetimi", "Finans",
  "Harcama belgesi, avans kaydı", "", "Çalışan",
  "Finans Ve Muhasebe İşlerinin Yürütülmesi", S_HUKUKI,
  "10 yıl (Vergi Usul Kanunu)", "Yetkili Kamu Kurum ve Kuruluşları", "Hayır", "",
  tedbir("yetki"), tedbir("politika", idari=True), IMHA_SIL, PERIYODIK, KARMA, ""),

 ("MALİ İŞLER MÜDÜRLÜĞÜ", "İcra ve Haciz İşlemleri Takibi", "Hukuki İşlem",
  "İcra dosya numarası, borç bilgisi", "", "Çalışan",
  "Hukuk İşlerinin Takibi Ve Yürütülmesi", S_HUKUKI,
  "Dosyanın kapanmasından itibaren 10 yıl", "Yetkili Kamu Kurum ve Kuruluşları", "Hayır", "",
  tedbir("yetki", "sifre"), tedbir("gizlilik", idari=True), IMHA_SIL, PERIYODIK, KARMA, ""),

 # --- SATIN ALMA ---
 ("SATIN ALMA MÜDÜRLÜĞÜ", "Tedarikçi Seçme ve Değerlendirme", "Kimlik",
  "Yetkili ad soyad, imza sirküleri bilgileri", "", "Tedarikçi Yetkilisi",
  "Tedarik Zinciri Yönetimi Süreçlerinin Yürütülmesi", S_SOZLESME,
  "Sözleşmenin sona ermesinden itibaren 10 yıl", "Yetkili Kamu Kurum ve Kuruluşları", "Hayır", "",
  tedbir("yetki"), tedbir("politika", idari=True), IMHA_SIL, PERIYODIK, KARMA, ""),

 ("SATIN ALMA MÜDÜRLÜĞÜ", "İhale ve Teklif Süreçleri", "Diğer(Teklif Bilgisi)",
  "Teklif tutarı, yetkili iletişim bilgisi", "", "Tedarikçi Yetkilisi",
  "Tedarik Zinciri Yönetimi Süreçlerinin Yürütülmesi", S_SOZLESME,
  "İhalenin sonuçlanmasından itibaren 5 yıl", "Yetkili Kamu Kurum ve Kuruluşları", "Hayır", "",
  tedbir("yetki", "sifre"), tedbir("gizlilik", idari=True), IMHA_SIL, PERIYODIK, KARMA, ""),

 # ENV-003 ornegi: tedbir yok
 ("SATIN ALMA MÜDÜRLÜĞÜ", "Tedarikçi Ziyaret Kayıtları", "Fiziksel Mekan Güvenliği",
  "Ziyaretçi ad soyad, giriş-çıkış saati", "", "Ziyaretçi",
  "Fiziksel Mekan Güvenliğinin Temini", S_MESRU,
  "Kayıt tarihinden itibaren 2 yıl", "Yetkili Kamu Kurum ve Kuruluşları", "Hayır", "",
  "", "", IMHA_SIL, PERIYODIK, FIZIKSEL, ""),

 # --- HUKUK ---
 ("HUKUK MÜŞAVİRLİĞİ", "Dava ve İcra Takibi", "Hukuki İşlem",
  "Dava dosya bilgileri, taraf bilgileri", "", "Diğer(Karşı Taraf)",
  "Hukuk İşlerinin Takibi Ve Yürütülmesi", S_HAK,
  "Davanın kesinleşmesinden itibaren 10 yıl", "Yetkili Kamu Kurum ve Kuruluşları", "Hayır", "",
  tedbir("yetki", "sifre"), tedbir("gizlilik", "politika", idari=True), IMHA_YOK, PERIYODIK, KARMA,
  "Anlaşmalı avukatlık bürosu"),

 ("HUKUK MÜŞAVİRLİĞİ", "Sözleşme Yönetimi", "Kimlik",
  "Sözleşme tarafı ad soyad, T.C. kimlik numarası", "", "Tedarikçi Yetkilisi",
  "Sözleşme Süreçlerinin Yürütülmesi", S_SOZLESME,
  "Sözleşmenin sona ermesinden itibaren 10 yıl", "Yetkili Kamu Kurum ve Kuruluşları", "Hayır", "",
  tedbir("yetki"), tedbir("politika", idari=True), IMHA_SIL, PERIYODIK, KARMA, ""),

 # Adli sicil - ozel nitelikli, dogru sebep
 ("HUKUK MÜŞAVİRLİĞİ", "Görev Öncesi Güvenlik İncelemesi", "Ceza Mahkumiyeti ve Güvenlik Tedbirleri",
  "Adli sicil kaydı", "Adli sicil kaydı", "Çalışan Adayı",
  "Çalışan Adayı / Stajyer / Öğrenci Seçme Ve Yerleştirme Süreçlerinin Yürütülmesi", S_KANUN,
  "İşe alım kararından itibaren 1 yıl", "Yetkili Kamu Kurum ve Kuruluşları", "Hayır", "",
  tedbir("sifre", "yetki", "anahtar"), tedbir("gizlilik", "disiplin", idari=True),
  IMHA_YOK, PERIYODIK, KARMA, ""),

 ("HUKUK MÜŞAVİRLİĞİ", "KVKK İlgili Kişi Başvuruları", "Kimlik",
  "Başvuran ad soyad, T.C. kimlik numarası, başvuru içeriği", "", "Diğer(İlgili Kişi)",
  "Talep / Şikayetlerin Takibi", S_HUKUKI,
  "Başvurunun sonuçlanmasından itibaren 3 yıl", "Yetkili Kamu Kurum ve Kuruluşları", "Hayır", "",
  tedbir("yetki", "sifre"), tedbir("politika", "egitim", idari=True), IMHA_SIL, PERIYODIK, KARMA, ""),

 # --- PAZARLAMA ---
 ("PAZARLAMA MÜDÜRLÜĞÜ", "E-Bülten ve Kampanya Gönderimi", "İletişim",
  "E-posta adresi, cep telefonu", "", "Potansiyel Ürün veya Hizmet Alıcısı",
  "Pazarlama Analiz Çalışmalarının Yürütülmesi", S_RIZA,
  "Rızanın geri alınmasına kadar", "Gerçek kişiler veya özel hukuk tüzel kişileri", "Hayır", "",
  tedbir("ag", "yetki"), tedbir("politika", idari=True), IMHA_SIL, PERIYODIK, ELEKTRONIK,
  "Toplu e-posta gönderim sağlayıcısı"),

 ("PAZARLAMA MÜDÜRLÜĞÜ", "Web Sitesi Çerez Yönetimi", "Pazarlama",
  "Çerez kimliği, gezinme geçmişi", "", "Potansiyel Ürün veya Hizmet Alıcısı",
  "Pazarlama Analiz Çalışmalarının Yürütülmesi", S_RIZA,
  "Çerez ömrü boyunca, azami 1 yıl", "Gerçek kişiler veya özel hukuk tüzel kişileri", "Evet",
  "Amerika Birleşik Devletleri", tedbir("ag", "sifre"), tedbir("politika", idari=True),
  IMHA_ANON, PERIYODIK, ELEKTRONIK, "Web analitik hizmet sağlayıcısı"),

 ("PAZARLAMA MÜDÜRLÜĞÜ", "Müşteri Memnuniyet Araştırması", "Diğer(Anket Yanıtı)",
  "Anket cevapları, müşteri numarası", "", "Müşteri",
  "Müşteri Memnuniyetine Yönelik Aktivitelerin Yürütülmesi", S_MESRU,
  "Araştırmanın tamamlanmasından itibaren 2 yıl", "Yetkili Kamu Kurum ve Kuruluşları", "Hayır", "",
  tedbir("yetki"), tedbir("politika", idari=True), IMHA_ANON, PERIYODIK, ELEKTRONIK, ""),

 # ENV-006 ornegi: tek dayanak acik riza
 ("PAZARLAMA MÜDÜRLÜĞÜ", "Etkinlik Fotoğraf ve Video Çekimi", "Görsel ve İşitsel Kayıtlar",
  "Fotoğraf, video görüntüsü", "", "Müşteri",
  "Reklam / Kampanya / Promosyon Süreçlerinin Yürütülmesi", S_RIZA,
  "Rızanın geri alınmasına kadar", "Herkese açık", "Hayır", "",
  tedbir("yetki"), tedbir("politika", idari=True), IMHA_SIL, PERIYODIK, ELEKTRONIK, ""),

 # --- MÜŞTERİ HİZMETLERİ ---
 ("MÜŞTERİ HİZMETLERİ MÜDÜRLÜĞÜ", "Çağrı Merkezi Ses Kaydı", "Görsel ve İşitsel Kayıtlar",
  "Ses kaydı, telefon numarası", "", "Müşteri",
  "Talep / Şikayetlerin Takibi", S_MESRU,
  "Kayıt tarihinden itibaren 3 yıl", "Yetkili Kamu Kurum ve Kuruluşları", "Hayır", "",
  tedbir("sifre", "yetki", "yedek"), tedbir("egitim", "politika", idari=True),
  IMHA_SIL, PERIYODIK, ELEKTRONIK, "Çağrı merkezi hizmet sağlayıcısı"),

 ("MÜŞTERİ HİZMETLERİ MÜDÜRLÜĞÜ", "Müşteri Kayıt ve Üyelik Yönetimi", "Kimlik",
  "Ad soyad, T.C. kimlik numarası, doğum tarihi", "", "Müşteri",
  "Mal / Hizmet Satış Süreçlerinin Yürütülmesi", S_SOZLESME,
  "Üyeliğin sona ermesinden itibaren 10 yıl", "Yetkili Kamu Kurum ve Kuruluşları", "Hayır", "",
  tedbir("ag", "sifre", "yetki"), tedbir("politika", "egitim", idari=True),
  IMHA_SIL, PERIYODIK, ELEKTRONIK, ""),

 ("MÜŞTERİ HİZMETLERİ MÜDÜRLÜĞÜ", "Şikâyet ve İtiraz Yönetimi", "Diğer(Şikâyet Kaydı)",
  "Şikâyet içeriği, iletişim bilgisi", "", "Müşteri",
  "Talep / Şikayetlerin Takibi", S_HUKUKI,
  "Şikâyetin kapanmasından itibaren 5 yıl", "Yetkili Kamu Kurum ve Kuruluşları", "Hayır", "",
  tedbir("yetki", "sifre"), tedbir("politika", idari=True), IMHA_SIL, PERIYODIK, KARMA, ""),

 # Eksik saklama suresi (ENV-001)
 ("MÜŞTERİ HİZMETLERİ MÜDÜRLÜĞÜ", "Sosyal Medya Etkileşim Takibi", "İletişim",
  "Kullanıcı adı, mesaj içeriği", "", "Potansiyel Ürün veya Hizmet Alıcısı",
  "İletişim Faaliyetlerinin Yürütülmesi", S_RIZA,
  "", "Gerçek kişiler veya özel hukuk tüzel kişileri", "Hayır", "",
  tedbir("ag"), "", "", "", ELEKTRONIK, "Sosyal medya yönetim platformu"),

 # --- İDARİ İŞLER / GÜVENLİK ---
 ("İDARİ İŞLER MÜDÜRLÜĞÜ", "Bina Giriş-Çıkış Kontrolü", "Fiziksel Mekan Güvenliği",
  "Kartlı geçiş kaydı, ad soyad", "", "Çalışan",
  "Fiziksel Mekan Güvenliğinin Temini", S_MESRU,
  "Kayıt tarihinden itibaren 2 yıl", "Yetkili Kamu Kurum ve Kuruluşları", "Hayır", "",
  tedbir("yetki", "yedek"), tedbir("politika", idari=True), IMHA_SIL, PERIYODIK, ELEKTRONIK, ""),

 ("İDARİ İŞLER MÜDÜRLÜĞÜ", "Kamera ile İzleme Faaliyeti", "Görsel ve İşitsel Kayıtlar",
  "Güvenlik kamerası görüntüsü", "", "Ziyaretçi",
  "Fiziksel Mekan Güvenliğinin Temini", S_MESRU,
  "Kayıt tarihinden itibaren 30 gün", "Yetkili Kamu Kurum ve Kuruluşları", "Hayır", "",
  tedbir("sifre", "yetki", "yedek"), tedbir("politika", "egitim", idari=True),
  IMHA_SIL, PERIYODIK, ELEKTRONIK, "Özel güvenlik hizmet sağlayıcısı"),

 ("İDARİ İŞLER MÜDÜRLÜĞÜ", "Araç Filo Yönetimi", "Diğer(Araç Bilgisi)",
  "Plaka, sürücü belgesi bilgisi, km kaydı", "", "Çalışan",
  "Taşınır Mal Ve Kaynakların Güvenliğinin Temini", S_MESRU,
  "Zimmetin sona ermesinden itibaren 5 yıl", "Yetkili Kamu Kurum ve Kuruluşları", "Hayır", "",
  tedbir("yetki"), tedbir("politika", idari=True), IMHA_SIL, PERIYODIK, KARMA, ""),

 ("İDARİ İŞLER MÜDÜRLÜĞÜ", "Kurumsal Arşiv Yönetimi", "Özlük",
  "Arşiv dosya bilgileri", "", "Çalışan",
  "Saklama Ve Arşiv Faaliyetlerinin Yürütülmesi", S_HUKUKI,
  "Mevzuatta öngörülen süre boyunca", "Yetkili Kamu Kurum ve Kuruluşları", "Hayır", "",
  tedbir("yetki"), tedbir("politika", "disiplin", idari=True), IMHA_YOK, PERIYODIK, FIZIKSEL, ""),

 ("İDARİ İŞLER MÜDÜRLÜĞÜ", "Yemekhane ve Servis Yönetimi", "Diğer(Kullanım Kaydı)",
  "Yemekhane kart kaydı, servis güzergâh tercihi", "", "Çalışan",
  "Çalışanlar İçin Yan Haklar Ve Menfaatleri Süreçlerinin Yürütülmesi", S_MESRU,
  "Dönem sonundan itibaren 1 yıl", "Gerçek kişiler veya özel hukuk tüzel kişileri", "Hayır", "",
  tedbir("yetki"), tedbir("politika", idari=True), IMHA_SIL, PERIYODIK, ELEKTRONIK,
  "Yemek ve servis hizmeti sağlayıcısı"),
]

ALANLAR = ("birim", "faaliyet", "veri_kategorisi", "kisisel_veri", "ozel_nitelikli_veri",
           "kisi_grubu", "isleme_amaci", "hukuki_sebep", "saklama_suresi", "alici_grubu",
           "yurt_disi_aktarim", "yurt_disi_ulke", "teknik_tedbir", "idari_tedbir",
           "imha_yontemi", "periyodik_imha_suresi", "kayit_ortami", "veri_isleyen")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--replace", action="store_true",
                    help="mevcut envanteri sil ve yalnizca ornek veriyi yukle")
    args = ap.parse_args()

    conn = store.connect()
    try:
        if args.replace:
            conn.executescript("DELETE FROM envanter; DELETE FROM envanter_log;")
            # autoincrement sayaci da sifirlansin, ornek veri 1'den baslasin
            conn.execute("DELETE FROM sqlite_sequence WHERE name IN ('envanter','envanter_log')")
            conn.commit()
            print("Mevcut envanter silindi.")

        for kayit in K:
            store.create(conn, dict(zip(ALANLAR, kayit)), kaynak="ornek")

        rows = store.all_rows(conn)
    finally:
        conn.close()

    print(f"{len(K)} örnek kayıt eklendi — kurum: {KURUM}")
    print(f"Envanterdeki toplam satır: {len(rows)}")

    ornek = [r for r in rows if r.birim and r.birim.endswith("MÜDÜRLÜĞÜ") or r.birim == "HUKUK MÜŞAVİRLİĞİ"]
    rapor = audit.audit(ornek)
    print(f"\nÖrnek kayıtların denetimi: {rapor['satir']} satır, {rapor['bulgu']} bulgu")
    print(f"  temiz satır: {rapor['temiz_satir']}  uyum: %{rapor['uyum_orani']*100:.1f}")
    print(f"  seviye: {rapor['seviye']}")
    print(f"  kural : {rapor['kod']}")
    ozel = [r for r in ornek if r.veri_kategorisi and taxonomy.is_ozel_nitelikli_kategori(r.veri_kategorisi)]
    print(f"  özel nitelikli kategori içeren satır: {len(ozel)}")


if __name__ == "__main__":
    main()
