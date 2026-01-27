<script setup lang="ts">
import { h, ref, computed, onMounted } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import {
  NIcon,
  type MenuOption,
  NBreadcrumb,
  NBreadcrumbItem,
  NDropdown,
  NModal,
  NForm,
  NFormItem,
  NInput,
  NButton,
  NSelect,
  NDescriptions,
  NDescriptionsItem,
  NTag,
  NTabs,
  NTabPane,
} from 'naive-ui'
import * as Ionicons from '@vicons/ionicons5'
import {
  PersonCircleOutline as UserIcon,
  LogOutOutline as LogoutIcon,
  PersonOutline as ProfileIcon,
  LockClosedOutline as PasswordIcon,
  PersonCircleOutline,
  LockClosedOutline,
  KeyOutline,
  MailOutline,
  PhonePortraitOutline,
  TransgenderOutline,
  PersonOutline,
  CalendarOutline,
  BriefcaseOutline,
  PulseOutline,
} from '@vicons/ionicons5'
import { useUserStore } from '@/stores/user'
import type { Menu } from '@/api/menus'
import { updateCurrentUser, changePassword } from '@/api/auth'
import { $alert } from '@/utils/alert'
import { formatDateTime } from '@/utils/date'

defineOptions({
  name: 'MainLayout',
})

const userStore = useUserStore()
const route = useRoute()
const router = useRouter()
const siteTitle = import.meta.env.VITE_SITE_TITLE || 'Admin RBAC'

// 动态分辨率的图标图
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const iconsMap = Ionicons as Record<string, any>

function renderIcon(iconName: string | null) {
  if (!iconName) return undefined
  // 尝试找到完全匹配
  let icon = iconsMap[iconName]
  // 后备：如果找不到，请尝试附加“大纲”（常见模式）
  if (!icon && !iconName.endsWith('Outline')) {
    icon = iconsMap[`${iconName}Outline`]
  }
  if (!icon) return undefined
  return () => h(NIcon, null, { default: () => h(icon) })
}

// 将后端菜单数据转换为 Naive UI MenuOption
function transformMenuToOption(menu: Menu): MenuOption {
  // 如果未显式返回类型，则根据子项的存在进行推断。
  const hasChildren = menu.children && menu.children.length > 0
  const normalizedType = menu.type ? menu.type.toUpperCase() : 'MENU'

  //如果没有子节点且不是目录，则为叶子（链接）。
  //如果它有子菜单，那么它是一个子菜单（组）并且不应该是一个链接。
  const isLeaf = !hasChildren && normalizedType !== 'CATALOG'
  const routeName = menu.name

  const label = isLeaf
    ? () =>
        h(
          RouterLink,
          {
            to: { name: routeName },
          },
          { default: () => menu.title },
        )
    : menu.title

  const option: MenuOption = {
    label: label,
    key: isLeaf ? routeName : menu.id, // 如果是叶，则使用路由名称作为活动状态映射的键，否则使用 ID
    icon: renderIcon(menu.icon),
  }

  if (menu.children && menu.children.length > 0) {
    option.children = menu.children.map(transformMenuToOption)
  }

  return option
}

// 计算菜单选项
const menuOptions = computed(() => {
  return userStore.userMenus.map(transformMenuToOption)
})

const collapsed = ref(false)

const handleLogout = () => {
  userStore.logout()
}

const userDropdownOptions = [
  {
    label: '个人信息',
    key: 'profile',
    icon: () => h(NIcon, null, { default: () => h(ProfileIcon) }),
  },
  {
    label: '修改密码',
    key: 'change-password',
    icon: () => h(NIcon, null, { default: () => h(PasswordIcon) }),
  },
  {
    label: '退出登录',
    key: 'logout',
    icon: () => h(NIcon, null, { default: () => h(LogoutIcon) }),
  },
]

const handleUserDropdownSelect = (key: string) => {
  if (key === 'logout') {
    handleLogout()
  }
  if (key === 'profile') {
    handleOpenProfile()
  }
  if (key === 'change-password') {
    handleOpenChangePassword()
  }
}

const activeKey = computed(() => {
  return route.name as string
})

const breadcrumbs = computed(() => {
  return route.matched.filter((r) => r.meta && r.meta.title).map((r) => r.meta.title as string)
})

// === 用户配置文件逻辑 ===
const showProfileModal = ref(false)
const profileLoading = ref(false)
const displayUsername = computed(() => {
  return userStore.userInfo?.nickname || userStore.userInfo?.username || '用户'
})

const profileModel = ref({
  nickname: '',
  email: '',
  phone: '',
  gender: '保密',
})

const handleOpenProfile = () => {
  const user = userStore.userInfo
  if (user) {
    profileModel.value = {
      nickname: user.nickname || '',
      email: user.email || '',
      phone: user.phone || '',
      gender: user.gender || '保密',
    }
    showProfileModal.value = true
  }
}

