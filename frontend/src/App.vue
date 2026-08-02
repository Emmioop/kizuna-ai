<template>
  <div class="shell">
    <!-- 顶部 HUD 装饰条 -->
    <div class="hud-top">
      <div class="hud-line left"></div>
      <div class="hud-line right"></div>
    </div>

    <!-- 侧边栏 -->
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-logo">
          <div class="arc-reactor"></div>
        </div>
        <div>
          <div class="brand-title">J.A.R.V.I.S.</div>
          <div class="brand-sub">Just A Rather Very Intelligent System</div>
        </div>
      </div>

      <nav>
        <router-link to="/chat" class="nav-item">
          <el-icon><ChatDotRound /></el-icon><span>对话终端</span>
        </router-link>
        <router-link to="/system" class="nav-item">
          <el-icon><Monitor /></el-icon><span>系统控制台</span>
        </router-link>
        <router-link to="/tools" class="nav-item">
          <el-icon><SetUp /></el-icon><span>工具矩阵</span>
        </router-link>
        <router-link to="/memory" class="nav-item">
          <el-icon><Collection /></el-icon><span>数据档案</span>
        </router-link>
        <router-link to="/persona" class="nav-item">
          <el-icon><User /></el-icon><span>人格配置</span>
        </router-link>
        <router-link to="/greetings" class="nav-item">
          <el-icon><Bell /></el-icon><span>问候日志</span>
        </router-link>
        <router-link to="/settings" class="nav-item">
          <el-icon><Setting /></el-icon><span>LLM 接入</span>
        </router-link>
      </nav>

      <div class="status-card jarvis-card" v-if="persona">
        <div class="card-title">
          <span class="dot live"></span> 系统状态
        </div>
        <div class="status-row">
          <span>主人信任度</span>
          <el-progress :percentage="persona.affection" :show-text="false" :stroke-width="8"
            :color="trustColor(persona.affection)"/>
          <em>{{ persona.affection.toFixed(0) }}<small>/100</small></em>
        </div>
        <div class="status-row">
          <span>稳定度</span>
          <el-progress :percentage="persona.mood" :show-text="false" :stroke-width="8"
            :color="stabilityColor(persona.mood)"/>
          <em>{{ persona.mood.toFixed(0) }}<small>/100</small></em>
        </div>
        <div class="status-hint">{{ persona.mood_reason }}</div>
        <div class="status-meta">
          指令 <b>{{ persona.total_chats }}</b> 次 · 最后 {{ lastChatText }}</div>
        <el-button size="small" @click="reloadPersona" style="margin-top:8px;width:100%;">
            刷新状态
          </el-button>
      </div>
    </aside>

    <!-- 主内容 -->
    <main class="main">
      <header class="topbar">
        <div class="top-title">
          <span class="corner lt"></span>
          <span class="corner rt"></span>
          {{ (route.meta && route.meta.title) || '系统控制台' }}
          <span class="corner lb"></span>
          <span class="corner rb"></span>
        </div>
        <div class="top-right">
          <el-tag v-if="health?.llm_initialized" class="hud-tag ok" effect="dark">
            <span class="dot ok"></span>
            {{ health?.llm_provider }} · {{ health?.llm_model }}
          </el-tag>
          <el-tag v-else class="hud-tag err" effect="dark">
            <span class="dot err"></span>
            LLM 未接入
          </el-tag>
          <span class="sys-clock">{{ clockText }}</span>
        </div>
      </header>
      <section class="content">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" :persona="persona" @persona-updated="reloadPersona" />
          </transition>
        </router-view>
      </section>
    </main>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, computed } from 'vue'
import { useRoute } from 'vue-router'
import axios from 'axios'
import { ElMessage } from 'element-plus'

const route = useRoute()
const persona = ref(null)
const health = ref(null)
const clockText = ref('')

let clockTimer = null

const lastChatText = computed(() => {
  if (!persona.value || !persona.value.last_chat_at) return '从未'
  const d = new Date(persona.value.last_chat_at)
  const diff = Math.floor((Date.now() - d.getTime()) / 86400000)
  if (diff <= 0) return '今日'
  return diff + ' 天前'
})

function trustColor(v) {
  if (v >= 80) return '#00ffaa'
  if (v >= 50) return '#3fd5ff'
  if (v >= 30) return '#ffca3a'
  return '#ff4757'
}
function stabilityColor(v) {
  if (v >= 80) return '#00ffaa'
  if (v >= 55) return '#3fd5ff'
  if (v >= 30) return '#ffca3a'
  return '#ff4757'
}

