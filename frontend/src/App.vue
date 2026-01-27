<script setup lang="ts">
import { computed } from 'vue'
import {
  NConfigProvider,
  NMessageProvider,
  NDialogProvider,
  NNotificationProvider,
  NGlobalStyle,
  zhCN,
  dateZhCN,
} from 'naive-ui'
import hljs from 'highlight.js/lib/core'
import javascript from 'highlight.js/lib/languages/javascript'
import json from 'highlight.js/lib/languages/json'
import GlobalAlerts from '@/components/common/GlobalAlerts.vue'
import { globalOtpFlow } from '@/composables/useOtpFlow'
import OtpModal from '@/components/common/OtpModal.vue'

hljs.registerLanguage('javascript', javascript)
hljs.registerLanguage('json', json)

// 使用 computed 确保正确的响应式追踪
const otpShow = computed(() => globalOtpFlow.show.value)
const otpLoading = computed(() => globalOtpFlow.loading.value)
const otpInfoItems = computed(() => globalOtpFlow.infoItems.value)
const otpAlertText = computed(() => globalOtpFlow.details.value?.message)
const otpErrorMessage = computed(() => globalOtpFlow.errorMessage.value)
</script>

<template>
  <n-config-provider :locale="zhCN" :date-locale="dateZhCN" :theme-overrides="{
    common: {
      primaryColor: '#6366f1',
      primaryColorHover: '#818cf8',
      primaryColorPressed: '#4f46e5',
      borderRadius: '8px',
    },
    Button: {
      borderRadiusMedium: '8px',
      fontWeight: '500',
    },
    Card: {
      borderRadius: '12px',
    },
    Input: {
      borderRadius: '8px',
    },
    Code: {
      // Adjust valid theme properties if needed or leave default
    },
  }" :hljs="hljs">
    <n-global-style />
    <!-- Keep providers for now, but Message/Notification might be deprecated if we replace all -->
    <n-message-provider>
      <n-dialog-provider>
        <n-notification-provider>
          <GlobalAlerts />
          <router-view />
          <!-- v-if 控制渲染，:show 始终为 true 避免动画竞态 -->
          <OtpModal v-if="otpShow" :show="true" :loading="otpLoading"
            :info-items="otpInfoItems" :alert-text="otpAlertText"
            :error-message="otpErrorMessage" @update:show="(v) => !v && globalOtpFlow.close()"
            @confirm="globalOtpFlow.confirm" @timeout="globalOtpFlow.handleTimeout" />
        </n-notification-provider>
      </n-dialog-provider>
    </n-message-provider>
  </n-config-provider>
</template>

<style scoped></style>
