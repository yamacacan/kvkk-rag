import unittest

from kvkk_rag.inventory.normalize import fold, match_one, EXACT, NORMALIZED, CUSTOM


class TestNormalize(unittest.TestCase):
    def test_fold_turkish_chars(self):
        self.assertEqual(fold("İSTANBUL"), "istanbul")
        self.assertEqual(fold("IŞIK"), "ışık")
        self.assertEqual(fold("ÖĞRENCİ"), "öğrenci")
        self.assertEqual(fold("ÇALIŞAN"), "çalışan")

    def test_fold_typos_and_punctuation(self):
        # Temek hak -> temel hak
        self.assertEqual(fold("TEMEK HAK VE ÖZGÜRLÜKLER"), "temel hak ve özgürlükler")
        # Doğudan -> doğrudan
        self.assertEqual(fold("DOĞUDAN DOĞRUYA"), "doğrudan doğruya")
        # Punctuation removal
        self.assertEqual(fold("veri (kişisel)"), "veri kişisel")

    def test_match_one_exact(self):
        canon = ["Kimlik", "İletişim", "Sağlık Bilgileri"]
        res = match_one("Kimlik", canon)
        self.assertEqual(res.yontem, EXACT)
        self.assertEqual(res.kanonik, "Kimlik")
        self.assertEqual(res.guven, 1.0)

    def test_match_one_case_insensitive(self):
        canon = ["Kimlik", "İletişim", "Sağlık Bilgileri"]
        res = match_one("kimlik", canon)
        self.assertEqual(res.yontem, NORMALIZED)
        self.assertEqual(res.kanonik, "Kimlik")

    def test_match_one_diger(self):
        canon = ["Kimlik", "İletişim"]
        res = match_one("Diğer(Özel Proje Verisi)", canon)
        self.assertEqual(res.yontem, CUSTOM)
        self.assertEqual(res.kanonik, "Diğer(Özel Proje Verisi)")


if __name__ == "__main__":
    unittest.main()
