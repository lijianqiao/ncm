<script setup lang="ts">
import { computed, ref, watch } from 'vue'
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
    confirmText?: string
  }>(),
  {
    title: '需要 OTP 验证码',
    loading: false,
    length: 6,
    alertTitle: '需要 OTP',
    alertText: '请输入当前有效的 OTP 验证码以继续操作。',
    infoItems: () => [],
    confirmText: '确认',
  },
)

const emit = defineEmits<{
  (e: 'update:show', v: boolean): void
  (e: 'confirm', otpCode: string): void
}>()

const otpChars = ref<string[]>([])

const resetOtp = () => {
  otpChars.value = Array.from({ length: props.length }, () => '')
}

watch(
  () => props.show,
  (v) => {
    if (v) resetOtp()
  },
  { immediate: true },
)

const otpCode = computed(() => otpChars.value.join('').trim())

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
  <n-modal
    :show="show"
    preset="card"
    :title="title"
    style="width: 480px"
    :closable="!loading"
    :mask-closable="!loading"
    @update:show="(v) => emit('update:show', v)"
  >
    <n-space vertical size="large">
      <n-alert type="warning" :title="alertTitle" :show-icon="false">
        {{ alertText }}
      </n-alert>

      <n-descriptions v-if="infoItems.length" :column="1" label-placement="left" bordered>
        <n-descriptions-item v-for="item in infoItems" :key="item.label" :label="item.label">
          {{ item.value }}
        </n-descriptions-item>
      </n-descriptions>

      <n-form-item label="OTP 验证码" required>
        <div style="width: 100%; display: flex; justify-content: center">
          <n-input-otp
            v-model:value="otpChars"
            :length="length"
            :disabled="loading"
            @finish="submit"
          />
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
