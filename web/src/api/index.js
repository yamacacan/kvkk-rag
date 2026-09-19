// API uclari tek yerde; view'lar yol bilmez.
import { api, apiFetch, dosyaIndir } from './http';

const qs = (obj) => {
  const p = new URLSearchParams();
  Object.entries(obj || {}).forEach(([k, v]) => { if (v !== '' && v !== null && v !== undefined) p.set(k, v); });
  const s = p.toString();
  return s ? '?' + s : '';
};

export const auth = {
  login: (email, password) => api('/api/auth/login', { method: 'POST', body: { email, password, device: 'web' }, auth: false }),
  refresh: (refresh_token) => api('/api/auth/refresh', { method: 'POST', body: { refresh_token }, auth: false }),
  logout: (refresh_token) => api('/api/auth/logout', { method: 'POST', body: { refresh_token } }),
  me: () => api('/api/auth/me'),
  forgotPassword: (email) => api('/api/auth/forgot-password', { method: 'POST', body: { email }, auth: false }),
  resetPassword: (veri) => api('/api/auth/reset-password', { method: 'POST', body: veri, auth: false }),
  // kendi hesabi
  profilGuncelle: (veri) => api('/api/auth/profile', { method: 'PATCH', body: veri }),
  sifreDegistir: (veri) => api('/api/auth/password', { method: 'POST', body: veri }),
  oturumlar: () => api('/api/auth/sessions'),
  oturumKapat: (id) => api('/api/auth/sessions/' + id, { method: 'DELETE' }),
  digerOturumlariKapat: () => api('/api/auth/sessions/revoke-others', { method: 'POST' }),
};

export const panel = {
  getir: () => api('/api/dashboard'),
};

// ---- yonetim ----
export const kullanicilar = {
  liste: () => api('/api/users'),
  getir: (id) => api('/api/users/' + id),
  olustur: (veri) => api('/api/users', { method: 'POST', body: veri }),
  guncelle: (id, veri) => api('/api/users/' + id, { method: 'PATCH', body: veri }),
  sil: (id) => api('/api/users/' + id, { method: 'DELETE' }),
};

export const roller = {
  liste: () => api('/api/roles'),
  getir: (id) => api('/api/roles/' + id),
  olustur: (veri) => api('/api/roles', { method: 'POST', body: veri }),
  guncelle: (id, veri) => api('/api/roles/' + id, { method: 'PATCH', body: veri }),
  kapsamlar: (id, scopes) => api(`/api/roles/${id}/scopes`, { method: 'PUT', body: { scopes } }),
  klonla: (id, name) => api(`/api/roles/${id}/clone`, { method: 'POST', body: { name } }),
  sil: (id) => api('/api/roles/' + id, { method: 'DELETE' }),
};

export const izinler = {
  liste: () => api('/api/permissions'),
  onbellekSifirla: () => api('/api/permissions/cache-reset', { method: 'POST' }),
};

export const birimler = {
  liste: () => api('/api/departments'),
  getir: (id) => api('/api/departments/' + id),
  olustur: (veri) => api('/api/departments', { method: 'POST', body: veri }),
  guncelle: (id, veri) => api('/api/departments/' + id, { method: 'PATCH', body: veri }),
  sil: (id) => api('/api/departments/' + id, { method: 'DELETE' }),
};

export const gunluk = {
  liste: (filtre) => api('/api/audit-logs' + qs(filtre)),
  // her rota degisiminde: kim hangi ekrana bakti (denetim gunlugu page.view)
  sayfaGoruntule: (veri) => api('/api/audit-logs/page-view', { method: 'POST', body: veri }),
};

// ---- bildirimler (header zili) ----
export const bildirimler = {
  // liste(20) (zil) veya liste({durum, tur, arama, limit, offset}) (Tüm bildirimler sayfasi)
  liste: (f = 20) => api('/api/notifications' + qs(typeof f === 'number' ? { limit: f } : f)),
  okunmamis: () => api('/api/notifications/unread-count'),
  oku: (id) => api(`/api/notifications/${id}/read`, { method: 'POST' }),
  okunmadiYap: (id) => api(`/api/notifications/${id}/unread`, { method: 'POST' }),
  hepsiniOku: () => api('/api/notifications/read-all', { method: 'POST' }),
  okunmuslariTemizle: () => api('/api/notifications/clear-read', { method: 'POST' }),
  sil: (id) => api('/api/notifications/' + id, { method: 'DELETE' }),
};

// ---- kuyruk (arka plan isleri) ----
export const kuyruk = {
  liste: (filtre) => api('/api/queue' + qs(filtre)),
  yenidenDene: (id) => api(`/api/queue/${id}/retry`, { method: 'POST' }),
};

