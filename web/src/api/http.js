// HTTP istemcisi: JWT Bearer basligi, 401'de tek seferlik refresh + yeniden deneme,
// Turkce hata mesaji cikarimi, blob indirme. API adresi VITE_API_BASE ile ayri
// deploy'a (ornegin frontend Cloudflare Pages, API baska origin) tasinabilir.
import { useAuthStore } from '../stores/auth';
import { useUiStore } from '../stores/ui';

export const API_BASE = (import.meta.env.VITE_API_BASE || '').replace(/\/$/, '');

export class ApiError extends Error {
  constructor(status, message, errors = null) {
    super(message);
    this.status = status;
    this.errors = errors; // {alan: [mesaj]} (422)
  }
}

async function hataMesaji(r) {
  const metin = await r.text();
  try {
    const d = JSON.parse(metin);
    const detail = typeof d.detail === 'string' ? d.detail
      : Array.isArray(d.detail) ? d.detail.map((x) => x.msg || String(x)).join(', ') : null;
    return { mesaj: detail || d.mesaj || metin || `HTTP ${r.status}`, errors: d.errors || null };
  } catch {
    return { mesaj: metin || `HTTP ${r.status}`, errors: null };
  }
}

let yenilemeSozu = null; // es zamanli 401'ler tek refresh istegi paylasir

async function jetonYenile() {
  const auth = useAuthStore();
  if (!auth.refreshToken) return false;
  if (!yenilemeSozu) {
    yenilemeSozu = (async () => {
      try {
        const r = await fetch(API_BASE + '/api/auth/refresh', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: auth.refreshToken }),
        });
        if (!r.ok) return false;
        auth.oturumuYaz(await r.json());
        return true;
      } catch { return false; }
      finally { yenilemeSozu = null; }
    })();
  }
  return yenilemeSozu;
}

// Ham fetch: Response doner (indirme gibi durumlar icin). auth=false ise jeton eklenmez.
export async function apiFetch(path, { method = 'GET', body, headers = {}, auth = true, _tekrar = false } = {}) {
  const store = useAuthStore();
  const ui = useUiStore();
  const h = { ...headers };
  if (body !== undefined && !(body instanceof FormData) && !h['Content-Type']) h['Content-Type'] = 'application/json';
  if (auth && store.accessToken) h.Authorization = 'Bearer ' + store.accessToken;
  ui.istekBasla();
  let r;
  try {
    r = await fetch(API_BASE + path, {
      method, headers: h,
      body: body === undefined ? undefined : (body instanceof FormData ? body : JSON.stringify(body)),
    });
  } finally { ui.istekBitti(); }
  if (r.status === 401 && auth && !_tekrar && store.refreshToken) {
    if (await jetonYenile()) return apiFetch(path, { method, body, headers, auth, _tekrar: true });
  }
  if (r.status === 401 && auth) {
    store.oturumuKapat({ yerel: true });
    throw new ApiError(401, 'Oturum süresi doldu, lütfen tekrar giriş yapın.');
  }
  if (!r.ok) {
    const { mesaj, errors } = await hataMesaji(r);
    throw new ApiError(r.status, mesaj, errors);
  }
  return r;
}

export async function api(path, opts) {
  const r = await apiFetch(path, opts);
  if (r.status === 204) return null;
  return r.json();
}

// Content-Disposition'dan adla dosya indirir; yanit basliklarini doner
export async function dosyaIndir(path, { method = 'GET', body, varsayilanAd = 'dosya' } = {}) {
  const r = await apiFetch(path, { method, body });
  const blob = await r.blob();
  const cd = r.headers.get('Content-Disposition') || '';
  const ad = decodeURIComponent((cd.match(/filename="?([^"]+)"?/) || [])[1] || varsayilanAd);
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = ad; a.click();
  URL.revokeObjectURL(url);
  return r.headers;
}
