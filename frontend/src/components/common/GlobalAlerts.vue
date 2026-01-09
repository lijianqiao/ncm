<script setup lang="ts">
import { useAlertStore } from '@/stores/alert'
import { storeToRefs } from 'pinia'

const alertStore = useAlertStore()
const { alerts } = storeToRefs(alertStore)

const handleClose = (id: string) => {
  alertStore.remove(id)
}
</script>

<template>
  <div class="global-alerts-container">
    <transition-group name="alert-list">
      <div v-for="alert in alerts" :key="alert.id" class="alert-wrapper">
        <n-alert
          :type="alert.type"
          :title="alert.title"
          :closable="alert.closable"
          @close="handleClose(alert.id)"
          class="global-alert-item"
        >
          {{ alert.content }}
        </n-alert>
      </div>
    </transition-group>
  </div>
</template>

<style scoped>
.global-alerts-container {
  position: fixed;
  top: 20px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 9999;
  display: flex;
  flex-direction: column;
  gap: 10px;
  pointer-events: none; /* Allow clicks to pass through container */
  width: 90%;
  max-width: 400px;
}

.alert-wrapper {
  pointer-events: auto; /* Re-enable clicks for alerts */
  width: 100%;
}

.global-alert-item {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

/* Transition Styles */
.alert-list-enter-active,
.alert-list-leave-active {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.alert-list-enter-from,
.alert-list-leave-to {
  opacity: 0;
  transform: translateY(-20px);
}
</style>
