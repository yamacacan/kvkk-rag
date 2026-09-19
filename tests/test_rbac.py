# RBAC: iki kademeli yetki (Spatie izni + kapsam), cakisma cozumu, versiyonlu onbellek,
# sorgu ve kayit seviyesi filtreleme. Gecici SQLite dosyasi uzerinde calisir.
import pathlib
import shutil
import tempfile
import unittest

from kvkk_rag.config import settings

_TMP = pathlib.Path(tempfile.mkdtemp(prefix="kvkk_rbac_"))
_SAYAC = [0]
settings.SQLITE_PATH = _TMP / "test0.db"

from kvkk_rag.api.app.Models import permission_scope as ps  # noqa: E402
from kvkk_rag.api.app.Models.department import Department  # noqa: E402
from kvkk_rag.api.app.Models.envanter import Envanter  # noqa: E402
from kvkk_rag.api.app.Models.permission_scope import PermissionScope  # noqa: E402
from kvkk_rag.api.app.Models.role import Role  # noqa: E402
from kvkk_rag.api.app.Models.user import User  # noqa: E402
from kvkk_rag.api.app.Services import hashing  # noqa: E402
from kvkk_rag.api.app.Services.permission_cache import MemoryStore, cache, flush_cache  # noqa: E402
from kvkk_rag.api.app.Services.scope_filter import ScopeFilter  # noqa: E402
from kvkk_rag.api.app.Services.scope_resolver import ScopeResolver  # noqa: E402
from kvkk_rag.api.database import connection  # noqa: E402
from kvkk_rag.api.database.seeders import DatabaseSeeder  # noqa: E402
from kvkk_rag.inventory import store as inv_store  # noqa: E402

hashing.ITERATIONS = 1000  # testte hizli olsun


def _sifirla():
    # Her test sinifi taze bir veritabani dosyasi alir (Windows acik dosyayi silmez)
    _SAYAC[0] += 1
    settings.SQLITE_PATH = _TMP / f"test{_SAYAC[0]}.db"
    connection.reset()
    cache.store = MemoryStore()
    conn = connection.connect()
    DatabaseSeeder.run(conn, with_admin=False)
    return conn


def _satir(conn, birim, created_by=None, sorumlu_id=None):
    return inv_store.create(conn, {"birim": birim, "faaliyet": "İşe alım", "kisisel_veri": "Ad"},
                            kaynak="xlsx", meta={"created_by": created_by, "sorumlu_id": sorumlu_id})


class RbacBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.conn = _sifirla()
        c = cls.conn
        cls.ik = Department.find_or_create(c, "İK")
        cls.paz = Department.find_or_create(c, "Pazarlama")
        cls.admin = User.register(c, "Admin", "admin@t.local", "x").assign_role(c, "Admin")
        cls.birim = User.register(c, "Birim", "birim@t.local", "x", department_id=cls.ik.id) \
            .assign_role(c, "Birim Sorumlusu")
        cls.denetci = User.register(c, "Denetçi", "denetci@t.local", "x").assign_role(c, "Denetçi")
        cls.veri = User.register(c, "Veri", "veri@t.local", "x").assign_role(c, "Veri Giriş")
        cls.izleyici = User.register(c, "İzleyici", "izle@t.local", "x").assign_role(c, "İzleyici")
        cls.rolsuz = User.register(c, "Rolsüz", "rolsuz@t.local", "x")
        # satirlar: ik x2 (biri veri'nin), pazarlama x2 (biri denetciye atanmis)
        cls.s_ik_veri = _satir(c, "İK", created_by=cls.veri.id)
        cls.s_ik = _satir(c, "İK")
        cls.s_paz_atanmis = _satir(c, "Pazarlama", sorumlu_id=cls.denetci.id)
        cls.s_paz = _satir(c, "Pazarlama")

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()
        shutil.rmtree(_TMP, ignore_errors=True)

    def gorunen(self, user, module="inventory", action="view"):
        q = ScopeFilter.apply(Envanter.query(self.conn), user, module, action)
        return sorted(q.pluck("satir_no"))


class TestFonksiyonelIzin(RbacBase):
    # 1. kademe: kullanici bu eylemi yapabilir mi?
    def test_izin_bicimi_modul_aksiyon(self):
        from kvkk_rag.api.app.Models.permission import parse
        self.assertEqual(parse("findings.view"), ("findings", "view"))
        with self.assertRaises(ValueError):
            parse("findings")

    def test_rol_uzerinden_izin(self):
        self.assertTrue(self.birim.can(self.conn, "inventory.create"))
        self.assertFalse(self.birim.can(self.conn, "users.create"))
        self.assertFalse(self.izleyici.can(self.conn, "inventory.create"))

    def test_dogrudan_izin(self):
        u = User.register(self.conn, "D", "dogrudan@t.local", "x")
        self.assertFalse(u.can(self.conn, "graph.view"))
        u.give_permission_to(self.conn, "graph.view")
        self.assertTrue(u.can(self.conn, "graph.view"))
        u.revoke_permission_to(self.conn, "graph.view")
        self.assertFalse(u.can(self.conn, "graph.view"))

    def test_admin_her_seyi_yapabilir(self):
        self.assertTrue(self.admin.can(self.conn, "olmayan.izin"))
        self.assertTrue(self.admin.is_super(self.conn))

    def test_pasif_kullanici_hicbir_sey_yapamaz(self):
        u = User.register(self.conn, "P", "pasif@t.local", "x", is_active=False).assign_role(self.conn, "Admin")
        self.assertFalse(u.can(self.conn, "inventory.view"))

    def test_sifre_ozeti(self):
        self.assertTrue(self.birim.check_password("x"))
        self.assertFalse(self.birim.check_password("y"))
        self.assertTrue(self.birim.password.startswith("pbkdf2_sha256$"))


