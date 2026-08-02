import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { createRouter, createWebHashHistory } from 'vue-router'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import zhCn from 'element-plus/es/locale/lang/zh-cn'

import App from './App.vue'
import Chat from './views/Chat.vue'
import Memory from './views/Memory.vue'
import Persona from './views/Persona.vue'
import Settings from './views/Settings.vue'
import Greetings from './views/Greetings.vue'
import './style.scss'

const routes = [
  { path: '/', redirect: '/chat' },
  { path: '/chat', component: Chat, meta: { title: '聊天' } },
  { path: '/memory', component: Memory, meta: { title: '记忆' } },
  { path: '/persona', component: Persona, meta: { title: '人格' } },
  { path: '/greetings', component: Greetings, meta: { title: '问候' } },
  { path: '/settings', component: Settings, meta: { title: '设置' } },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

const app = createApp(App)
for (const [k, v] of Object.entries(ElementPlusIconsVue)) app.component(k, v)
app.use(ElementPlus, { locale: zhCn })
app.use(createPinia())
app.use(router)
app.mount('#app')