const handleUpdateProfile = async () => {
  profileLoading.value = true
  try {
    await updateCurrentUser(profileModel.value)
    $alert.success('更新成功')
    await userStore.fetchUserInfo() // 刷新
    showProfileModal.value = false
  } catch {
    // 错误由全局拦截器处理
  } finally {
    profileLoading.value = false
  }
}

// === 更改密码逻辑 ===
const showPasswordModal = ref(false)
const passwordLoading = ref(false)
const passwordModel = ref({
  old_password: '',
  new_password: '',
  confirm_password: '',
})

const handleOpenChangePassword = () => {
  passwordModel.value = {
    old_password: '',
    new_password: '',
    confirm_password: '',
  }
  showPasswordModal.value = true
}

const handleChangePassword = async () => {
  if (!passwordModel.value.old_password || !passwordModel.value.new_password) {
    $alert.warning('请填写完整')
    return
  }
  if (passwordModel.value.new_password !== passwordModel.value.confirm_password) {
    $alert.warning('两次新密码不一致')
    return
  }
  passwordLoading.value = true
  try {
    await changePassword({
      old_password: passwordModel.value.old_password,
      new_password: passwordModel.value.new_password,
    })
    $alert.success('密码修改成功，请重新登录')
    showPasswordModal.value = false
    userStore.logout()
  } catch {
    // 错误由全局拦截器处理
  } finally {
    passwordLoading.value = false
  }
}

onMounted(() => {
  if (userStore.userMenus.length === 0) {
    userStore.fetchUserMenus()
  }
})
</script>

