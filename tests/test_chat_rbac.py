import asyncio
import os
import pathlib
import shutil
import tempfile
import unittest

from kvkk_rag.config import settings

_TMP = pathlib.Path(tempfile.mkdtemp(prefix="kvkk_chat_rbac_"))
settings.SQLITE_PATH = _TMP / "chat_rbac.db"
os.environ["KVKK_ADMIN_EMAIL"] = "admin@test.local"
os.environ["KVKK_ADMIN_PASSWORD"] = "admin-sifre-123"

from kvkk_rag.api.app.Models.department import Department
from kvkk_rag.api.app.Models.user import User
from kvkk_rag.api.app.Services import hashing
from kvkk_rag.api.app.Services.permission_cache import MemoryStore, cache
from kvkk_rag.api.database import connection
from kvkk_rag.chat import engine as chat_engine
from kvkk_rag.inventory import store as inv_store

hashing.ITERATIONS = 1000


class DummyLLM:
    name = "dummy"

    def complete(self, messages, temperature=0.0, max_tokens=500):
        # En son kullanici mesajina gore yanit
        user_msg = messages[-1]["content"] if messages else ""
        if "Satır 1" in user_msg or "satır 1" in user_msg:
            return '{"bagimsiz_soru": "Satır 1 saklama süresini 5 yıl yap", "envanter_ilgili": true, "veritabani_sorgusu": true, "satir_no": 1, "guncelleme_istegi": true, "guncellenecek_alanlar": {"saklama_suresi": "5 yıl"}}'
        if "Satır 2" in user_msg or "satır 2" in user_msg:
            return '{"bagimsiz_soru": "Satır 2 saklama süresini 10 yıl yap", "envanter_ilgili": true, "veritabani_sorgusu": true, "satir_no": 2, "guncelleme_istegi": true, "guncellenecek_alanlar": {"saklama_suresi": "10 yıl"}}'
        if "Veritabanı" in user_msg or "veritabanı" in user_msg or "kayıtlar" in user_msg:
            return '{"bagimsiz_soru": "Veritabanındaki kayıtlar neler?", "envanter_ilgili": true, "veritabani_sorgusu": true}'
        return '{"bagimsiz_soru": "Genel soru", "envanter_ilgili": false}'


