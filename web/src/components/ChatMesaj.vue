<script setup>
// Tek sohbet balonu. Asistan cevabi sinirli markdown'dan HTML'e cevrilir (kacislanmis),
// [dayanak] kunyeleri tiklaninca ayni mesajin kaynak kartina kaydirilir.
import { computed, ref } from 'vue';
import { cevapHtml, kaynakAnahtari, kunyeHedefi } from '../utils/cevap';
import { kisalt } from '../utils/format';

const props = defineProps({ mesaj: { type: Object, required: true } });
const emit = defineEmits(['envanter-ekle', 'kayit-ac', 'satir-guncelle', 'kayit-duzenle']);

const kullanici = computed(() => props.mesaj.role === 'user');
const html = computed(() => cevapHtml(props.mesaj.content));
const kaynaklar = computed(() => props.mesaj.sources || []);
const zorunluSayisi = computed(() => kaynaklar.value.filter((s) => (s.baglayicilik || '').startsWith('zorunlu')).length);
const anahtarlar = computed(() => kaynaklar.value.map(kaynakAnahtari));
const acik = ref(false);
const vurgu = ref(-1);
const kartlar = ref([]);

const oneri = computed(() => props.mesaj.envanter?.oneri || null);
const eslesen = computed(() => props.mesaj.envanter?.eslesen || []);
const guncelleme = computed(() => props.mesaj.envanter?.guncelleme || props.mesaj.veritabani?.guncelleme || null);
const dbSatirlar = computed(() => props.mesaj.veritabani?.satirlar || props.mesaj.envanter?.satirlar || []);

const guncelleniyor = ref(false);
const guncellendi = ref(false);

function kunyeTikla(e) {
  const el = e.target.closest('.kunye');
  if (!el) return;
  const i = kunyeHedefi(el.dataset.kunye, anahtarlar.value);
  if (i < 0) { el.title = 'Bu dayanak kaynak listesinde eşleşmedi'; return; }
  acik.value = true;
  requestAnimationFrame(() => {
    const k = kartlar.value[i];
    if (k) k.scrollIntoView({ behavior: 'smooth', block: 'center' });
    vurgu.value = i;
    setTimeout(() => { vurgu.value = -1; }, 2200);
  });
}

function uygula() {
  if (!guncelleme.value || guncelleniyor.value || guncellendi.value) return;
  guncelleniyor.value = true;
  emit('satir-guncelle', {
    satirNo: guncelleme.value.satir_no,
    yeniDegerler: guncelleme.value.yeni_degerler,
    tamam: () => {
      guncelleniyor.value = false;
      guncellendi.value = true;
    },
    hata: () => {
      guncelleniyor.value = false;
    }
  });
}
</script>

