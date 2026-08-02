<template>
  <div class="shell">
    <!-- 侧边栏 -->
    <aside class="sidebar">
      <div class="brand">
        <span class="brand-emoji">🌙</span>
        <div>
          <div class="brand-title">羁绊 AI</div>
          <div class="brand-sub">Kizuna · 只属于你</div>
        </div>
      </div>

      <nav>
        <router-link to="/chat" class="nav-item">
          <el-icon><ChatDotRound /></el-icon><span>聊天</span>
        </router-link>
        <router-link to="/memory" class="nav-item">
          <el-icon><Collection /></el-icon><span>记忆</span>
        </router-link>
        <router-link to="/persona" class="nav-item">
          <el-icon><User /></el-icon><span>人格设置</span>
        </router-link>
        <router-link to="/greetings" class="nav-item">
          <el-icon><Bell /></el-icon><span>问候</span>
        </router-link>
        <router-link to="/settings" class="nav-item">
          <el-icon><Setting /></el-icon><span>LLM 设置</span>
        </router-link>
      </nav>

      <div class="status-card" v-if="persona">
        <div class="status-row"><span>好感</span>
          <el-progress :percentage="persona.affection" :show-text="false" :stroke-width="10" color="#e57373"/>
          <em>{{ persona.affection.toFixed(0) }}/100</em>
        </div>
        <div class="status-row"><span>心情</span>
          <el-progress :percentage="persona.mood" :show-text="false" :stroke-width="10" color="#79d279"/>
          <em>{{ persona.mood.toFixed(0) }}/100</em>
        </div>
        <div class="status-hint">{{ persona.mood_reason }}</div>
        <div class="status-meta">对话 {{ persona.total_chats }} 次 · 上次 {{ lastChatText }}</div>
        <el-button size="small" type="warning" plain @click="reloadPersona" style="margin-top:8px;width:100%;">刷新</el-button>
      </div>
    </aside>

    <!-- 主内容 -->
    <main class="main">
      <header class="topbar">
        <div class="top-title">{{ (route.meta && route.meta.title) || '羁绊 AI' }}</div>
        <div class="top-right">
          <el-tag v-if="health?.llm_initialized" type="success" effect="dark">
            {{ health?.llm_provider }} · {{ health?.llm_model }}
          </el-tag>
          <el-tag v-else type="danger" effect="dark">⚠ LLM 未配置</el-tag>
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
import { ref, onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import axios from 'axios'
import { ElMessage } from 'element-plus'

const route = useRoute()
const persona = ref(null)
const health = ref(null)

const lastChatText = computed(() => {
  if (!persona.value || !persona.value.last_chat_at) return '从未'
  const d = new Date(persona.value.last_chat_at)
  const diff = Math.floor((Date.now() - d.getTime()) / 86400000)
  if (diff <= 0) return '今天'
  return diff + ' 天前'
})

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

onMounted(reloadPersona)
defineExpose({ reloadPersona })
</script>

<style scoped lang="scss">
.shell {
  display: grid;
  grid-template-columns: 240px 1fr;
  height: 100vh;
}
.sidebar {
  background: var(--bg-panel);
  border-right: 1px solid var(--border);
  display: flex; flex-direction: column;
  overflow-y: auto;
}
.brand {
  padding: 18px 16px; display: flex; gap: 10px; align-items: center;
  border-bottom: 1px solid var(--border);
}
.brand-emoji { font-size: 30px; }
.brand-title { font-size: 17px; font-weight: 700; color: var(--accent); letter-spacing: 0.04em; }
.brand-sub { font-size: 11px; color: var(--text-dim); }
nav { padding: 10px 10px; display: flex; flex-direction: column; gap: 4px; flex: 1; }
.nav-item {
  display: flex; align-items: center; gap: 10px;
  padding: 10px 12px; border-radius: 8px;
  color: var(--text-soft); text-decoration: none; font-size: 14px;
  transition: all 0.15s ease;
  .el-icon { font-size: 16px; }
}
.nav-item:hover { background: var(--bg-panel-2); color: var(--text); }
.nav-item.router-link-active {
  background: linear-gradient(90deg, rgba(246,180,79,0.18), transparent);
  color: var(--accent);
  border: 1px solid rgba(246,180,79,0.35);
}

.status-card {
  margin: 12px; padding: 12px; border-radius: 10px;
  background: var(--bg-panel-2);
  border: 1px solid var(--border);
}
.status-row {
  display: grid; grid-template-columns: 32px 1fr 50px;
  gap: 8px; align-items: center;
  font-size: 12px; color: var(--text-soft); margin-bottom: 8px;
  em { font-size: 11px; color: var(--text-dim); text-align: right; font-style: normal; }
}
.status-hint { font-size: 11px; color: var(--text-dim); margin-bottom: 6px; }
.status-meta { font-size: 10px; color: var(--text-dim); }

.main { display: flex; flex-direction: column; overflow: hidden; }
.topbar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 18px;
  border-bottom: 1px solid var(--border); background: var(--bg-panel);
}
.top-title { font-size: 16px; color: var(--accent); font-weight: 600; }
.content { flex: 1; overflow-y: auto; padding: 16px 20px; }
.fade-enter-active, .fade-leave-active { transition: opacity 0.2s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
@media (max-width: 860px) {
  .shell { grid-template-columns: 64px 1fr; }
  .brand-title, .brand-sub, .nav-item span { display: none; }
  .status-card { display: none; }
  .nav-item { justify-content: center; }
}
</style>