class TestChatRbac(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from kvkk_rag.api import bootstrap

        settings.SQLITE_PATH = _TMP / "chat_rbac.db"
        connection.reset()
        cache.store = MemoryStore()
        cls.app = bootstrap.create_app(graphql=False, static=False, seed=False)
        conn = connection.connect()

        # Envanter satirlari ekle
        inv_store.create(conn, {
            "birim": "İK",
            "faaliyet": "İşe alım",
            "kisisel_veri": "Aday Telefon",
            "saklama_suresi": "2 Yıl"
        }, kaynak="xlsx")
        inv_store.create(conn, {
            "birim": "Pazarlama",
            "faaliyet": "Kampanya",
            "kisisel_veri": "Müşteri E-posta",
            "saklama_suresi": "1 Yıl"
        }, kaynak="xlsx")
        conn.close()

        bootstrap.migrate_and_seed()

        conn = connection.connect()
        cls.conn = conn

        # Kullanicilari hazirla
        cls.admin = User.find_by_email(conn, "admin@test.local")

        # İK departmani
        dep_ik = Department.find_by_name(conn, "İK")
        if not dep_ik:
            dep_ik = Department.create(conn, name="İK")

        # Birim Sorumlusu: Ayse (İK departmani)
        cls.ayse = User.register(conn, "Ayşe", "ayse@test.local", "sifre1234", department_id=dep_ik.id)
        cls.ayse.assign_role(conn, "Birim Sorumlusu")

        # İzleyici: Mehmet (Salt okunur, inventory.update yok)
        cls.mehmet = User.register(conn, "Mehmet", "mehmet@test.local", "sifre1234")
        cls.mehmet.assign_role(conn, "İzleyici")

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()
        shutil.rmtree(_TMP, ignore_errors=True)

    def setUp(self):
        self._orig_get_llm = chat_engine.get_llm
        chat_engine.get_llm = lambda provider=None: DummyLLM()

    def tearDown(self):
        chat_engine.get_llm = self._orig_get_llm

    def test_superadmin_satir_guncelleme_yetkili(self):
        res = chat_engine.chat(
            [{"role": "user", "content": "Satır 1'in saklama süresini 5 yıl yap"}],
            user=self.admin, conn=self.conn
        )
        self.assertIsNotNone(res.veritabani)
        guncelleme = res.veritabani.get("guncelleme")
        self.assertIsNotNone(guncelleme)
        self.assertTrue(guncelleme["yetkili"])
        self.assertEqual(guncelleme["satir_no"], 1)
        self.assertEqual(guncelleme["yeni_degerler"].get("saklama_suresi"), "5 yıl")

    def test_birim_sorumlusu_kendi_departmanina_yetkili(self):
        # Satır 1 -> İK (Ayşe'nin departmanı)
        res = chat_engine.chat(
            [{"role": "user", "content": "Satır 1'in saklama süresini 5 yıl yap"}],
            user=self.ayse, conn=self.conn
        )
        self.assertIsNotNone(res.veritabani)
        guncelleme = res.veritabani.get("guncelleme")
        self.assertIsNotNone(guncelleme)
        self.assertTrue(guncelleme["yetkili"])
        self.assertEqual(guncelleme["satir_no"], 1)
        self.assertEqual(guncelleme["kapsam"], "department")

    def test_birim_sorumlusu_baska_departmana_kapsam_yetersiz(self):
        # Satır 2 -> Pazarlama (Ayşe İK sorumlusu, Pazarlama kapsamı dışı!)
        res = chat_engine.chat(
            [{"role": "user", "content": "Satır 2'nin saklama süresini 10 yıl yap"}],
            user=self.ayse, conn=self.conn
        )
        self.assertIsNotNone(res.veritabani)
        guncelleme = res.veritabani.get("guncelleme")
        self.assertIsNotNone(guncelleme)
        self.assertFalse(guncelleme["yetkili"])
        self.assertIn("dışındadır", guncelleme["sebep"])

    def test_izleyici_guncelleme_yetkisiz(self):
        # Mehmet İzleyici rolündedir, 'inventory.update' izni yoktur
        res = chat_engine.chat(
            [{"role": "user", "content": "Satır 1'in saklama süresini 5 yıl yap"}],
            user=self.mehmet, conn=self.conn
        )
        self.assertIsNotNone(res.veritabani)
        guncelleme = res.veritabani.get("guncelleme")
        self.assertIsNotNone(guncelleme)
        self.assertFalse(guncelleme["yetkili"])
        self.assertIn("inventory.update", guncelleme["sebep"])

    def test_kapsam_filtreli_veritabani_goruntuleme(self):
        # Ayşe (İK Sorumlusu) veritabanı sorguladığında sadece İK satırlarını görmeli
        res = chat_engine.chat(
            [{"role": "user", "content": "Veritabanındaki kayıtlar neler?"}],
            user=self.ayse, conn=self.conn
        )
        self.assertIsNotNone(res.veritabani)
        self.assertTrue(res.veritabani["goruntuleme_yetkisi"])
        satirlar = res.veritabani["satirlar"]
        self.assertTrue(len(satirlar) > 0)
        # Sadece İK departmanı olmalı
        for s in satirlar:
            self.assertEqual(s["birim"], "İK")

    def test_http_chat_api(self):
        try:
            import httpx
        except ImportError:
            return

        async def run():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url="http://test") as c:
                # Login Ayse
                r_login = await c.post("/api/auth/login", json={"email": "ayse@test.local", "password": "sifre1234"})
                self.assertEqual(r_login.status_code, 200)
                h = {"Authorization": f"Bearer {r_login.json()['access_token']}"}

                # Chat post (Ayşe İK birim sorumlusu -> Satır 1 yetkili)
                r_chat1 = await c.post("/api/chat", headers=h, json={
                    "messages": [{"role": "user", "content": "Satır 1'in saklama süresini 5 yıl yap"}]
                })
                self.assertEqual(r_chat1.status_code, 200, r_chat1.text)
                data1 = r_chat1.json()
                self.assertIn("envanter", data1)
                self.assertTrue(data1["envanter"]["guncelleme"]["yetkili"])
                self.assertEqual(data1["envanter"]["guncelleme"]["satir_no"], 1)

                # Chat post (Ayşe -> Satır 2 Pazarlama -> kapsam dışı yetkisiz)
                r_chat2 = await c.post("/api/chat", headers=h, json={
                    "messages": [{"role": "user", "content": "Satır 2'nin saklama süresini 10 yıl yap"}]
                })
                self.assertEqual(r_chat2.status_code, 200, r_chat2.text)
                data2 = r_chat2.json()
                self.assertFalse(data2["envanter"]["guncelleme"]["yetkili"])

        asyncio.run(run())
