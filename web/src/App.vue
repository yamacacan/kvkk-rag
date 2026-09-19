<script setup>
import ProgressBar from './components/ProgressBar.vue';
import Toast from './components/Toast.vue';
import DialogKutusu from './components/DialogKutusu.vue';
</script>

<template>
  <ProgressBar />
  <router-view />
  <Toast />
  <DialogKutusu />
</template>