<template>
  <div class="flex" :class="kullanici ? 'justify-end' : 'justify-start'">
    <div class="px-4 py-3 text-sm leading-relaxed"
      :class="kullanici ? 'bg-indigo-600 text-white rounded-2xl rounded-br-sm max-w-[75%] whitespace-pre-wrap' : 'bg-[var(--bg-inset)] border border-[var(--line)] rounded-2xl rounded-bl-sm max-w-[92%]'">
      <template v-if="kullanici">{{ mesaj.content }}</template>
      <span v-else-if="mesaj.bekliyor" class="text-[var(--t2)]">Kaynaklar taranıyor ve cevap üretiliyor…</span>
      <span v-else-if="mesaj.hata" class="text-rose-400">Hata: {{ mesaj.hata }}</span>
      <template v-else>
        <div class="cevap-govde text-slate-200" v-html="html" @click="kunyeTikla"></div>

        <!-- Güncelleme Talebi ve Yetki/Kapsam Kartı -->
        <div v-if="guncelleme && guncelleme.istendi" class="mt-3 p-3.5 rounded-xl border"
          :class="guncelleme.yetkili ? 'bg-indigo-950/40 border-indigo-500/30' : 'bg-rose-950/30 border-rose-500/30'">
          <div class="flex items-center justify-between gap-2 mb-2">
            <div class="flex items-center gap-2">
              <span class="text-[10px] font-bold px-1.5 py-0.5 rounded uppercase"
                :class="guncelleme.yetkili ? 'bg-indigo-500/20 text-indigo-300' : 'bg-rose-500/20 text-rose-300'">
                {{ guncelleme.yetkili ? 'GÜNCELLEME ÖNERİSİ' : 'YETKİ YETERSİZ' }}
              </span>
              <span class="text-xs font-semibold text-white">Satır #{{ guncelleme.satir_no || '?' }}</span>
            </div>
            <span v-if="guncelleme.kapsam" class="text-[10px] px-2 py-0.5 rounded bg-[var(--bg-3)] border border-[var(--line)] text-[var(--t2)]">
              Kapsam: {{ guncelleme.kapsam }}
            </span>
          </div>

          <!-- Yetkili ise değişiklik diff'i ve aksiyonlar -->
          <template v-if="guncelleme.yetkili">
            <p class="text-[11px] text-[var(--t1)] mb-2">Veritabanında uygulanacak değişiklikler:</p>
            <div class="space-y-1.5 mb-3 bg-[var(--bg-2)] p-2.5 rounded-lg border border-[var(--line)]">
              <div v-for="(yeniVal, alan) in guncelleme.yeni_degerler" :key="alan" class="text-xs">
                <span class="font-medium text-slate-400 capitalize">{{ alan.replace('_', ' ') }}:</span>
                <span v-if="guncelleme.eski_degerler && guncelleme.eski_degerler[alan]" class="line-through text-rose-400/80 mx-1.5 text-[11px]">
                  {{ guncelleme.eski_degerler[alan] }}
                </span>
                <span class="text-emerald-400 font-semibold">{{ yeniVal }}</span>
              </div>
            </div>

            <div class="flex items-center gap-2">
              <button :disabled="guncelleniyor || guncellendi"
                class="px-3 py-1.5 text-xs font-bold rounded-lg transition-all flex items-center gap-1.5"
                :class="guncellendi ? 'bg-emerald-600 text-white' : 'bg-emerald-500 hover:bg-emerald-400 text-black disabled:opacity-50'"
                @click="uygula">
                <span v-if="guncellendi">✓ Güncellendi</span>
                <span v-else-if="guncelleniyor">Güncelleniyor…</span>
                <span v-else>Değişikliği Uygula</span>
              </button>
              <button class="px-3 py-1.5 text-xs font-semibold rounded-lg bg-[var(--bg-3)] border border-[var(--line)] text-slate-200 hover:text-white"
                @click="emit('kayit-duzenle', guncelleme.satir_no)">
                Formda Düzenle
              </button>
            </div>
          </template>

          <!-- Yetkisiz ise açıklama -->
          <template v-else>
            <p class="text-xs text-rose-200 leading-relaxed mb-1">{{ guncelleme.sebep }}</p>
            <p class="text-[10.5px] text-[var(--t2)]">Bu işlemi gerçekleştirebilmek için 'inventory.update' iznine ve ilgili departman/satır yetki kapsamına sahip olmanız gerekir.</p>
          </template>
        </div>

        <!-- Envanterde Var Kartı -->
        <div v-if="oneri && oneri.tip === 'envanterde_var'" class="mt-3 p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/25">
          <div class="flex items-center gap-2 mb-1.5">
            <span class="text-[10px] font-bold px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300">ENVANTER</span>
            <span class="text-[11px] font-semibold text-white">"{{ oneri.kisisel_veri }}" envanterde kayıtlı</span>
          </div>
          <div class="space-y-0.5">
            <div v-for="r in eslesen" :key="r.satir_no" class="text-[11px] text-slate-300 leading-snug">
              <span class="font-mono text-indigo-400">#{{ r.satir_no }}</span> {{ kisalt(r.kisisel_veri, 40) }}
              <span class="text-[var(--t2)]">· {{ kisalt(r.faaliyet, 40) }} · {{ kisalt(r.birim, 28) }}</span>
            </div>
          </div>
          <div class="flex gap-3 mt-2">
            <button v-if="eslesen[0]" class="text-[11px] font-semibold text-emerald-300 hover:text-white" @click="emit('kayit-ac', eslesen[0].satir_no)">Kaydı Aç →</button>
            <button v-if="eslesen[0]" class="text-[11px] font-semibold text-indigo-300 hover:text-white" @click="emit('kayit-duzenle', eslesen[0].satir_no)">Düzenle ✏️</button>
          </div>
        </div>

        <!-- Envantere Ekle Kartı -->
        <div v-else-if="oneri" class="mt-3 p-3 rounded-lg bg-amber-500/10 border border-amber-500/25">
          <div class="flex items-center gap-2 mb-1.5">
            <span class="text-[10px] font-bold px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300">ENVANTER</span>
            <span class="text-[11px] font-semibold text-white">"{{ oneri.kisisel_veri }}" envanterde birebir kayıtlı değil</span>
          </div>
          <template v-if="eslesen.length">
            <p class="text-[10.5px] text-[var(--t2)] mb-1">Yakın kayıtlar (aynı değil):</p>
            <div class="space-y-0.5 mb-2">
              <div v-for="r in eslesen" :key="r.satir_no" class="text-[11px] text-slate-300 leading-snug">
                <span class="font-mono text-indigo-400">#{{ r.satir_no }}</span> {{ kisalt(r.kisisel_veri, 40) }}
                <span class="text-[var(--t2)]">· {{ kisalt(r.faaliyet, 40) }} · {{ kisalt(r.birim, 28) }}</span>
              </div>
            </div>
          </template>
          <p class="text-[11px] text-slate-200 mb-2">Bu veriyi envantere eklemek ister misiniz? Alanlar mevzuat dayanağıyla önerilir, kaydetmeden önce gözden geçirirsiniz.</p>
          <button class="px-3 py-1.5 text-xs font-bold rounded-lg bg-amber-500 hover:bg-amber-400 text-black"
            @click="emit('envanter-ekle', { veri: oneri.kisisel_veri || '', birim: oneri.birim || '', faaliyet: oneri.faaliyet || '' })">Envantere ekle</button>
        </div>

        <!-- Eşleşen Canlı Veritabanı Kayıtları (Öneri veya Güncelleme yoksa) -->
        <div v-else-if="dbSatirlar.length && !guncelleme" class="mt-3 p-3 rounded-lg bg-indigo-500/10 border border-indigo-500/25">
          <div class="flex items-center justify-between gap-2 mb-1.5">
            <div class="flex items-center gap-1.5">
              <span class="text-[10px] font-bold px-1.5 py-0.5 rounded bg-indigo-500/20 text-indigo-300">GÜNCEL VERİTABANI</span>
              <span class="text-[11px] font-semibold text-white">{{ dbSatirlar.length }} kayıt bulundu</span>
            </div>
          </div>
          <div class="space-y-1">
            <div v-for="r in dbSatirlar.slice(0, 5)" :key="r.satir_no" class="text-[11px] text-slate-300 flex items-center justify-between py-0.5 border-b border-[var(--line)]/50 last:border-0">
              <div>
                <span class="font-mono text-indigo-400">#{{ r.satir_no }}</span> {{ kisalt(r.kisisel_veri, 35) }}
                <span class="text-[var(--t2)]">· {{ kisalt(r.birim, 20) }} · {{ kisalt(r.faaliyet, 25) }}</span>
              </div>
              <div class="flex items-center gap-2">
                <button class="text-[10.5px] text-indigo-300 hover:text-white" @click="emit('kayit-ac', r.satir_no)">Gör</button>
                <button class="text-[10.5px] text-emerald-400 hover:text-white" @click="emit('kayit-duzenle', r.satir_no)">Düzenle ✏️</button>
              </div>
            </div>
          </div>
        </div>

        <!-- Kaynaklar Accordion -->
        <details v-if="kaynaklar.length" class="mt-3 group" :open="acik" @toggle="acik = $event.target.open">
          <summary class="cursor-pointer text-[10.5px] font-semibold text-[var(--t2)] hover:text-white select-none">
            {{ kaynaklar.length }} kaynak · {{ zorunluSayisi }} zorunlu, {{ kaynaklar.length - zorunluSayisi }} tavsiye</summary>
          <div class="mt-2 rounded-lg border border-[var(--line)] divide-y divide-[var(--line)] bg-[var(--bg-2)]">
            <div v-for="(s, i) in kaynaklar" :key="i" :ref="(el) => (kartlar[i] = el)"
              class="px-3 py-2 hover:bg-[var(--bg-3)]/40 transition-colors" :class="vurgu === i ? 'kaynak-vurgu' : ''">
              <div class="flex items-center gap-2 mb-0.5">
                <span class="font-mono text-[10px] text-[var(--t2)]">[{{ i + 1 }}]</span>
                <span class="text-[10px] font-bold px-1.5 py-0.5 rounded border"
                  :class="(s.baglayicilik || '').startsWith('zorunlu') ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30' : 'bg-amber-500/15 text-amber-400 border-amber-500/30'">
                  {{ (s.baglayicilik || '').startsWith('zorunlu') ? 'ZORUNLU' : 'TAVSİYE' }}</span>
                <span class="text-[11px] font-semibold text-white">{{ kisalt(s.belge_adi, 58) }}</span>
                <span v-if="s.madde_no || s.karar_no" class="font-mono text-[10.5px] text-indigo-400">{{ s.madde_no ? 'm.' + s.madde_no : s.karar_no }}</span>
              </div>
              <p class="text-[11px] text-[var(--t1)] leading-snug">{{ kisalt(s.eslesen_parca || s.text, 220) }}</p>
            </div>
          </div>
        </details>
      </template>
    </div>
  </div>
</template>
