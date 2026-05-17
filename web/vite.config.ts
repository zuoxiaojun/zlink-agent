import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import { resolve } from 'path'

export default defineConfig(({ mode }) => {
  // 从项目根目录 .env 加载环境变量
  const envDir = resolve(__dirname, '..')
  const env = loadEnv(mode, envDir, '')

  const frontendPort = parseInt(env.YS_FRONTEND_PORT || '8088')
  const backendPort = env.YS_AGENT_PORT || '8089'

  return {
    plugins: [react()],
    server: {
      port: frontendPort,
      proxy: {
        '/api': `http://localhost:${backendPort}`,
        '/ws': {
          target: `ws://localhost:${backendPort}`,
          ws: true,
        },
      },
    },
  }
})