function tick() {
  const d = new Date()
  const p = n => String(n).padStart(2, '0')
  clockText.value = `${d.getFullYear()}-${p(d.getMonth()+1)}-${p(d.getDate())}  ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
}

async function reloadHealth() {
  try {
    health.value = (await axios.get('/api/health')).data
  } catch (e) {
    health.value = { ok: false, llm_initialized: false }
  }
}

async function reloadPersona() {
  try {
    persona.value = (await axios.get('/api/persona')).data
  } catch (e) {
    ElMessage.error('加载人格失败: ' + (e.response?.data?.detail || e.message))
  }
  await reloadHealth()
}

onMounted(() => {
  tick()
  clockTimer = setInterval(tick, 1000)
  reloadPersona()
})
onBeforeUnmount(() => clockTimer && clearInterval(clockTimer))
defineExpose({ reloadPersona })
</script>

<style scoped lang="scss">
.shell {
  display: grid;
  grid-template-columns: 260px 1fr;
  height: 100vh;
  position: relative;
  background: var(--bg);
  color: var(--text);
}
/* 顶部 HUD 装饰线 */
.hud-top {
  position: absolute; left: 0; right: 0; top: 0; height: 6px; z-index: 20;
  display: flex; justify-content: space-between; pointer-events: none;
}
.hud-line {
  width: 30%; height: 2px;
  background: linear-gradient(90deg, transparent, var(--accent), var(--accent-2));
  box-shadow: 0 0 8px var(--accent);
  opacity: 0.75;
}
.hud-line.right { transform: scaleX(-1); }

.sidebar {
  background: linear-gradient(180deg, #06101e, #030a15);
  border-right: 1px solid var(--border);
  display: flex; flex-direction: column;
  overflow-y: auto; overflow-x: hidden;
  position: relative;
  box-shadow: inset -2px 0 30px rgba(63, 213, 255, 0.04);
}
.sidebar::before {
  content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 2px;
  background: linear-gradient(180deg, var(--accent), transparent 60%);
  opacity: 0.6;
}

.brand {
  padding: 22px 18px 18px;
  display: flex; gap: 12px; align-items: center;
  border-bottom: 1px solid var(--border);
  position: relative;
}
.brand-logo {
  width: 44px; height: 44px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  background: radial-gradient(circle at 50% 50%, rgba(63,213,255,0.25), transparent 70%);
}
/* 电弧反应堆动画光圈 */
.arc-reactor {
  width: 28px; height: 28px; border-radius: 50%;
  background: radial-gradient(circle, #fff 0%, var(--accent) 28%, var(--accent-2) 60%, transparent 70%);
  box-shadow:
    0 0 10px var(--accent), 0 0 22px var(--accent-2);
  animation: pulse 2.6s ease-in-out infinite;
}
@keyframes pulse {
  0%,100% { opacity: 0.9; transform: scale(1); }
  50% { opacity: 1; transform: scale(1.06); }
}
.brand-title {
  font-size: 18px; font-weight: 700;
  color: var(--accent);
  letter-spacing: 0.12em;
  text-shadow: 0 0 10px rgba(63,213,255,0.5);
}
.brand-sub {
  font-size: 10px;
  color: var(--text-dim);
  margin-top: 2px;
  letter-spacing: 0.04em;
}

nav { padding: 10px 10px; display: flex; flex-direction: column; gap: 2px; flex: 1; }
.nav-item {
  display: flex; align-items: center; gap: 10px;
  padding: 10px 12px; border-radius: 4px;
  color: var(--text-soft);
  text-decoration: none; font-size: 13.5px;
  letter-spacing: 0.04em;
  transition: all 0.15s ease;
  border-left: 2px solid transparent;
  .el-icon { font-size: 16px; }
}
.nav-item:hover {
  background: rgba(63, 213, 255, 0.06);
  color: var(--accent);
  border-left-color: rgba(63,213,255,0.5);
}
.nav-item.router-link-active {
  background: linear-gradient(90deg, rgba(63,213,255,0.12), transparent);
  color: var(--accent);
  border-left: 2px solid var(--accent);
  box-shadow: inset 0 0 14px rgba(63,213,255,0.06);
}

/* 贾维斯状态栏 */
.jarvis-card {
  margin: 14px; padding: 14px;
  border: 1px solid var(--border);
  border-radius: 4px;
  background: linear-gradient(180deg, rgba(11,26,46,0.6), #081828);
  position: relative;
  overflow: hidden;
}
.jarvis-card::before {
  content: "";
  position: absolute; inset: 0;
  background:
    linear-gradient(135deg, transparent 0 49.5%, var(--accent) 49.5% 50.5%, transparent 50.5%) 0 0 / 14px 14px;
  opacity: 0.04;
  pointer-events: none;
}
.card-title {
  font-size: 12px;
  color: var(--text-soft);
  letter-spacing: 0.12em;
  margin-bottom: 10px;
  display: flex; align-items: center; gap: 6px;
}
.dot {
  display: inline-block; width: 8px; height: 8px; border-radius: 50%;
}
.dot.live { background: var(--accent-3); box-shadow: 0 0 6px var(--accent-3); animation: blink 1.4s ease-in-out infinite; }
.dot.ok { background: var(--accent-3); }
.dot.err { background: var(--accent-danger); }
@keyframes blink { 50% { opacity: 0.35; } }
.status-row {
  display: grid;
  grid-template-columns: 70px 1fr 58px;
  gap: 8px; align-items: center;
  font-size: 11.5px; color: var(--text-soft);
  margin-bottom: 8px;
  em {
    font-size: 12px;
    color: var(--accent);
    text-align: right;
    font-style: normal;
    font-weight: 600;
    small { color: var(--text-dim); font-weight: 400; margin-left: 1px; font-size: 10px; }
  }
}
.status-hint {
  font-size: 11px;
  color: var(--text-dim);
  margin: 6px 0 4px;
  line-height: 1.5;
}
.status-meta {
  font-size: 10px; color: var(--text-dim);
  b { color: var(--accent); font-weight: 600; }
}

.main { display: flex; flex-direction: column; overflow: hidden; position: relative; }
.topbar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 20px;
  border-bottom: 1px solid var(--border);
  background: linear-gradient(180deg, rgba(6,16,30,0.95), #040c18);
  position: relative;
}
.top-title {
  position: relative;
  font-size: 14px;
  color: var(--accent);
  font-weight: 600;
  letter-spacing: 0.18em;
  padding: 6px 16px;
  text-transform: uppercase;
}
.top-title .corner {
  position: absolute; width: 8px; height: 8px; border: 1px solid var(--accent);
  opacity: 0.85;
}
.top-title .corner.lt { left: 0; top: 0; border-right: none; border-bottom: none; }
.top-title .corner.rt { right: 0; top: 0; border-left: none; border-bottom: none; }
.top-title .corner.lb { left: 0; bottom: 0; border-right: none; border-top: none; }
.top-title .corner.rb { right: 0; bottom: 0; border-left: none; border-top: none; }

.top-right { display: flex; align-items: center; gap: 14px; }
.hud-tag {
  background: transparent !important;
  border: 1px solid var(--accent) !important;
  color: var(--text) !important;
  display: inline-flex !important;
  align-items: center !important;
  gap: 6px;
  padding: 4px 10px !important;
  border-radius: 2px !important;
  font-size: 11.5px !important;
  letter-spacing: 0.04em;
}
.hud-tag.ok { border-color: var(--accent-3) !important; }
.hud-tag.err { border-color: var(--accent-danger) !important; }

.sys-clock {
  font-family: "SF Mono", Menlo, Consolas, monospace;
  font-size: 12px;
  color: var(--accent);
  letter-spacing: 0.08em;
  padding: 4px 10px;
  border: 1px dashed rgba(63,213,255,0.25);
  border-radius: 2px;
  background: rgba(63,213,255,0.04);
}

.content {
  flex: 1;
  overflow-y: auto;
  padding: 18px 22px;
  position: relative;
}
.content::before {
  content: "";
  position: absolute;
  right: 22px; top: 18px;
  width: 60px; height: 60px;
  border-right: 1px solid rgba(63,213,255,0.15);
  border-top: 1px solid rgba(63,213,255,0.15);
  pointer-events: none;
}
.content::after {
  content: "";
  position: absolute;
  left: 22px; bottom: 18px;
  width: 60px; height: 60px;
  border-left: 1px solid rgba(63,213,255,0.15);
  border-bottom: 1px solid rgba(63,213,255,0.15);
  pointer-events: none;
}

.fade-enter-active, .fade-leave-active { transition: opacity 0.25s ease, transform 0.25s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; transform: translateY(6px); }

@media (max-width: 900px) {
  .shell { grid-template-columns: 64px 1fr; }
  .brand-title, .brand-sub, .nav-item span { display: none; }
  .jarvis-card { display: none; }
  .nav-item { justify-content: center; }
}
</style>
