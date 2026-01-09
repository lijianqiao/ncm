<script setup lang="ts">
import { useRouter } from 'vue-router'
import { NResult, NButton } from 'naive-ui'

defineOptions({
  name: 'NotFound',
})

const router = useRouter()
</script>

<template>
  <div class="error-page">
    <n-result status="404" title="404 页面不存在" description="抱歉，您访问的页面不存在">
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
