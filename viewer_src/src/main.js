// Kosmos-equivalent viewer entry: one global that mounts matterviz's Structure component, plus a
// handle that swaps the structure IN PLACE so a frame change never re-fits the camera.
import 'matterviz/app.css'
import { mount } from 'svelte'
import { Structure } from 'matterviz'

const KOSMOS_HIGHLIGHT = `#000`
const KOSMOS_RADIUS = 1.5

function scene_props_for(marks, extra) {
  const base = { ...(extra || {}) }
  if (marks && marks.length) {
    base.active_sites = marks
    base.active_highlight_color = KOSMOS_HIGHLIGHT
  }
  return base
}

globalThis.renderMatterViz = (structure, target, props = {}) => {
  const { marks, scene_props, ...rest } = props
  const site_radius_overrides = marks && marks.length
    ? new Map(marks.map((i) => [i, KOSMOS_RADIUS]))
    : undefined
  return mount(Structure, {
    target,
    props: {
      structure,
      show_controls: false,
      style: `height:100%;background:#fff`,
      ...(site_radius_overrides ? { site_radius_overrides } : {}),
      scene_props: scene_props_for(marks, scene_props),
      ...rest,
    },
  })
}
globalThis.__mv_ready = true
