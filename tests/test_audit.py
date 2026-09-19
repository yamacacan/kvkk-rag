import unittest

from kvkk_rag.inventory.audit import audit_row
from kvkk_rag.inventory.loader import InventoryRow


class TestAuditRules(unittest.TestCase):
    def test_env_001_missing_retention_period(self):
        row = InventoryRow(
            satir_no=1,
            birim="İK",
            faaliyet="İşe alım",
            veri_kategorisi="Kimlik",
            kisisel_veri="Ad Soyad",
            saklama_suresi=None,
            teknik_tedbir="SSL",
            idari_tedbir="Gizlilik Taahhütnamesi",
            imha_yontemi="Silme",
        )
        findings = audit_row(row)
        codes = [f.kod for f in findings]
        self.assertIn("ENV-001", codes)

    def test_env_002_missing_disposal_method(self):
        row = InventoryRow(
            satir_no=2,
            birim="İK",
            faaliyet="İşe alım",
            veri_kategorisi="Kimlik",
            kisisel_veri="Ad Soyad",
            saklama_suresi="10 yıl",
            teknik_tedbir="SSL",
            idari_tedbir="Gizlilik Taahhütnamesi",
            imha_yontemi=None,
        )
        findings = audit_row(row)
        codes = [f.kod for f in findings]
        self.assertIn("ENV-002", codes)

    def test_env_003_missing_measures(self):
        row = InventoryRow(
            satir_no=3,
            birim="İK",
            faaliyet="İşe alım",
            veri_kategorisi="Kimlik",
            kisisel_veri="Ad Soyad",
            saklama_suresi="10 yıl",
            imha_yontemi="Silme",
            teknik_tedbir=None,
            idari_tedbir=None,
        )
        findings = audit_row(row)
        codes = [f.kod for f in findings]
        self.assertIn("ENV-003", codes)
        self.assertEqual(codes.count("ENV-003"), 2)

    def test_env_004_special_category_wrong_basis(self):
        # Health data grounded on general processing condition (e.g. Contract performance)
        row = InventoryRow(
            satir_no=4,
            birim="Sağlık Birimi",
            faaliyet="Periyodik Muayene",
            veri_kategorisi="Sağlık Bilgileri",
            kisisel_veri="Kan Grubu",
            hukuki_sebep="Bir Sözleşmenin Kurulması veya İfasıyla Doğrudan Doğruya İlgili Olması Kaydıyla...",
            saklama_suresi="15 yıl",
            imha_yontemi="Anonimleştirme",
            teknik_tedbir="Şifreleme",
            idari_tedbir="Erişim Matrisi",
        )
        findings = audit_row(row)
        codes = [f.kod for f in findings]
        self.assertIn("ENV-004", codes)

    def test_env_005_cross_border_transfer(self):
        row = InventoryRow(
            satir_no=5,
            birim="BT",
            faaliyet="Bulut Yedekleme",
            veri_kategorisi="İletişim",
            kisisel_veri="E-posta",
            saklama_suresi="5 yıl",
            imha_yontemi="Yok Etme",
            teknik_tedbir="TLS 1.3",
            idari_tedbir="Sözleşme",
            yurt_disi_aktarim="Evet",
        )
        findings = audit_row(row)
        codes = [f.kod for f in findings]
        self.assertIn("ENV-005", codes)

    def test_env_006_consent_as_sole_basis(self):
        row = InventoryRow(
            satir_no=6,
            birim="Pazarlama",
            faaliyet="Bülten Gönderimi",
            veri_kategorisi="İletişim",
            kisisel_veri="E-posta",
            hukuki_sebep="Açık Rıza",
            saklama_suresi="3 yıl",
            imha_yontemi="Silme",
            teknik_tedbir="Erişim Yetki Kontrolü",
            idari_tedbir="Aydınlatma Metni",
        )
        findings = audit_row(row)
        codes = [f.kod for f in findings]
        self.assertIn("ENV-006", codes)


if __name__ == "__main__":
    unittest.main()
