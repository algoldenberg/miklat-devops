import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // vite.config.js выполняется в Node вне клиентского import.meta.env —
  // .env-файлы сюда нужно подгружать явно через loadEnv.
  const env = loadEnv(mode, process.cwd(), '');

  return {
    plugins: [react()],
    server: {
      host: true,
      port: 5173,
      proxy: {
        // Локальная разработка (npm run dev) без docker-compose: тот же приём,
        // что и в nginx.conf для собранного контейнера — фронтенд всегда
        // обращается к "/api/*", прокси отрезает префикс и форвардит на
        // miklat-gateway. Адрес настраивается через VITE_GATEWAY_URL в .env
        // (см. .env.example), по умолчанию — как в docker-compose: 8000 на хосте.
        '/api': {
          target: env.VITE_GATEWAY_URL || 'http://localhost:8000',
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api/, ''),
        },
      },
    },
  };
})
