// Uygulama ici bildirimler (header zili). Sunucudaki notifications tablosunu
// periyodik yoklar (varsayilan 20 sn; sekme gizliyken durur, bekleyen belge varken
// sıklaşır). Yeni bir bildirim gelince toast da gosterir ve 'yeni' olayini yayar
// (ornegin Belgeler sayfasi listesini tazeler).
import { defineStore } from 'pinia';
import { bildirimler as api } from '../api';
import { useAuthStore } from './auth';
import { useUiStore } from './ui';

const NORMAL = 20000;
const HIZLI = 5000;

export const useBildirimStore = defineStore('bildirim', {
  state: () => ({
    liste: [],
    okunmamis: 0,
    acik: false,
    yukleniyor: false,
    sonId: null,          // en son gorulen bildirim id'si (yeni gelenleri ayirt etmek icin)
    hizli: false,         // bekleyen is varken sik yokla
    _zamanlayici: null,
    _dinleyiciler: [],    // yeni bildirim geldiginde cagrilacak fonksiyonlar
  }),
  actions: {
    async yukle({ sessiz = false } = {}) {
      const auth = useAuthStore();
      if (!auth.isAuthenticated) return;
      if (!sessiz) this.yukleniyor = true;
      try {
        const d = await api.liste(20);
        const yeniler = this.sonId === null ? [] : d.bildirimler.filter((b) => b.id > this.sonId);
        this.liste = d.bildirimler;
        this.okunmamis = d.okunmamis;
        if (d.bildirimler.length) this.sonId = Math.max(this.sonId ?? 0, ...d.bildirimler.map((b) => b.id));
        else if (this.sonId === null) this.sonId = 0;
        if (yeniler.length) this.yeniGeldi(yeniler);
      } catch {} finally { this.yukleniyor = false; }
    },
    yeniGeldi(yeniler) {
      const ui = useUiStore();
      const TUR = { ok: 'ok', hata: 'hata', uyari: 'uyari', bilgi: 'bilgi' };
      // En fazla 3 toast; fazlasi tek satirda ozetlenir
      yeniler.slice(0, 3).forEach((b) => ui.toast({ baslik: b.title, metin: b.body || '', tur: TUR[b.level] || 'bilgi', sure: 7000 }));
      if (yeniler.length > 3) ui.bildir(`${yeniler.length - 3} bildirim daha geldi.`, 'bilgi');
      this._dinleyiciler.forEach((fn) => { try { fn(yeniler); } catch {} });
    },
    dinle(fn) {
      this._dinleyiciler.push(fn);
      return () => { this._dinleyiciler = this._dinleyiciler.filter((f) => f !== fn); };
    },
    async oku(id) {
      const b = this.liste.find((x) => x.id === id);
      if (b && !b.okundu) {
        b.okundu = true; this.okunmamis = Math.max(0, this.okunmamis - 1);
        try { await api.oku(id); } catch {}
      }
    },
    async hepsiniOku() {
      this.liste.forEach((b) => { b.okundu = true; });
      this.okunmamis = 0;
      try { await api.hepsiniOku(); } catch {}
    },
    async sil(id) {
      const b = this.liste.find((x) => x.id === id);
      this.liste = this.liste.filter((x) => x.id !== id);
      if (b && !b.okundu) this.okunmamis = Math.max(0, this.okunmamis - 1);
      try { await api.sil(id); } catch {}
    },
    // ---- yoklama ----
    _tur() {
      clearTimeout(this._zamanlayici);
      this._zamanlayici = setTimeout(async () => {
        if (document.visibilityState === 'visible') await this.yukle({ sessiz: true });
        if (this._zamanlayici) this._tur();
      }, this.hizli ? HIZLI : NORMAL);
    },
    basla() {
      if (this._zamanlayici) return;
      this.yukle({ sessiz: true });
      this._tur();
      document.addEventListener('visibilitychange', this._gorunurluk);
    },
    durdur() {
      clearTimeout(this._zamanlayici); this._zamanlayici = null;
      document.removeEventListener('visibilitychange', this._gorunurluk);
      this.liste = []; this.okunmamis = 0; this.sonId = null; this.hizli = false;
    },
    _gorunurluk() {
      // sekmeye donunce hemen tazele
      if (document.visibilityState === 'visible') useBildirimStore().yukle({ sessiz: true });
    },
    hizliYokla(acik) {
      // bekleyen is varken sik yokla; degisiklik hemen uygulansin (mevcut bekleme kesilir)
      if (this.hizli === !!acik) return;
      this.hizli = !!acik;
      if (this._zamanlayici) this._tur();
    },
  },
});