<template>
  <n-layout has-sider position="absolute">
    <n-layout-sider
      bordered
      collapse-mode="width"
      :collapsed-width="64"
      :width="240"
      :collapsed="collapsed"
      show-trigger
      @collapse="collapsed = true"
      @expand="collapsed = false"
      class="sidebar"
    >
      <div class="logo" @click="router.push('/')" style="cursor: pointer">
        <div class="logo-icon">A</div>
        <span v-if="!collapsed" class="logo-title">{{ siteTitle }}</span>
      </div>
      <n-menu
        :collapsed="collapsed"
        :collapsed-width="64"
        :collapsed-icon-size="22"
        :options="menuOptions"
        :value="activeKey"
      />
    </n-layout-sider>

    <n-layout class="main-content">
      <n-layout-header bordered class="header">
        <div class="header-left">
          <n-breadcrumb>
            <n-breadcrumb-item>
              <router-link to="/">首页</router-link>
            </n-breadcrumb-item>
            <n-breadcrumb-item v-for="item in breadcrumbs" :key="item">
              {{ item }}
            </n-breadcrumb-item>
          </n-breadcrumb>
        </div>

        <div class="header-right">
          <n-dropdown :options="userDropdownOptions" @select="handleUserDropdownSelect">
            <div class="user-profile">
              <n-icon size="20" :component="UserIcon" />
              <span class="username">{{ displayUsername }}</span>
            </div>
          </n-dropdown>
        </div>
      </n-layout-header>

      <n-layout-content
        content-style="padding: 24px; min-height: calc(100vh - 64px); background-color: #f8fafc;"
      >
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component v-if="Component" :is="Component" :key="route.fullPath" />
            <div v-else />
          </transition>
        </router-view>
      </n-layout-content>
    </n-layout>

    <!-- 轮廓模态 -->
    <n-modal v-model:show="showProfileModal" preset="card" title="个人信息" style="width: 600px">
      <n-tabs type="line" animated>
        <n-tab-pane name="info" tab="基本信息">
          <n-descriptions bordered label-placement="left" :column="1">
            <n-descriptions-item>
              <template #label>
                <n-icon
                  :component="PersonCircleOutline"
                  style="margin-right: 4px; vertical-align: -2px"
                />
                用户名
              </template>
              {{ userStore.userInfo?.username }}
            </n-descriptions-item>
            <n-descriptions-item>
              <template #label>
                <n-icon
                  :component="PersonOutline"
                  style="margin-right: 4px; vertical-align: -2px"
                />
                昵称
              </template>
              {{ userStore.userInfo?.nickname || '未设置' }}
            </n-descriptions-item>
            <n-descriptions-item>
              <template #label>
                <n-icon
                  :component="PhonePortraitOutline"
                  style="margin-right: 4px; vertical-align: -2px"
                />
                手机号
              </template>
              {{ userStore.userInfo?.phone || '未设置' }}
            </n-descriptions-item>
            <n-descriptions-item>
              <template #label>
                <n-icon :component="MailOutline" style="margin-right: 4px; vertical-align: -2px" />
                邮箱
              </template>
              {{ userStore.userInfo?.email || '未设置' }}
            </n-descriptions-item>
            <n-descriptions-item>
              <template #label>
                <n-icon
                  :component="TransgenderOutline"
                  style="margin-right: 4px; vertical-align: -2px"
                />
                性别
              </template>
              {{ userStore.userInfo?.gender || '未设置' }}
            </n-descriptions-item>
            <n-descriptions-item>
              <template #label>
                <n-icon :component="PulseOutline" style="margin-right: 4px; vertical-align: -2px" />
                状态
              </template>
              <n-tag :type="userStore.userInfo?.is_active ? 'success' : 'error'">
                {{ userStore.userInfo?.is_active ? '启用' : '停用' }}
              </n-tag>
            </n-descriptions-item>
            <n-descriptions-item>
              <template #label>
                <n-icon
                  :component="CalendarOutline"
                  style="margin-right: 4px; vertical-align: -2px"
                />
                注册时间
              </template>
              {{ formatDateTime(userStore.userInfo?.created_at || '') }}
            </n-descriptions-item>
            <n-descriptions-item>
              <template #label>
                <n-icon
                  :component="BriefcaseOutline"
                  style="margin-right: 4px; vertical-align: -2px"
                />
                角色
              </template>
              {{ userStore.userInfo?.roles?.length ? '已分配' : '无角色' }}
            </n-descriptions-item>
          </n-descriptions>
        </n-tab-pane>
        <n-tab-pane name="edit" tab="修改资料">
          <n-form
            ref="profileFormRef"
            :model="profileModel"
            label-placement="left"
            label-width="80"
          >
            <n-form-item label="昵称" path="nickname">
              <n-input v-model:value="profileModel.nickname" placeholder="请输入昵称">
                <template #prefix>
                  <n-icon :component="PersonOutline" />
                </template>
              </n-input>
            </n-form-item>
            <n-form-item label="手机号" path="phone">
              <n-input v-model:value="profileModel.phone" placeholder="请输入手机号">
                <template #prefix>
                  <n-icon :component="PhonePortraitOutline" />
                </template>
              </n-input>
            </n-form-item>
            <n-form-item label="邮箱" path="email">
              <n-input v-model:value="profileModel.email" placeholder="请输入邮箱">
                <template #prefix>
                  <n-icon :component="MailOutline" />
                </template>
              </n-input>
            </n-form-item>
            <n-form-item label="性别" path="gender">
              <n-select
                v-model:value="profileModel.gender"
                :options="[
                  { label: '男', value: '男' },
                  { label: '女', value: '女' },
                  { label: '保密', value: '保密' },
                ]"
              />
            </n-form-item>
            <div style="display: flex; justify-content: flex-end">
              <n-button type="primary" :loading="profileLoading" @click="handleUpdateProfile">
                保存修改
              </n-button>
            </div>
          </n-form>
        </n-tab-pane>
      </n-tabs>
    </n-modal>

    <!-- 更改密码模式 -->
    <n-modal v-model:show="showPasswordModal" preset="card" title="修改密码" style="width: 500px">
      <n-form :model="passwordModel" label-placement="left" label-width="100">
        <n-form-item label="旧密码" path="old_password" required>
          <n-input
            v-model:value="passwordModel.old_password"
            type="password"
            show-password-on="click"
            placeholder="请输入旧密码"
          >
            <template #prefix>
              <n-icon :component="KeyOutline" />
            </template>
          </n-input>
        </n-form-item>
        <n-form-item label="新密码" path="new_password" required>
          <n-input
            v-model:value="passwordModel.new_password"
            type="password"
            show-password-on="click"
            placeholder="请输入新密码"
          >
            <template #prefix>
              <n-icon :component="LockClosedOutline" />
            </template>
          </n-input>
        </n-form-item>
        <n-form-item label="确认新密码" path="confirm_password" required>
          <n-input
            v-model:value="passwordModel.confirm_password"
            type="password"
            show-password-on="click"
            placeholder="请再次输入新密码"
          >
            <template #prefix>
              <n-icon :component="LockClosedOutline" />
            </template>
          </n-input>
        </n-form-item>
        <div style="display: flex; justify-content: flex-end; gap: 12px">
          <n-button @click="showPasswordModal = false">取消</n-button>
          <n-button type="primary" :loading="passwordLoading" @click="handleChangePassword">
            确认修改
          </n-button>
        </div>
      </n-form>
    </n-modal>
  </n-layout>
</template>

<style scoped>
.sidebar {
  box-shadow: 2px 0 8px rgba(0, 0, 0, 0.05);
  z-index: 10;
}

.logo {
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: white;
  border-bottom: 1px solid #eee;
  overflow: hidden;
  gap: 12px;
}

.logo-icon {
  width: 32px;
  height: 32px;
  background: linear-gradient(135deg, #6366f1, #a855f7);
  color: white;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  font-size: 18px;
  flex-shrink: 0;
}

.logo-title {
  font-size: 18px;
  font-weight: 700;
  color: #333;
  white-space: nowrap;
}

.header {
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  background: white;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03);
}

.user-profile {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  padding: 6px 12px;
  border-radius: 6px;
  transition: background-color 0.2s;
}

.user-profile:hover {
  background-color: #f1f5f9;
}

.username {
  font-size: 14px;
  font-weight: 500;
}

/* 过渡 */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
