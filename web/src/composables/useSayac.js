// Sayi animasyonu (count-up): hedef degisince ~900 ms'de yumusak artar.
import { ref, watch } from 'vue';

export function useSayac(hedef, sure = 900) {
  const deger = ref(0);
  const azaltilmis = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
  let cerceve = null;
  watch(hedef, (yeni) => {
    const son = Number(yeni) || 0;
    if (azaltilmis) { deger.value = son; return; }
    cancelAnimationFrame(cerceve);
    const bas = deger.value, t0 = performance.now();
    const adim = (t) => {
      const x = Math.min(1, (t - t0) / sure);
      const e = 1 - Math.pow(1 - x, 3); // ease-out cubic
      deger.value = Math.round(bas + (son - bas) * e);
      if (x < 1) cerceve = requestAnimationFrame(adim);
    };
    cerceve = requestAnimationFrame(adim);
    // rAF calismayan ortamlarda (gizli sekme) yine de hedefe otur
    setTimeout(() => { if (deger.value !== son) deger.value = son; }, sure + 200);
  }, { immediate: true });
  return deger;
}
