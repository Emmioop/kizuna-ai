<template>
  <div>
    <!-- 工具条 -->
    <div class="toolbar">
      <el-select v-model="category" placeholder="类别" clearable style="width:140px;" @change="load">
        <el-option v-for="(v,k) in cats" :key="k" :label="v" :value="k" />
      </el-select>
      <el-input v-model="q" placeholder="搜索记忆（语义+关键词）" clearable style="width:300px;" @clear="load" @keyup.enter="search">
        <template #append><el-button @click="search"><el-icon><Search /></el-icon></el-button></template>
      </el-input>
      <el-button type="warning" @click="openNew">
        <el-icon><Plus /></el-icon>新增记忆
      </el-button>
      <div style="flex:1"></div>
      <el-tag type="info">共 {{ items.length }} 条</el-tag>
    </div>

    <el-table :data="items" stripe style="margin-top:10px;">
      <el-table-column prop="id" label="#" width="58" />
      <el-table-column label="类别" width="120">
        <template #default="{row}">
          <el-tag :type="tagType(row.category)" size="small">
            {{ row.category_label || cats[row.category] || row.category }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="title" label="标题" min-width="180" />
      <el-table-column prop="content" label="内容" min-width="300">
        <template #default="{row}">
          <div class="cont-text">{{ row.content }}</div>
        </template>
      </el-table-column>
      <el-table-column label="⭐/权" width="90" align="center">
        <template #default="{row}">
          <div v-if="row.pinned" style="color:var(--accent)">⭐</div>
          <div style="font-size:11px;color:var(--text-dim)">权重 {{ row.weight }}</div>
        </template>
      </el-table-column>
      <el-table-column label="命中分" width="80" align="center">
        <template #default="{row}">
          <span v-if="row.score !== undefined">{{ (row.score*100).toFixed(0) }}</span>
          <span v-else style="color:var(--text-dim)">—</span>
        </template>
      </el-table-column>
      <el-table-column prop="access_count" label="调用" width="60" align="center" />
      <el-table-column label="操作" width="140" align="right" fixed="right">
        <template #default="{row}">
          <el-button size="small" text type="primary" @click="openEdit(row)">编辑</el-button>
          <el-popconfirm title="删除这条记忆？" @confirm="del(row.id)">
            <template #reference>
              <el-button size="small" text type="danger">删除</el-button>
            </template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>

    <!-- 编辑/新增对话框 -->
    <el-dialog v-model="dlg" :title="editing ? '编辑记忆' : '新增记忆'" width="560px">
      <el-form :model="form" label-width="80px">
        <el-form-item label="类别">
          <el-select v-model="form.category" style="width:100%;">
            <el-option v-for="(v,k) in cats" :key="k" :label="v" :value="k" />
          </el-select>
        </el-form-item>
        <el-form-item label="标题">
          <el-input v-model="form.title" placeholder="一句话概括，比如：主人的生日" />
        </el-form-item>
        <el-form-item label="标签">
          <el-input v-model="form.tags" placeholder="用逗号分隔，例如：家人，生日，重要" />
        </el-form-item>
        <el-form-item label="内容">
          <el-input v-model="form.content" type="textarea" :rows="4"
            placeholder="详细内容，例如：主人是 1998 年 3 月 12 日出生的，属虎，双鱼座。" />
        </el-form-item>
        <el-form-item label="权重">
          <el-slider v-model="form.weight" :min="1" :max="10" :step="1" show-input />
        </el-form-item>
        <el-form-item label="重要">
          <el-switch v-model="form.pinned" />
          <span style="color:var(--text-dim);font-size:12px;margin-left:8px;">
            开启后每次聊天都会优先被看到
          </span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dlg=false">取消</el-button>
        <el-button type="warning" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, ref, reactive } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'

const items = ref([])
const cats = ref({})
const category = ref('')
const q = ref('')
const dlg = ref(false)
const editing = ref(false)
const form = reactive({
  category: 'important', title: '', content: '', tags: '', weight: 5, pinned: false, _id: null,
})

function tagType(k) {
  return {
    user_profile: 'success',
    important: 'warning',
    anniversary: 'danger',
    conversation: 'info',
  }[k] || 'info'
}

async function loadCats() {
  cats.value = (await axios.get('/api/memory/categories')).data
}

async function load() {
  const r = await axios.get('/api/memory', { params: { category: category.value || '', q: '' } })
  items.value = r.data
}

async function search() {
  const r = await axios.get('/api/memory', { params: { category: category.value || '', q: q.value || '' } })
  items.value = r.data
}

function openNew() {
  editing.value = false
  Object.assign(form, { category: 'important', title: '', content: '', tags: '', weight: 5, pinned: false, _id: null })
  dlg.value = true
}
function openEdit(row) {
  editing.value = true
  Object.assign(form, {
    category: row.category, title: row.title, content: row.content, tags: row.tags || '',
    weight: Number(row.weight || 5), pinned: !!row.pinned, _id: row.id,
  })
  dlg.value = true
}
async function save() {
  try {
    if (editing.value) {
      await axios.patch('/api/memory/' + form._id, form)
    } else {
      await axios.post('/api/memory', form)
    }
    dlg.value = false
    ElMessage.success('已保存')
    await load()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || e.message)
  }
}
async function del(id) {
  await axios.delete('/api/memory/' + id)
  ElMessage.success('已删除')
  await load()
}
onMounted(async () => { await loadCats(); await load() })
</script>

<style scoped lang="scss">
.toolbar { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }
.cont-text {
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  overflow: hidden; color: var(--text-soft); font-size: 13px;
}
</style>
