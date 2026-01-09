<template>
  <div class="error-page">
    <div class="error-code">403</div>
    <div class="error-desc">抱歉，您无权访问该页面</div>
    <div class="error-handle">
      <router-link to="/">
        <n-button type="primary" size="large">返回首页</n-button>
      </router-link>
    </div>
  </div>
</template>

<script lang="ts" setup>
import { NButton } from 'naive-ui'

defineOptions({
  name: 'ForbiddenError',
})
</script>

<style scoped>
.error-page {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100vh;
  box-sizing: border-box;
}
.error-code {
  line-height: 1;
  font-size: 250px;
  font-weight: bolder;
  color: #f02d2d;
}
.error-desc {
  font-size: 30px;
  color: #777;
}
.error-handle {
  margin-top: 30px;
  padding-bottom: 200px;
}
</style>
