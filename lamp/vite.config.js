import { defineConfig } from 'vite';

// Pin a port distinct from cutRope (5173) so both frontends can run in parallel.
export default defineConfig({
  server: { port: 5174, strictPort: true },
  preview: { port: 5174, strictPort: true },
  test: {
    environment: 'jsdom'
  }
});
