import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// GitHub Pages 部署：base 是仓库名 /kizuna-ai/
// 本地开发：依然可以 / 或 dev server 反代 /api -> :8000
const isDeploy = process.env.GITHUB_PAGES === '1' || process.env.DEPLOY === '1'

export default defineConfig({
  base: isDeploy ? '/kizuna-ai/' : '/',
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      }
    }
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  }
})
