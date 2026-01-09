<script setup lang="ts">
import { useRouter } from 'vue-router'
import { NResult, NButton } from 'naive-ui'

defineOptions({
  name: 'ServerError',
})

const router = useRouter()
</script>

<template>
  <div class="error-page">
    <n-result
      status="500"
      title="500 服务器错误"
      description="抱歉，服务器出现了一些问题，请稍后再试"
    >
      <template #footer>
        <n-button type="primary" @click="router.push('/')">返回首页</n-button>
      </template>
    </n-result>
  </div>
</template>

<style scoped>
.error-page {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100vh;
  background-color: #f8fafc;
}
</style>
