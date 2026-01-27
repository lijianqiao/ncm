<script setup lang="ts">
import { computed, ref, watch, onBeforeUnmount } from 'vue'
import { NModal, NAlert, NFormItem, NInputOtp, NButton, NSpace, NDescriptions, NDescriptionsItem } from 'naive-ui'

defineOptions({
  name: 'OtpModal',
})

type InfoItem = {
  label: string
  value: string
}

const props = withDefaults(
  defineProps<{
    show: boolean
    title?: string
    loading?: boolean
    length?: number
    alertTitle?: string
    alertText?: string
    infoItems?: InfoItem[]
    maxInfoItems?: number
    errorMessage?: string
    confirmText?: string
  }>(),
  {
    title: '需要 OTP 验证码',
    loading: false,
    length: 6,
    alertTitle: '需要 OTP',
    alertText: '请输入当前有效的 OTP 验证码以继续操作。',
    infoItems: () => [],
    maxInfoItems: 3,
    confirmText: '确认',
    errorMessage: '',
  },
)

const emit = defineEmits<{
  (e: 'update:show', v: boolean): void
  (e: 'confirm', otpCode: string): void
}>()

const otpChars = ref<string[]>([])
const idleTimeoutMs = 60_000
const inactivityTimer = ref<ReturnType<typeof setTimeout> | null>(null)

const resetOtp = () => {
  otpChars.value = Array.from({ length: props.length }, () => '')
}

const clearInactivityTimer = () => {
  if (inactivityTimer.value) {
    clearTimeout(inactivityTimer.value)
    inactivityTimer.value = null
  }
}

const startInactivityTimer = () => {
  if (!props.show || props.loading) return
  clearInactivityTimer()
  inactivityTimer.value = setTimeout(() => {
    if (!props.loading && props.show) {
      emit('update:show', false)
    }
  }, idleTimeoutMs)
}

watch(
  () => props.show,
  (v) => {
    if (v) {
      resetOtp()
      startInactivityTimer()
    } else {
      clearInactivityTimer()
    }
  },
  { immediate: true },
)

// 当错误信息出现时，自动清空输入框，方便用户重新输入
watch(
  () => props.errorMessage,
  (newVal) => {
    if (newVal) {
      resetOtp()
      startInactivityTimer()
    }
  }
)

watch(
  () => otpChars.value.join(''),
  () => {
    startInactivityTimer()
  }
)

watch(
  () => props.loading,
  (v) => {
    if (v) {
      clearInactivityTimer()
    } else {
      startInactivityTimer()
    }
  }
)

onBeforeUnmount(() => {
  clearInactivityTimer()
})

const otpCode = computed(() => otpChars.value.join('').trim())
const visibleInfoItems = computed(() => props.infoItems.slice(0, props.maxInfoItems))
const hiddenInfoCount = computed(() => Math.max(0, props.infoItems.length - props.maxInfoItems))

const close = () => {
  if (props.loading) return
  emit('update:show', false)
}

const submit = () => {
  if (props.loading) return
  if (otpCode.value.length !== props.length) return
  emit('confirm', otpCode.value)
}
</script>

<template>
  <n-modal :show="show" preset="card" :title="title" style="width: 480px; z-index: 2001;" :closable="!loading"
    :mask-closable="!loading" @update:show="(v) => emit('update:show', v)">
    <n-space vertical size="large">
      <n-alert type="warning" :title="alertTitle" :show-icon="false">
        {{ alertText }}
      </n-alert>

      <n-descriptions v-if="infoItems.length" :column="1" label-placement="left" bordered>
        <n-descriptions-item v-for="item in visibleInfoItems" :key="item.label" :label="item.label">
          {{ item.value }}
        </n-descriptions-item>
        <n-descriptions-item v-if="hiddenInfoCount > 0" label="更多">
          … 还有 {{ hiddenInfoCount }} 项
        </n-descriptions-item>
      </n-descriptions>

      <n-form-item label="OTP 验证码" required :validation-status="errorMessage ? 'error' : undefined"
        :feedback="errorMessage">
        <div style="width: 100%; display: flex; justify-content: center">
          <n-input-otp v-model:value="otpChars" :length="length" :disabled="loading" @finish="submit" />
        </div>
      </n-form-item>

      <n-space justify="end">
        <n-button :disabled="loading" @click="close">取消</n-button>
        <n-button type="primary" :loading="loading" :disabled="otpCode.length !== length" @click="submit">
          {{ confirmText }}
        </n-button>
      </n-space>
    </n-space>
  </n-modal>
</template>
