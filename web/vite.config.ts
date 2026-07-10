import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import { resolve } from 'path'

export default defineConfig(({ mode }) => {
  const envDir = resolve(__dirname, '..')
  const env = loadEnv(mode, envDir, '')

  const frontendPort = parseInt(env.ZLINK_FRONTEND_PORT || '8088')
  const backendPort = env.ZLINK_AGENT_PORT || '8089'

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
