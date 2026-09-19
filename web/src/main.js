import { createApp } from 'vue';
import { createPinia } from 'pinia';
import App from './App.vue';
import router from './router';
import { FontAwesomeIcon } from './plugins/fontawesome';
import './style.css';

import { useUiStore } from './stores/ui';

const pinia = createPinia();
createApp(App).component('FaIcon', FontAwesomeIcon).use(pinia).use(router).mount('#app');

// Tema: kayitli tercihi uygula; "system" seciliyse isletim sistemi degisimini izle
const ui = useUiStore(pinia);
ui.temaUygula();
window.matchMedia?.('(prefers-color-scheme: light)').addEventListener?.('change', () => { if (ui.tema === 'system') ui.temaUygula(); });
