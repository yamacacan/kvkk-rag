// Arayuz tercihleri (sidebar, tema), yukleme durumlari, toast yigini ve SweetAlert
// tarzi dialog kuyrugu; tercihler localStorage'da kalici.
import { defineStore } from 'pinia';

const KEY = 'kvkk_ui';
function oku() { try { return JSON.parse(localStorage.getItem(KEY) || '{}'); } catch { return {}; } }

const TEMALAR = ['dark', 'light', 'system'];
const sistemTemasi = () => (window.matchMedia?.('(prefers-color-scheme: light)').matches ? 'light' : 'dark');
let toastSayac = 0;

export const useUiStore = defineStore('ui', {
  state: () => ({
    sidebarDar: !!oku().sidebarDar,
    tema: TEMALAR.includes(oku().tema) ? oku().tema : 'dark',
    paletAcik: false,
    gecis: false,      // rota gecisi suruyor
    aktifIstek: 0,     // acik API istegi sayisi
    toastlar: [],      // {id, tur, baslik, metin, sure}
    dialog: null,      // {mod: 'onay'|'uyari', tur, baslik, metin, onayMetni, iptalMetni, tehlikeli, resolve}
  }),
  getters: {
    // uygulanan tema: system ise isletim sistemi tercihi
    etkinTema: (s) => (s.tema === 'system' ? sistemTemasi() : s.tema),
    bildirim: (s) => s.toastlar[s.toastlar.length - 1] || null,
  },
  actions: {
    sidebarToggle() { this.sidebarDar = !this.sidebarDar; this.kaydet(); },
    istekBasla() { this.aktifIstek += 1; },
    istekBitti() { this.aktifIstek = Math.max(0, this.aktifIstek - 1); },
    temaAyarla(t) { this.tema = TEMALAR.includes(t) ? t : 'dark'; this.temaUygula(); this.kaydet(); },
    temaDegistir() { this.temaAyarla(this.etkinTema === 'dark' ? 'light' : 'dark'); },
    temaUygula() {
      const t = this.etkinTema;
      document.documentElement.setAttribute('data-theme', t);
      document.documentElement.classList.toggle('dark', t === 'dark');
    },
    kaydet() { try { localStorage.setItem(KEY, JSON.stringify({ sidebarDar: this.sidebarDar, tema: this.tema })); } catch {} },

    // ---- toast yigini (sag ust, otomatik gizlenir, uzerine gelince durur) ----
    toast({ baslik = '', metin = '', tur = 'bilgi', sure = 4000 } = {}) {
      const id = ++toastSayac;
      this.toastlar.push({ id, baslik, metin, tur, sure });
      if (this.toastlar.length > 5) this.toastlar.splice(0, this.toastlar.length - 5);
      return id;
    },
    toastKapat(id) { this.toastlar = this.toastlar.filter((t) => t.id !== id); },
    // kisa yol: bildir('Kaydedildi.') / bildir('Hata', 'hata')
    bildir(metin, tur = 'ok', sure = 3600) {
      const BASLIK = { ok: 'Başarılı', hata: 'Hata', uyari: 'Dikkat', bilgi: 'Bilgi' };
      return this.toast({ baslik: BASLIK[tur] || 'Bilgi', metin, tur, sure });
    },

    // ---- SweetAlert tarzi dialoglar: Promise doner ----
    onay({ baslik = 'Emin misiniz?', metin = '', tur = 'uyari', onayMetni = 'Onayla', iptalMetni = 'Vazgeç', tehlikeli = false, detay = null } = {}) {
      return new Promise((resolve) => {
        this.dialog = { mod: 'onay', baslik, metin, tur, onayMetni, iptalMetni, tehlikeli: tehlikeli || tur === 'hata', detay, resolve };
      });
    },
    uyar({ baslik = '', metin = '', tur = 'bilgi', onayMetni = 'Tamam', detay = null } = {}) {
      return new Promise((resolve) => {
        this.dialog = { mod: 'uyari', baslik, metin, tur, onayMetni, detay, resolve };
      });
    },
    basari(baslik, metin = '') { return this.uyar({ baslik, metin, tur: 'ok' }); },
    hata(baslik, metin = '') { return this.uyar({ baslik, metin, tur: 'hata', onayMetni: 'Kapat' }); },
    dialogKapat(sonuc = false) {
      const d = this.dialog;
      this.dialog = null;
      d?.resolve?.(d.mod === 'onay' ? !!sonuc : undefined);
    },
  },
});
