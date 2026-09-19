<script setup>
// KVKK Uyum logosu (satır içi SVG). Renkler tema değişkenlerinden gelir: aydınlık temada
// mor gradyan, karanlık temada beyaz (style.css: --logo-*). Dosya yüklemez, önbellek sorunu
// yaşamaz; ayrı dosyalar (favicon vb.) src/public/assests/img/logo altındadır.
//   <Logo />        yalnızca işaret (kalkan + belge + tik)
//   <Logo tam />    işaret + KVKK UYUM yazısı
defineProps({ tam: { type: Boolean, default: false } });
</script>

<template>
  <svg xmlns="http://www.w3.org/2000/svg" :viewBox="tam ? '0 0 1024 1024' : '232 72 640 640'" role="img" aria-label="KVKK Uyum" class="logo">
    <defs>
      <linearGradient id="logoMor" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0%" stop-color="#7C4DFF" /><stop offset="100%" stop-color="#4B20B8" />
      </linearGradient>
    </defs>
    <path class="logo-ana" d="M300 145 L405 105 L405 190 L355 215 L355 375 C355 485 430 555 512 595 C545 579 576 562 602 540 L625 610 C590 638 552 660 512 680 C385 620 300 535 300 390 Z" />
    <path class="logo-ana" d="M405 105 H665 L760 200 V385 H690 V245 H610 V175 H475 V515 C455 500 430 480 405 450 Z" />
    <path class="logo-detay" d="M665 105 V200 H760 Z" />
    <circle class="logo-detay" cx="540" cy="260" r="38" />
    <path class="logo-detay" d="M470 345 C470 305 495 285 540 285 C585 285 610 305 610 345 C610 360 600 368 585 368 H495 C480 368 470 360 470 345 Z" />
    <rect class="logo-detay" x="470" y="405" width="170" height="24" rx="12" />
    <rect class="logo-detay" x="470" y="450" width="105" height="24" rx="12" />
    <circle class="logo-ana" cx="700" cy="500" r="105" />
    <path class="logo-tik" d="M650 500 L684 534 L754 462" fill="none" stroke-width="28" stroke-linecap="round" stroke-linejoin="round" />
    <template v-if="tam">
      <text class="logo-ana" x="512" y="805" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" font-size="142" font-weight="700" letter-spacing="2">KVKK</text>
      <text class="logo-uyum" x="512" y="895" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" font-size="68" font-weight="500" letter-spacing="30">UYUM</text>
    </template>
  </svg>
</template>
