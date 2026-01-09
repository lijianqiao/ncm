import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
// 通用字体
import 'vfonts/Lato.css'
// 等宽字体
import 'vfonts/FiraCode.css'

import { permission } from './directives/permission'

const app = createApp(App)

app.use(createPinia())
app.use(router)
app.directive('permission', permission)

app.mount('#app')
