<script setup>
// Gecmis tarayicida tutulur; sunucu her turda tam gecmisi alir (durumsuz API).
import { computed, nextTick, onMounted, ref } from 'vue';
import { asistan as asistanApi, envanter as envApi } from '../api';
import { useAuthStore } from '../stores/auth';
import ChatMesaj from '../components/ChatMesaj.vue';
import EnvanterForm from '../components/EnvanterForm.vue';

const auth = useAuthStore();
const ORNEKLER = [
  'Çalışanların parmak izi ile mesai takibi yapabilir miyim?',
  'Bana gelen başvuruyu kaç gün içinde cevaplamalıyım?',
  'İK olarak adayların referans kişilerinin telefon numarasını almayı planlıyoruz',
  'Pazarlama birimimiz müşterilerin doğum tarihini kampanya için kaydediyor, uygun mu?',
];

const mesajlar = ref([]);
const girdi = ref('');
const bekliyor = ref(false);
const kutu = ref(null);
const girdiEl = ref(null);
const form = ref(null); // {mevcut, onDoldur}

// Güncel Veritabanı Çekmecesi State
const veritabaniAc = ref(false);
const dbSatirlar = ref([]);
const dbYukleniyor = ref(false);
const dbArama = ref('');

const goruntulemeKapsami = computed(() => auth.scope('inventory', 'view') || 'Tüm Kurum');
const guncellemeKapsami = computed(() => auth.scope('inventory', 'update') || 'none');
const filtreliDbSatirlar = computed(() => {
  const q = dbArama.value.trim().toLowerCase();
  if (!q) return dbSatirlar.value;
  return dbSatirlar.value.filter((r) => {
    return (r.kisisel_veri || '').toLowerCase().includes(q) ||
           (r.birim || '').toLowerCase().includes(q) ||
           (r.faaliyet || '').toLowerCase().includes(q) ||
           (r.hukuki_sebep || '').toLowerCase().includes(q) ||
           String(r.satir_no).includes(q);
  });
});

async function veritabaniYukle() {
  if (!auth.can('inventory.view')) return;
  dbYukleniyor.value = true;
  try {
    const res = await envApi.liste({ limit: 300 });
    dbSatirlar.value = res.satirlar || [];
  } catch (e) {
    console.error('Veritabanı yüklenemedi:', e);
  } finally {
    dbYukleniyor.value = false;
  }
}

onMounted(() => {
  if (auth.can('inventory.view')) {
    veritabaniYukle();
  }
});

async function kaydir() { await nextTick(); if (kutu.value) kutu.value.scrollTop = kutu.value.scrollHeight; }

function girdiBoyut() {
  const t = girdiEl.value; if (!t) return;
  t.style.height = 'auto'; t.style.height = Math.min(t.scrollHeight, 160) + 'px';
}

async function gonder(metin) {
  metin = (metin ?? girdi.value).trim();
  if (!metin || bekliyor.value) return;
  bekliyor.value = true;
  mesajlar.value.push({ role: 'user', content: metin });
  mesajlar.value.push({ role: 'assistant', content: '', bekliyor: true });
  girdi.value = ''; await nextTick(); girdiBoyut(); kaydir();
  try {
    const gecmis = mesajlar.value.filter((m) => !m.bekliyor && !m.hata).map((m) => ({ role: m.role, content: m.content }));
    const d = await asistanApi.sohbet(gecmis, 10);
    mesajlar.value[mesajlar.value.length - 1] = {
      role: 'assistant',
      content: d.answer,
      sources: d.sources,
      envanter: d.envanter,
      veritabani: d.veritabani,
    };
  } catch (e) {
    mesajlar.value[mesajlar.value.length - 1] = { role: 'assistant', content: '', hata: e.message };
  } finally {
    bekliyor.value = false; kaydir(); girdiEl.value?.focus();
  }
}

function yeniSohbet() { mesajlar.value = []; girdiEl.value?.focus(); }

async function kayitAc(satirNo) {
  try { form.value = { mevcut: (await envApi.getir(satirNo)).satir, onDoldur: null }; }
  catch (e) { alert('Kayıt açılamadı: ' + e.message); }
}

async function kayitDuzenle(satirNoOrObj) {
  if (!auth.can('inventory.update')) {
    alert("Envanter satırı güncelleme yetkiniz ('inventory.update') bulunmuyor.");
    return;
  }
  try {
    const satir = typeof satirNoOrObj === 'object' && satirNoOrObj !== null
      ? satirNoOrObj
      : (await envApi.getir(satirNoOrObj)).satir;
    form.value = { mevcut: satir, onDoldur: null };
  } catch (e) {
    alert('Kayıt açılamadı: ' + e.message);
  }
}

async function chatSatirGuncelle({ satirNo, yeniDegerler, tamam, hata }) {
  if (!auth.can('inventory.update')) {
    alert("Envanter satırı güncelleme yetkiniz ('inventory.update') bulunmuyor.");
    if (hata) hata();
    return;
  }
  try {
    await envApi.guncelle(satirNo, yeniDegerler);
    await veritabaniYukle();
    if (tamam) tamam();
  } catch (e) {
    alert('Güncelleme başarısız: ' + (e.message || e));
    if (hata) hata();
  }
}