class TestKapsamCozumleme(RbacBase):
    # 2. kademe: hangi veriler uzerinde?
    def test_oncelik_hiyerarsisi(self):
        self.assertEqual([ps.priority(s) for s in ("all", "department", "assigned", "own", "none")],
                         [5, 4, 3, 2, 1])
        self.assertEqual(ps.highest(["own", "department", "assigned"]), "department")
        self.assertEqual(ps.highest([]), ps.NONE)

    def test_rol_kapsamlari(self):
        c = self.conn
        self.assertEqual(self.birim.scope_for(c, "inventory", "view"), "department")
        self.assertEqual(self.denetci.scope_for(c, "inventory", "view"), "assigned")
        self.assertEqual(self.veri.scope_for(c, "inventory", "view"), "own")
        self.assertEqual(self.izleyici.scope_for(c, "inventory", "view"), "all")

    def test_admin_kapsami_atlar(self):
        # permission_scopes'ta satiri yok; yine de all
        self.assertEqual(PermissionScope.query(self.conn).where("role_id", Role.find_by_name(self.conn, "Admin").id).count(), 0)
        self.assertEqual(self.admin.scope_for(self.conn, "inventory", "view"), "all")

    def test_tanimsiz_kapsam_none(self):
        self.assertEqual(self.rolsuz.scope_for(self.conn, "inventory", "view"), "none")
        self.assertEqual(self.izleyici.scope_for(self.conn, "inventory", "delete"), "none")

    def test_coklu_rol_en_genis_kapsam_kazanir(self):
        # Veri Giris (own) + Denetci (assigned) + Birim Sorumlusu (department) -> department
        u = User.register(self.conn, "Çok", "cok@t.local", "x")
        u.assign_role(self.conn, "Veri Giriş")
        self.assertEqual(u.scope_for(self.conn, "inventory", "view"), "own")
        u.assign_role(self.conn, "Denetçi")
        self.assertEqual(u.scope_for(self.conn, "inventory", "view"), "assigned")
        u.assign_role(self.conn, "Birim Sorumlusu")
        self.assertEqual(u.scope_for(self.conn, "inventory", "view"), "department")
        u.assign_role(self.conn, "İzleyici")
        self.assertEqual(u.scope_for(self.conn, "inventory", "view"), "all")
        # izin birlesimi: delete yalnizca Birim Sorumlusu'ndan gelir -> department
        self.assertEqual(u.scope_for(self.conn, "inventory", "delete"), "department")


class TestSorguSeviyesiFiltre(RbacBase):
    # ScopeFilter.apply: Builder'a SQL kosulu eklenir
    def test_all_kosul_eklemez(self):
        q = ScopeFilter.apply(Envanter.query(self.conn), self.admin, "inventory", "view")
        sql, params = q.to_sql()
        self.assertNotIn("WHERE", sql)
        self.assertEqual(q.scope_applied, "all")

    def test_own(self):
        q = ScopeFilter.apply(Envanter.query(self.conn), self.veri, "inventory", "view")
        sql, params = q.to_sql()
        self.assertIn("envanter.created_by = ?", sql)
        self.assertEqual(params, [self.veri.id])
        self.assertEqual(self.gorunen(self.veri), [self.s_ik_veri])

    def test_assigned(self):
        q = ScopeFilter.apply(Envanter.query(self.conn), self.denetci, "inventory", "view")
        sql, _ = q.to_sql()
        self.assertIn("sorumlu_id = ?", sql)
        self.assertIn("EXISTS", sql)
        self.assertEqual(self.gorunen(self.denetci), [self.s_paz_atanmis])
        # ekip uyesi olarak atanan da gorur
        Envanter.find(self.conn, self.s_ik).assign(self.conn, None, [self.denetci.id])
        self.assertEqual(self.gorunen(self.denetci), [self.s_ik, self.s_paz_atanmis])
        Envanter.find(self.conn, self.s_ik).assign(self.conn, None, [])

    def test_department(self):
        q = ScopeFilter.apply(Envanter.query(self.conn), self.birim, "inventory", "view")
        sql, params = q.to_sql()
        self.assertIn("envanter.birim IN (SELECT name FROM departments", sql)
        self.assertEqual(params, [self.ik.id])
        self.assertEqual(self.gorunen(self.birim), [self.s_ik_veri, self.s_ik])

    def test_coklu_departman(self):
        self.birim.sync_departments(self.conn, [self.paz.id])  # tekil İK + coklu Pazarlama
        try:
            self.assertEqual(self.gorunen(self.birim), [self.s_ik_veri, self.s_ik, self.s_paz_atanmis, self.s_paz])
        finally:
            self.birim.sync_departments(self.conn, [])

    def test_departmansiz_kullanici_hicbir_sey_gormez(self):
        u = User.register(self.conn, "B2", "b2@t.local", "x").assign_role(self.conn, "Birim Sorumlusu")
        self.assertEqual(self.gorunen(u), [])

    def test_none(self):
        q = ScopeFilter.apply(Envanter.query(self.conn), self.rolsuz, "inventory", "view")
        self.assertIn("0 = 1", q.to_sql()[0])
        self.assertEqual(self.gorunen(self.rolsuz), [])
        self.assertEqual(self.gorunen(self.izleyici, "inventory", "delete"), [])


