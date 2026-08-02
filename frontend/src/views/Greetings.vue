<template>
  <div>
    <section class="card">
      <h3>主动触发问候</h3>
      <p class="sub">除了按时间自动触发，你也可以手动让她发一条消息。触发的内容会被写入历史记录。</p>

      <div class="btns">
        <el-button type="warning" @click="trigger('morning')">
          <el-icon><Sunny /></el-icon> 说早安
        </el-button>
        <el-button type="primary" @click="trigger('bed')">
          <el-icon><Moon /></el-icon> 睡前提醒
        </el-button>
        <el-button type="danger" @click="trigger('anniversary')">
          <el-icon><Cake /></el-icon> 纪念日祝福
        </el-button>
        <el-button type="success" @click="trigger('miss')">
          <el-icon><Connection /></el-icon> 久未联系
        </el-button>
      </div>

      <el-dialog v-model="showResult" title="她想对你说的话" width="560px">
        <div class="result-text">{{ lastResult }}</div>
      </el-dialog>
    </section>

    <section class="card" style="margin-top:16px;">
      <h3>问候历史</h3>
      <el-table :data="items" stripe style="margin-top:10px;">
        <el-table-column label="类型" width="120">
          <template #default="{row}">
            <el-tag :type="typeTag(row.type)" size="small">{{ typeLabel(row.type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="content" label="内容" min-width="420">
          <template #default="{row}"><div class="cont-text">{{ row.content }}</div></template>
        </el-table-column>
        <el-table-column label="触发时间" width="170">
          <template #default="{row}">{{ fmt(row.trigger_time) }}</template>
        </el-table-column>
        <el-table-column label="已读" width="70" align="center">
          <template #default="{row}">
            <el-tag v-if="row.user_read" type="success" size="small">✓</el-tag>
            <el-tag v-else type="info" size="small">未读</el-tag>
          </template>
        </el-table-column>
      </el-table>
    </section>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'

const items = ref([])
const showResult = ref(false)
const lastResult = ref('')

function typeLabel(t) {
  return { morning: '早安', bed: '睡前', anniversary: '纪念日', miss: '想你了', custom: '自定义' }[t] || t
}
function typeTag(t) {
  return { morning: 'warning', bed: 'primary', anniversary: 'danger', miss: 'success' }[t] || 'info'
}
function fmt(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return (d.getMonth()+1) + '/' + d.getDate() + ' ' + d.toTimeString().slice(0,5)
}

async function load() {
  try {
    items.value = (await axios.get('/api/greeting/history', { params: { limit: 100 } })).data
  } catch(e) {}
}

async function trigger(type_) {
  try {
    const r = await axios.post('/api/greeting/trigger/' + type_)
    if (r.data.ok) {
      lastResult.value = r.data.content
      showResult.value = true
      ElMessage.success('已触发')
      await load()
    } else {
      ElMessage.warning('触发失败，可能 LLM 未配置')
    }
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || e.message)
  }
}

onMounted(load)
</script>

<style scoped lang="scss">
.card {
  background: var(--bg-panel); border: 1px solid var(--border);
  border-radius: 12px; padding: 18px 22px;
}
.card h3 { margin: 0 0 6px; color: var(--accent); font-size: 16px; }
.sub { color: var(--text-soft); font-size: 13px; margin-bottom: 14px; }
.btns { display: flex; gap: 10px; flex-wrap: wrap; }
.cont-text {
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  overflow: hidden; color: var(--text-soft); font-size: 13px; line-height: 1.6;
}
.result-text {
  background: var(--bg-panel-2); border: 1px solid var(--border);
  padding: 18px; border-radius: 10px; line-height: 1.9; font-size: 15px;
  white-space: pre-wrap; color: var(--text);
}
</style>
