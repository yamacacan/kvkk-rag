<script setup>
defineProps({ modelValue: Boolean, disabled: Boolean, etiket: String });
const emit = defineEmits(['update:modelValue']);
</script>

<template>
  <button type="button" role="switch" :aria-checked="modelValue" :disabled="disabled" :title="etiket"
    class="anahtar" :class="modelValue ? 'acik' : ''" @click="emit('update:modelValue', !modelValue)"></button>
</template>
