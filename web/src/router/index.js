import { createRouter, createWebHistory } from 'vue-router';
import { useAuthStore } from '../stores/auth';
import { useUiStore } from '../stores/ui';
import { gunluk as gunlukApi } from '../api';

// meta.requiresAuth: oturum; meta.permission: Spatie izni (backend'de de ayni izin
// rota basina denetlenir — buradaki kontrol yalnizca arayuz akisi icindir).
// meta.kirinti: header'daki breadcrumb; meta.grup: sidebar grubu (moduller | yonetim)
const uygulama = [
  { path: '', name: 'panel', component: () => import('../views/PanelView.vue'),
    meta: { baslik: 'Panel', kirinti: ['Genel Bakış', 'Panel'] } },
  { path: 'envanter', name: 'envanter', component: () => import('../views/EnvanterView.vue'),
    meta: { permission: 'inventory.view', baslik: 'Veri Envanteri', kirinti: ['Denetim', 'Veri Envanteri'] } },
  { path: 'bulgular', name: 'bulgular', component: () => import('../views/EnvanterView.vue'),
    props: { mod: 'bulgular' }, meta: { permission: 'findings.view', baslik: 'Uyum Bulguları', kirinti: ['Denetim', 'Uyum Bulguları'] } },
  { path: 'asistan', name: 'asistan', component: () => import('../views/AsistanView.vue'),
    meta: { permission: 'chat.use', baslik: 'Mevzuat Asistanı', kirinti: ['Denetim', 'Mevzuat Asistanı'] } },
  { path: 'belgeler', name: 'belgeler', component: () => import('../views/BelgelerView.vue'),
    meta: { permission: 'documents.view', baslik: 'Kurumsal Belgeler', kirinti: ['Uyum Belgeleri', 'Kurumsal Belgeler'] } },
  { path: 'faaliyet-belgeleri', name: 'faaliyet-belgeleri', component: () => import('../views/FaaliyetBelgeleriView.vue'),
    meta: { permission: 'documents.view', baslik: 'Faaliyet Belgeleri', kirinti: ['Uyum Belgeleri', 'Faaliyet Belgeleri'] } },
  { path: 'acik-riza', name: 'acik-riza', component: () => import('../views/AcikRizaView.vue'),
    meta: { permission: 'consents.view', baslik: 'Açık Rıza Kayıtları', kirinti: ['Denetim', 'Açık Rıza Kayıtları'] } },
  { path: 'graf', name: 'graf', component: () => import('../views/GrafView.vue'),
    meta: { permission: 'graph.view', baslik: 'Bilgi Grafiği', kirinti: ['Denetim', 'Bilgi Grafiği'] } },
  { path: 'profil', name: 'profil', component: () => import('../views/ProfilView.vue'),
    meta: { baslik: 'Profilim', kirinti: ['Hesap', 'Profilim'] } },
  { path: 'bildirimler', name: 'bildirimler', component: () => import('../views/BildirimlerView.vue'),
    meta: { baslik: 'Bildirimler', kirinti: ['Hesap', 'Bildirimler'] } },
  // ---- yonetim ----
  { path: 'yonetim/kullanicilar', name: 'kullanicilar', component: () => import('../views/yonetim/KullanicilarView.vue'),
    meta: { permission: 'users.view', baslik: 'Kullanıcılar', kirinti: ['Yönetim', 'Kullanıcılar'] } },
  { path: 'yonetim/roller', name: 'roller', component: () => import('../views/yonetim/RollerView.vue'),
    meta: { permission: 'roles.view', baslik: 'Roller & İzinler', kirinti: ['Yönetim', 'Erişim & Kimlik', 'Roller & Yetkilendirme'] } },
  { path: 'yonetim/birimler', name: 'birimler', component: () => import('../views/yonetim/BirimlerView.vue'),
    meta: { permission: 'departments.view', baslik: 'Birimler', kirinti: ['Yönetim', 'Birimler'] } },
  { path: 'yonetim/kurum-profili', name: 'kurum-profili', component: () => import('../views/yonetim/KurumProfiliView.vue'),
    meta: { permission: 'profile.view', baslik: 'Kurum Profili', kirinti: ['Yönetim', 'Kurum Profili'] } },
  { path: 'yonetim/gunluk', name: 'gunluk', component: () => import('../views/yonetim/GunlukView.vue'),
    meta: { permission: 'audit.view', baslik: 'Denetim Günlüğü', kirinti: ['Yönetim', 'Denetim Günlüğü'] } },
  { path: 'yetki-yok', name: 'yetki-yok', component: () => import('../views/YetkiYokView.vue'),
    meta: { baslik: 'Yetki Yok', kirinti: ['Yetki Yok'] } },
];

const routes = [
  { path: '/', component: () => import('../layouts/AppLayout.vue'), meta: { requiresAuth: true }, children: uygulama },
  {
    path: '/',
    component: () => import('../layouts/AuthLayout.vue'),
    meta: { guest: true },
    children: [
      { path: 'login', name: 'login', component: () => import('../views/auth/LoginView.vue') },
      { path: 'sifremi-unuttum', name: 'sifremi-unuttum', component: () => import('../views/auth/ForgotPasswordView.vue') },
      { path: 'sifre-sifirla', name: 'sifre-sifirla', component: () => import('../views/auth/ResetPasswordView.vue') },
    ],
  },
  { path: '/:pathMatch(.*)*', redirect: '/' },
];

const router = createRouter({ history: createWebHistory(), routes });

// Kullanicinin girebilecegi ilk sayfa: panel herkese acik
export function ilkSayfa() {
  return { name: 'panel' };
}

router.beforeEach(async (to) => {
  useUiStore().gecis = true; // tembel yuklenen sayfa parcasi + guard'lar surdukce ilerleme cubugu
  const auth = useAuthStore();
  if (to.matched.some((m) => m.meta.requiresAuth)) {
    if (!auth.isAuthenticated && (auth.accessToken || auth.refreshToken)) await auth.restore();
    else if (auth.isAuthenticated && !auth.dogrulandi) await auth.restore();
    if (!auth.isAuthenticated) return { name: 'login', query: to.fullPath !== '/' ? { redirect: to.fullPath } : {} };
    if (to.meta.permission && !auth.can(to.meta.permission)) return { name: 'yetki-yok', query: { izin: to.meta.permission } };
  }
  if (to.matched.some((m) => m.meta.guest) && auth.isAuthenticated && to.name === 'login') {
    return ilkSayfa(auth);
  }
  return true;
});

router.afterEach((to, from) => {
  useUiStore().gecis = false;
  document.title = (to.meta.baslik ? to.meta.baslik + ' — ' : '') + 'KVKK Uyum';
  // Sayfa goruntulemesi denetim gunlugune (page.view): yalnizca oturumlu uygulama sayfalari,
  // ayni sayfada sorgu degisimi sayilmaz; hata sessizce yutulur (gezinmeyi engellemez).
  const auth = useAuthStore();
  if (auth.isAuthenticated && to.matched.some((m) => m.meta.requiresAuth) && to.name !== 'yetki-yok' && to.path !== from.path) {
    gunlukApi.sayfaGoruntule({ path: to.path, name: String(to.name || ''), title: to.meta.baslik || '' }).catch(() => {});
  }
});
router.onError(() => { useUiStore().gecis = false; });

export default router;