class TestKayitSeviyesiDogrulama(RbacBase):
    # User.has_scoped_permission: Spatie izni + kaydin kapsamla uyusmasi
    def test_own(self):
        c = self.conn
        self.assertTrue(self.veri.has_scoped_permission(c, "inventory", "update", Envanter.find(c, self.s_ik_veri)))
        self.assertFalse(self.veri.has_scoped_permission(c, "inventory", "update", Envanter.find(c, self.s_ik)))

    def test_department(self):
        c = self.conn
        self.assertTrue(self.birim.has_scoped_permission(c, "inventory", "delete", Envanter.find(c, self.s_ik)))
        self.assertFalse(self.birim.has_scoped_permission(c, "inventory", "delete", Envanter.find(c, self.s_paz)))

    def test_assigned(self):
        c = self.conn
        self.assertTrue(self.denetci.has_scoped_permission(c, "inventory", "update", Envanter.find(c, self.s_paz_atanmis)))
        self.assertFalse(self.denetci.has_scoped_permission(c, "inventory", "update", Envanter.find(c, self.s_paz)))

    def test_izin_yoksa_kapsam_fark_etmez(self):
        # Izleyici her satiri gorur ama silemez (izin yok)
        c = self.conn
        self.assertTrue(self.izleyici.has_scoped_permission(c, "inventory", "view", Envanter.find(c, self.s_paz)))
        self.assertFalse(self.izleyici.has_scoped_permission(c, "inventory", "delete", Envanter.find(c, self.s_paz)))

    def test_admin(self):
        self.assertTrue(self.admin.has_scoped_permission(self.conn, "inventory", "delete", Envanter.find(self.conn, self.s_paz)))

    def test_kayitsiz_aksiyon(self):
        self.assertTrue(self.veri.has_scoped_permission(self.conn, "inventory", "create"))
        self.assertFalse(self.rolsuz.has_scoped_permission(self.conn, "inventory", "create"))


class TestVersiyonluOnbellek(RbacBase):
    def test_anahtar_bicimi(self):
        v = cache.version()
        self.assertEqual(cache.scope_key([3, 1], "findings", "view"), f"scope_v{v}_1,3__findings__view")

    def test_isabet_ve_gecersizleme(self):
        c = self.conn
        rol = Role.find_by_name(c, "Veri Giriş")
        cache.hits = cache.misses = 0
        self.assertEqual(self.veri.scope_for(c, "inventory", "view"), "own")
        self.assertEqual(self.veri.scope_for(c, "inventory", "view"), "own")
        self.assertEqual((cache.misses, cache.hits), (1, 1))
        eski_surum = cache.version()
        # kapsam degisince gozlemci surumu artirir; anahtar silinmeden yeni deger okunur
        rol.set_scope(c, "inventory", "view", "department")
        self.assertGreater(cache.version(), eski_surum)
        self.assertEqual(ScopeResolver().resolve(c, self.veri, "inventory", "view"), "department")
        # eski surumlu anahtar hala depoda (O(1): tek tek silinmedi) ama artik kullanilmiyor
        self.assertEqual(cache.store.get(f"scope_v{eski_surum}_{rol.id}__inventory__view"), "own")
        rol.set_scope(c, "inventory", "view", "own")
        self.assertEqual(ScopeResolver().resolve(c, self.veri, "inventory", "view"), "own")

    def test_izin_degisince_surum_artar(self):
        c = self.conn
        rol = Role.find_by_name(c, "İzleyici")
        v = cache.version()
        self.assertFalse(self.izleyici.can(c, "inventory.create"))
        rol.give_permission_to(c, "inventory.create")
        self.assertGreater(cache.version(), v)
        self.izleyici.forget_cached()  # istek basina ezber; yeni istekte yeniden yuklenir
        self.assertTrue(self.izleyici.can(c, "inventory.create"))
        rol.revoke_permission_to(c, "inventory.create")
        self.izleyici.forget_cached()
        self.assertFalse(self.izleyici.can(c, "inventory.create"))

    def test_flush_cache_surumu_artirir(self):
        v = cache.version()
        self.assertEqual(flush_cache(), v + 1)


if __name__ == "__main__":
    unittest.main()