function envanterEkle(onDoldur) {
  if (!auth.can('inventory.create')) { alert('Envantere kayıt ekleme yetkiniz yok.'); return; }
  form.value = { mevcut: null, onDoldur };
}

function satiriSoraAktar(satir) {
  girdi.value = `Satır #${satir.satir_no} (${satir.kisisel_veri} - ${satir.birim}) kaydının hukuki sebebini ve mevzuata uygunluğunu değerlendirir misin?`;
  nextTick(() => {
    girdiBoyut();
    girdiEl.value?.focus();
  });
}
</script>

<template>
  <section class="relative">
    <!-- Üst Başlık ve Butonlar -->
    <div class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-4">
      <div>
        <h1 class="text-2xl font-extrabold text-white tracking-tight sm:text-3xl mb-1">Mevzuat Asistanı</h1>
        <p class="text-xs text-[var(--t1)]">
          Sohbet ederek sorun; cevaplar mevzuata ve kurumunuzun güncel veri tabanına dayanır.
        </p>
      </div>
      <div class="flex items-center gap-2 self-stretch sm:self-auto">
        <button
          v-if="auth.can('inventory.view')"
          class="px-3 py-1.5 text-xs font-semibold rounded-lg border transition-colors flex items-center gap-2"
          :class="veritabaniAc ? 'bg-indigo-600 text-white border-indigo-500 shadow-md shadow-indigo-600/30' : 'bg-[var(--bg-3)] border-[var(--line)] text-[var(--t1)] hover:text-white'"
          @click="veritabaniAc = !veritabaniAc">
          <span>🗄️ Güncel Veritabanı</span>
          <span v-if="dbSatirlar.length" class="px-1.5 py-0.5 rounded-full text-[10px] bg-indigo-500/30 text-indigo-200 font-mono">
            {{ dbSatirlar.length }}
          </span>
        </button>
        <button
          class="px-3 py-1.5 text-xs font-semibold rounded-lg bg-[var(--bg-3)] border border-[var(--line)] text-[var(--t1)] hover:text-white"
          @click="yeniSohbet">
          Yeni sohbet
        </button>
      </div>
    </div>

    <!-- Ana Alan: Sohbet Penceresi ve Yan Yana / Açılır Veritabanı Paneli -->
    <div class="grid grid-cols-1 transition-all duration-300 gap-4" :class="veritabaniAc ? 'lg:grid-cols-12' : 'grid-cols-1'">
      <!-- Sohbet Kutusu -->
      <div
        class="rounded-2xl border border-[var(--line)] bg-[var(--bg-2)] flex flex-col transition-all duration-300"
        :class="veritabaniAc ? 'lg:col-span-7' : 'col-span-1'"
        style="height: calc(100vh - 190px); min-height: 500px;">
        
        <div ref="kutu" class="flex-1 overflow-y-auto p-5 space-y-4">
          <div v-if="!mesajlar.length" class="h-full flex flex-col items-center justify-center text-center">
            <p class="text-sm font-semibold text-white mb-1">Ne sormak istersiniz?</p>
            <p class="text-[11px] text-[var(--t2)] mb-4 max-w-md">
              Mevzuatla ilgili soru sorabilir, kurum veritabanındaki kayıtları inceleyebilir veya yetkiniz dahilinde satır güncelleme talep edebilirsiniz.
            </p>
            <div class="flex flex-wrap justify-center gap-1.5 max-w-2xl">
              <button
                v-for="s in ORNEKLER"
                :key="s"
                class="px-2.5 py-1 rounded-md text-[11px] bg-[var(--bg-3)] border border-[var(--line)] text-[var(--t1)] hover:text-white hover:border-indigo-500 transition-colors"
                @click="gonder(s)">
                {{ s }}
              </button>
            </div>
          </div>
          <ChatMesaj
            v-for="(m, i) in mesajlar"
            :key="i"
            :mesaj="m"
            @kayit-ac="kayitAc"
            @kayit-duzenle="kayitDuzenle"
            @satir-guncelle="chatSatirGuncelle"
            @envanter-ekle="envanterEkle" />
        </div>

        <div class="border-t border-[var(--line)] p-3 bg-[var(--bg-1)]/60 rounded-b-2xl">
          <div class="flex gap-2 items-end">
            <textarea
              ref="girdiEl"
              v-model="girdi"
              rows="1"
              placeholder="Mesaj yazın… (Enter gönderir, Shift+Enter yeni satır)"
              class="flex-1 resize-none bg-[var(--bg-inset)] border border-[var(--line)] rounded-lg px-3 py-2.5 text-sm text-white placeholder-[var(--t2)] focus:outline-none focus:border-indigo-500 max-h-40"
              @input="girdiBoyut"
              @keydown.enter.exact.prevent="gonder()"></textarea>
            <button
              :disabled="bekliyor"
              class="px-5 py-2.5 text-sm font-bold rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white shadow-lg shadow-indigo-600/30 whitespace-nowrap"
              @click="gonder()">
              Gönder
            </button>
          </div>
        </div>
      </div>

      <!-- Güncel Veritabanı Çekmecesi / Yan Panel -->
      <div
        v-if="veritabaniAc"
        class="lg:col-span-5 rounded-2xl border border-[var(--line)] bg-[var(--bg-2)] flex flex-col overflow-hidden animate-fadeIn"
        style="height: calc(100vh - 190px); min-height: 500px;">
        
        <!-- Panel Başlığı -->
        <div class="p-3.5 border-b border-[var(--line)] bg-[var(--bg-1)]/80 flex items-center justify-between">
          <div class="flex items-center gap-2">
            <span class="text-sm font-bold text-white">Güncel Veritabanı</span>
            <span class="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
              Kapsam: {{ goruntulemeKapsami }}
            </span>
          </div>
          <div class="flex items-center gap-2">
            <button
              class="text-xs text-[var(--t2)] hover:text-white px-2 py-1 rounded hover:bg-[var(--bg-3)]"
              title="Yenile"
              @click="veritabaniYukle">
              🔄
            </button>
            <button
              class="text-xs text-[var(--t2)] hover:text-white px-2 py-1 rounded hover:bg-[var(--bg-3)]"
              @click="veritabaniAc = false">
              ✕
            </button>
          </div>
        </div>

        <!-- Arama Kutusu -->
        <div class="p-3 border-b border-[var(--line)] bg-[var(--bg-inset)]">
          <input
            v-model="dbArama"
            type="text"
            placeholder="Kişisel veri, birim, faaliyet veya satır no ara…"
            class="w-full bg-[var(--bg-2)] border border-[var(--line)] rounded-lg px-3 py-1.5 text-xs text-white placeholder-[var(--t2)] focus:outline-none focus:border-indigo-500" />
        </div>

        <!-- Kayıt Listesi -->
        <div class="flex-1 overflow-y-auto p-3 space-y-2">
          <div v-if="dbYukleniyor" class="py-12 text-center text-xs text-[var(--t2)]">
            Veritabanı kayıtları yükleniyor…
          </div>
          <div v-else-if="!filtreliDbSatirlar.length" class="py-12 text-center text-xs text-[var(--t2)]">
            Eşleşen envanter kaydı bulunamadı.
          </div>
          <div
            v-for="satir in filtreliDbSatirlar"
            :key="satir.satir_no"
            class="p-3 rounded-xl bg-[var(--bg-inset)] border border-[var(--line)] hover:border-indigo-500/40 transition-all text-xs">
            <div class="flex items-start justify-between gap-2 mb-1.5">
              <div class="flex items-center gap-1.5">
                <span class="font-mono text-indigo-400 font-bold">#{{ satir.satir_no }}</span>
                <span class="font-semibold text-white">{{ satir.kisisel_veri }}</span>
              </div>
              <span v-if="satir.veri_kategorisi" class="text-[10px] px-1.5 py-0.5 rounded bg-[var(--bg-3)] text-slate-300">
                {{ satir.veri_kategorisi }}
              </span>
            </div>

            <div class="text-[11px] text-[var(--t1)] space-y-0.5 mb-2.5">
              <div><span class="text-slate-400">Birim:</span> {{ satir.birim }} · <span class="text-slate-400">Faaliyet:</span> {{ satir.faaliyet }}</div>
              <div><span class="text-slate-400">Hukuki Sebep:</span> {{ satir.hukuki_sebep || '—' }}</div>
              <div><span class="text-slate-400">Saklama:</span> {{ satir.saklama_suresi || '—' }}</div>
            </div>

            <div class="flex items-center justify-between pt-2 border-t border-[var(--line)]/50">
              <button
                class="text-[11px] font-semibold text-indigo-400 hover:text-indigo-300 flex items-center gap-1"
                @click="satiriSoraAktar(satir)">
                <span>💬 Soru Sor</span>
              </button>
              <div class="flex items-center gap-2">
                <button
                  class="text-[11px] text-slate-300 hover:text-white"
                  @click="kayitAc(satir.satir_no)">
                  Detay
                </button>
                <button
                  v-if="auth.can('inventory.update')"
                  class="px-2 py-0.5 text-[11px] font-semibold rounded bg-emerald-500/15 text-emerald-400 hover:bg-emerald-500/25 border border-emerald-500/30"
                  @click="kayitDuzenle(satir)">
                  Düzenle ✏️
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- Panel Alt Bilgi -->
        <div class="p-2.5 border-t border-[var(--line)] bg-[var(--bg-1)]/60 text-[11px] text-[var(--t2)] flex items-center justify-between">
          <span>Toplam {{ filtreliDbSatirlar.length }} kayıt listeleniyor</span>
          <span v-if="auth.can('inventory.update')" class="text-emerald-400">Düzenleme Yetkisi Aktif</span>
        </div>
      </div>
    </div>

    <!-- Kayıt Düzenleme / Ekleme Modalı -->
    <EnvanterForm
      v-if="form"
      :mevcut="form.mevcut"
      :on-doldur="form.onDoldur"
      @kaydedildi="veritabaniYukle"
      @kapat="form = null" />
  </section>
</template>
