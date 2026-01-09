<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { NIcon } from 'naive-ui'
import { PersonOutline, LockClosedOutline } from '@vicons/ionicons5'
import { $alert } from '@/utils/alert'
import { login } from '@/api/auth'
import { useUserStore } from '@/stores/user'

defineOptions({
  name: 'LoginPage',
})

const router = useRouter()
const userStore = useUserStore()

const siteTitle = import.meta.env.VITE_SITE_TITLE || 'Admin RBAC'
const siteCopyright =
  import.meta.env.VITE_SITE_COPYRIGHT || '© 2025 Admin RBAC. All Rights Reserved.'

const formRef = ref()
const model = ref({
  username: '',
  password: '',
})

const rules = {
  username: {
    required: true,
    message: '请输入用户名',
    trigger: 'blur',
  },
  password: {
    required: true,
    message: '请输入密码',
    trigger: 'blur',
  },
}

const loading = ref(false)

const handleLogin = async (e: Event) => {
  e.preventDefault()
  formRef.value?.validate(async (errors: unknown) => {
    if (!errors) {
      loading.value = true
      try {
        // login() 已正确返回 LoginResult 类型
        const res = await login(model.value)
        // 直接使用类型安全的属性访问
        userStore.setToken(res.access_token)

        $alert.success('登录成功')
        router.push('/')
      } catch {
        // 错误已由 request.ts 统一处理和显示
      } finally {
        loading.value = false
      }
    }
  })
}
</script>

<template>
  <div class="login-container">
    <div class="login-box">
      <div class="header">
        <h2 class="title">{{ siteTitle }}</h2>
        <p class="subtitle">欢迎回来，请登录您的账户</p>
      </div>

      <n-form ref="formRef" :model="model" :rules="rules" size="large" :show-label="false">
        <n-form-item path="username">
          <n-input
            v-model:value="model.username"
            placeholder="用户名"
            @keydown.enter.prevent="handleLogin"
          >
            <template #prefix>
              <n-icon size="18" color="#808695"><PersonOutline /></n-icon>
            </template>
          </n-input>
        </n-form-item>
        <n-form-item path="password">
          <n-input
            v-model:value="model.password"
            type="password"
            show-password-on="click"
            placeholder="密码"
            @keydown.enter.prevent="handleLogin"
          >
            <template #prefix>
              <n-icon size="18" color="#808695"><LockClosedOutline /></n-icon>
            </template>
          </n-input>
        </n-form-item>
        <n-button
          type="primary"
          block
          :loading="loading"
          attr-type="submit"
          @click="handleLogin"
          class="login-btn"
        >
          登录
        </n-button>
      </n-form>
    </div>
    <div class="footer-copyright">{{ siteCopyright }}</div>
  </div>
</template>

<style scoped>
.login-container {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  height: 100vh;
  width: 100vw;
  background-color: #f0f2f5;
  background-image: url("data:image/svg+xml,%3Csvg width='20' height='20' viewBox='0 0 20 20' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='%239C92AC' fill-opacity='0.05' fill-rule='evenodd'%3E%3Ccircle cx='3' cy='3' r='3'/%3E%3Ccircle cx='13' cy='13' r='3'/%3E%3C/g%3E%3C/svg%3E");
}

.login-box {
  width: 360px;
  padding: 40px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08);
}

.header {
  text-align: center;
  margin-bottom: 30px;
}

.title {
  font-size: 24px;
  font-weight: 600;
  color: #1f2937;
  margin-bottom: 8px;
}

.subtitle {
  font-size: 14px;
  color: #6b7280;
  margin: 0;
}

.login-btn {
  font-weight: 500;
}

.footer-copyright {
  margin-top: 40px;
  font-size: 12px;
  color: #9ca3af;
}
</style>
