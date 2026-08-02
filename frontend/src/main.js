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
import System from './views/System.vue'
import Tools from './views/Tools.vue'
import './style.scss'

const routes = [
  { path: '/', redirect: '/chat' },
  { path: '/chat', component: Chat, meta: { title: '对话终端 · CHAT TERMINAL' } },
  { path: '/system', component: System, meta: { title: '系统控制台 · SYSTEM CONSOLE' } },
  { path: '/tools', component: Tools, meta: { title: '工具矩阵 · TOOL MATRIX' } },
  { path: '/memory', component: Memory, meta: { title: '数据档案 · DATA ARCHIVE' } },
  { path: '/persona', component: Persona, meta: { title: '人格配置 · PERSONA CONFIG' } },
  { path: '/greetings', component: Greetings, meta: { title: '问候日志 · GREETING LOG' } },
  { path: '/settings', component: Settings, meta: { title: 'LLM 接入 · LLM SETUP' } },
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
