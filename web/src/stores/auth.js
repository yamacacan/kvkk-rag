// Oturum durumu (Pinia): JWT access + refresh jetonu, kullanici, izin/kapsam sorgusu.
// Jetonlar localStorage'da tutulur; sayfa yenilenince /api/auth/me ile dogrulanir.
import { defineStore } from 'pinia';
import { auth as authApi } from '../api';

const KEY = 'kvkk_oturum';

function oku() {
  try { return JSON.parse(localStorage.getItem(KEY) || 'null') || {}; } catch { return {}; }
}

export const useAuthStore = defineStore('auth', {
  state: () => {
    const k = oku();
    return {
      user: k.user || null,
      accessToken: k.accessToken || '',
      refreshToken: k.refreshToken || '',
      dogrulandi: false, // bu oturumda /me ile teyit edildi mi
    };
  },
  getters: {
    isAuthenticated: (s) => !!s.accessToken && !!s.user,
    isSuper: (s) => !!s.user?.is_super,
    permissions: (s) => s.user?.permissions || [],
    roller: (s) => s.user?.roles || [],
  },
  actions: {
    can(izin) {
      if (!this.user) return false;
      if (this.user.is_super) return true;
      return this.permissions.includes(izin);
    },
    canAny(...izinler) { return izinler.some((i) => this.can(i)); },
    scope(modul, aksiyon) { return this.user?.scopes?.[modul]?.[aksiyon] || null; },

    oturumuYaz(d) {
      // login / refresh yaniti: {access_token, refresh_token, user}
      this.accessToken = d.access_token || this.accessToken;
      this.refreshToken = d.refresh_token || this.refreshToken;
      if (d.user) this.user = d.user;
      this.dogrulandi = true;
      this.kaydet();
    },
    kaydet() {
      try {
        localStorage.setItem(KEY, JSON.stringify({
          user: this.user, accessToken: this.accessToken, refreshToken: this.refreshToken,
        }));
      } catch {}
    },
    async login(email, password) {
      const d = await authApi.login(email, password);
      this.oturumuYaz(d);
      return this.user;
    },
    async fetchMe() {
      const d = await authApi.me();
      this.user = d.user; this.dogrulandi = true; this.kaydet();
      return this.user;
    },
    // Sayfa acilisinda: jeton varsa /me ile teyit; 401 ise http katmani refresh dener,
    // o da olmazsa oturumuKapat cagrilmis olur.
    async restore() {
      if (!this.accessToken && !this.refreshToken) return false;
      try { await this.fetchMe(); return true; } catch { return false; }
    },
    async oturumuKapat({ yerel = false } = {}) {
      if (!yerel && this.accessToken) {
        try { await authApi.logout(this.refreshToken || undefined); } catch {}
      }
      this.user = null; this.accessToken = ''; this.refreshToken = ''; this.dogrulandi = false;
      try { localStorage.removeItem(KEY); } catch {}
    },
  },
});
