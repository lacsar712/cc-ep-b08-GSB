<template>
  <div class="page">
    <h1>新建实验 Run</h1>
    <p class="muted">提交 StartRun 命令：写入 event_store 并投影为 running</p>
    <div class="card" style="max-width: 720px">
      <n-alert
        v-if="errorMessage"
        type="error"
        title="创建被拒绝"
        :show-icon="true"
        style="margin-bottom: 16px"
        closable
        @close="errorMessage = ''"
      >
        {{ errorMessage }}
      </n-alert>
      <n-form label-placement="top">
        <n-form-item label="项目 project" required>
          <n-input v-model:value="form.project" placeholder="protein-folding" @input="errorMessage = ''" />
        </n-form-item>
        <n-form-item label="名称 name" required>
          <n-input v-model:value="form.name" placeholder="实验名称" @input="errorMessage = ''" />
        </n-form-item>
        <n-form-item label="数据集指纹 dataset_content_sha256（64 位 hex）" required>
          <n-input v-model:value="form.dataset_content_sha256" class="mono" placeholder="64 hex" />
          <n-button text type="primary" style="margin-top: 4px" @click="fillDataset">用示例填充</n-button>
        </n-form-item>
        <n-form-item label="代码提交 code_commit_sha" required>
          <n-input v-model:value="form.code_commit_sha" class="mono" placeholder="git commit sha" />
          <n-button text type="primary" style="margin-top: 4px" @click="fillCommit">用示例填充</n-button>
        </n-form-item>
        <n-form-item label="描述">
          <n-input v-model:value="form.description" type="textarea" :rows="3" />
        </n-form-item>
        <n-button type="primary" :loading="loading" @click="submit">启动 Run</n-button>
      </n-form>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useMessage } from 'naive-ui'
import { createRun } from '../api/client'

const router = useRouter()
const message = useMessage()
const loading = ref(false)
const errorMessage = ref('')

const form = reactive({
  project: 'protein-folding',
  name: '',
  dataset_content_sha256: '',
  code_commit_sha: '',
  description: '',
  expected_version: 0,
})

function randomHex(n) {
  const bytes = new Uint8Array(n)
  crypto.getRandomValues(bytes)
  return Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('')
}

function fillDataset() {
  form.dataset_content_sha256 = randomHex(32)
}

function fillCommit() {
  form.code_commit_sha = randomHex(20)
}

async function submit() {
  if (!form.name.trim()) {
    message.warning('请填写名称')
    return
  }
  if (!form.project.trim()) {
    message.warning('请填写项目')
    return
  }
  loading.value = true
  errorMessage.value = ''
  try {
    const run = await createRun({
      ...form,
      project: form.project.trim(),
      name: form.name.trim(),
    })
    message.success('Run 已启动')
    router.push(`/runs/${run.id}`)
  } catch (e) {
    // 服务端拒绝（如 409：同项目下已有未结束的同名 Run），在表单上方固定展示原因
    errorMessage.value =
      e.response?.data?.detail || e.message || '创建失败，请稍后重试'
    message.error(errorMessage.value)
  } finally {
    loading.value = false
  }
}
</script>
