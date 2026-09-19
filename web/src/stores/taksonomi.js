// Acilir liste kaynaklari (seeder taksonomisi + envanterden turetilenler); bir kez yuklenir.
import { defineStore } from 'pinia';
import { taksonomi as taxApi } from '../api';

export const useTaksonomiStore = defineStore('taksonomi', {
  state: () => ({ veri: null, yukleniyor: false }),
  getters: {
    ozelKategoriler: (s) => new Set(s.veri?.ozel_nitelikli_kategoriler || []),
  },
  actions: {
    async yukle() {
      if (this.veri || this.yukleniyor) return this.veri;
      this.yukleniyor = true;
      try { this.veri = await taxApi.getir(); } finally { this.yukleniyor = false; }
      return this.veri;
    },
    secenekler(grup, alan) { return this.veri?.[grup]?.[alan] || []; },
  },
});
