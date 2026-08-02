import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { createRouter, createWebHashHistory } from 'vue-router'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import axios from 'axios'
import { ElMessage } from 'element-plus'

import App from './App.vue'
import Chat from './views/Chat.vue'
import Memory from './views/Memory.vue'
import Persona from './views/Persona.vue'
import Settings from './views/Settings.vue'
import Greetings from './views/Greetings.vue'
import System from './views/System.vue'
import Tools from './views/Tools.vue'
import './style.scss'

// ================================================================
// 🛠 后端地址解析：支持 GitHub Pages 托管前端 + 自建后端（Cloudflare Tunnel 等）
// ================================================================
const LS_KEY_BACKEND = 'jarvis.backend_url'

/**
 * 读取/写入后端地址。优先级：
 *   1. localStorage 用户手动填写的地址
 *   2. 当前主机是 localhost/127.0.0.1/192.168/10./172.16~31 → 默认 /api (相对，走当前 host:8000)
 *   3. 其他主机（GitHub Pages / 公网静态托管）→ 空字符串，提示用户去设置页填写
 */
export function getBackendBase() {
  const saved = localStorage.getItem(LS_KEY_BACKEND)
  if (saved) {
    // 去掉末尾斜杠，避免重复拼接
    return saved.replace(/\/+$/, '')
  }
  const host = window.location.hostname
  const isLocalHost = (
    host === 'localhost' ||
    host === '127.0.0.1' ||
    host.startsWith('192.168.') ||
    host.startsWith('10.') ||
    /^172\.(1[6-9]|2\d|3[01])\./.test(host)
  )
  return isLocalHost ? '' : ''
}

export function setBackendBase(url) {
  const clean = (url || '').trim().replace(/\/+$/, '')
  if (!clean) {
    localStorage.removeItem(LS_KEY_BACKEND)
  } else {
    localStorage.setItem(LS_KEY_BACKEND, clean)
  }
  axios.defaults.baseURL = clean || ''
}

// 初始化 axios
axios.defaults.timeout = 120000 // LLM 慢，2 分钟超时
axios.defaults.baseURL = getBackendBase() || ''

// 统一拦截 401 / 网络错误 → 提醒用户后端地址
axios.interceptors.response.use(
  r => r,
  err => {
    const msg = err.message || ''
    const status = err.response?.status
    const url = err.config?.url || ''
    if (
      !window.__jarvis_network_error_shown__ && (
        msg.includes('Network Error') ||
        /Failed to fetch|net::ERR_CONNECTION|timed out|timeout/i.test(msg) ||
        status === 0
      )
    ) {
      const host = window.location.hostname
      if (!host.startsWith('127.0.0.1') && host !== 'localhost' && !host.startsWith('192.168.')) {
        window.__jarvis_network_error_shown__ = true
        setTimeout(() => { window.__jarvis_network_error_shown__ = false }, 20000)
        ElMessage({
          type: 'warning',
          duration: 12000,
          message: '⚠ 连不上贾维斯后端。若你正在使用 GitHub Pages，请先到「LLM 接入」填写后端地址（Cloudflare Tunnel 的 https://xxx.trycloudflare.com 公网地址）。',
          showClose: true,
        })
      }
    }
    return Promise.reject(err)
  },
)

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

router.afterEach(to => {
  if (to.meta?.title) document.title = String(to.meta.title) + ' · JARVIS'
})

const app = createApp(App)
for (const [k, v] of Object.entries(ElementPlusIconsVue)) app.component(k, v)
app.use(ElementPlus, { locale: zhCn })
app.use(createPinia())
app.use(router)
app.mount('#app')
