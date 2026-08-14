import { defineConfig } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'

// Builds the site's structure viewer from the matterviz package, so the panes can be given the
// same settings Kosmos uses (scene_props.active_sites + active_highlight_color, site_radius_overrides).
export default defineConfig({
  plugins: [svelte()],
  build: {
    outDir: '../docs/mv',
    emptyOutDir: true,
    cssCodeSplit: false,
    target: 'es2022',
    lib: { entry: 'src/main.js', formats: ['es'], fileName: () => 'mv-app.js' },
  },
})