export const sistem = {
  health: () => api('/api/health', { auth: false }),
};

export const envanter = {
  liste: (filtre) => api('/api/inventory' + qs(filtre)),
  ozet: () => api('/api/inventory/summary'),
  getir: (satirNo) => api('/api/inventory/' + satirNo),
  olustur: (veri) => api('/api/inventory', { method: 'POST', body: veri }),
  guncelle: (satirNo, veri) => api('/api/inventory/' + satirNo, { method: 'PATCH', body: veri }),
  sil: (satirNo) => api('/api/inventory/' + satirNo, { method: 'DELETE' }),
  topluSil: (satirlar) => api('/api/inventory/bulk-delete', { method: 'POST', body: { satir_no: satirlar } }),
  oneri: (veri) => api('/api/inventory/suggest', { method: 'POST', body: veri }),
  gecmis: (satirNo) => api(`/api/inventory/${satirNo}/history`),
  excel: (filtre) => dosyaIndir('/api/inventory/export' + qs(filtre), { varsayilanAd: 'veri_envanteri.xlsx' }),
  // ---- kuyruklu isler: Excel disa/ice aktarim, yeniden indeksleme; hazir olunca bildirim ----
  disaAktar: (veri) => api('/api/inventory/export', { method: 'POST', body: veri }),
  iceAktar: (dosya, mod = 'ekle') => { const f = new FormData(); f.append('dosya', dosya); f.append('mod', mod); return api('/api/inventory/import', { method: 'POST', body: f }); },
  yenidenIndeksle: () => api('/api/inventory/reindex', { method: 'POST' }),
  islemler: (limit = 30) => api('/api/inventory/islemler' + qs({ limit })),
  islem: (id) => api('/api/inventory/islemler/' + id),
  islemIndir: (id, ad = 'veri_envanteri.xlsx') => dosyaIndir(`/api/inventory/islemler/${id}/indir`, { varsayilanAd: ad }),
  islemSil: (id) => api('/api/inventory/islemler/' + id, { method: 'DELETE' }),
};

export const taksonomi = {
  getir: () => api('/api/taxonomy'),
};

export const profil = {
  getir: () => api('/api/profile'),
  kaydet: (veri) => api('/api/profile', { method: 'PUT', body: veri }),
};

export const belgeler = {
  liste: () => api('/api/documents'),
  faaliyetler: (birim) => api('/api/documents/faaliyetler' + qs({ birim })),
  onizleme: (veri) => api('/api/documents/preview', { method: 'POST', body: veri }),
  // uretim kuyruga alinir (202); belge hazir olunca bildirim gelir, /uretilen listesinden indirilir
  uret: (veri) => api('/api/documents/generate', { method: 'POST', body: veri }),
  uretHepsi: (veri) => api('/api/documents/generate-all', { method: 'POST', body: veri }),
  uretilenler: (limit = 30) => api('/api/documents/uretilen' + qs({ limit })),
  uretilen: (id) => api('/api/documents/uretilen/' + id),
  indir: (id, ad = 'belge') => dosyaIndir(`/api/documents/uretilen/${id}/indir`, { varsayilanAd: ad }),
  uretilenSil: (id) => api('/api/documents/uretilen/' + id, { method: 'DELETE' }),
};

// ---- faaliyet belgeleri: envanter degisince otomatik yenilenen Aydinlatma / Acik Riza ----
export const faaliyetBelgeleri = {
  liste: () => api('/api/faaliyet-belgeleri'),
  yenile: (faaliyet) => api('/api/faaliyet-belgeleri/yenile' + qs({ faaliyet }), { method: 'POST' }),
  getir: (id) => api('/api/faaliyet-belgeleri/' + id),
  indir: (id, ad = 'belge.docx') => dosyaIndir(`/api/faaliyet-belgeleri/${id}/indir`, { varsayilanAd: ad }),
};

// ---- acik riza kayitlari (consents) ----
export const acikRiza = {
  liste: (filtre) => api('/api/consents' + qs(filtre)),
  faaliyetler: () => api('/api/consents/faaliyetler'),
  getir: (id) => api('/api/consents/' + id),
  olustur: (veri) => api('/api/consents', { method: 'POST', body: veri }),
  guncelle: (id, veri) => api('/api/consents/' + id, { method: 'PATCH', body: veri }),
  sil: (id) => api('/api/consents/' + id, { method: 'DELETE' }),
};

export const asistan = {
  sohbet: (messages, limit = 10) => api('/api/chat', { method: 'POST', body: { messages, limit } }),
};

export const graf = {
  risk: (limit = 10) => api('/api/graph/risk' + qs({ limit })),
  madde: (no) => api('/api/graph/madde/' + encodeURIComponent(no)),
};

export { apiFetch };
