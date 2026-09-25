# Phase 8 — Dark Mode

**Completed:** 2026-09-10 · **Index:** [`SUMMARY.md`](../SUMMARY.md)

- Added a checkable `View > Dark Mode` action. Dark mode is enabled by default and can be restored from session JSON.
- Applied a Nord/slate UI palette using `#2E3440` for backgrounds and `#ECEFF4` for default text.
- Added HSL pixel transformation in `RenderEngine`: near-white low-saturation paper becomes slate, near-black body text becomes ice, and colored pixels retain hue and saturation while their lightness is clamped to $0.55 \le L \le 0.75$.
- Each viewer rerenders its active page when the theme changes, without reopening the PDF.
- Possible improvements include moving pixel processing to a worker for very large pages, caching transformed pages, and adding contrast-aware handling for images and transparency.
- Replaced the Python per-pixel loop with NumPy array operations and a precomputed 256-entry RGB LUT for neutral pixels. The LUT maps ice text to slate paper through a smooth cubic curve, preserving grayscale antialiasing levels instead of flattening font edges.
- Colored pixels are transformed in bulk with their hue and saturation retained; lightness moves smoothly into the readable midrange rather than being hard-clipped at the endpoints. This reduces UI lag and avoids destroying subpixel edge relationships.
- Replaced the colored-pixel cutoff with continuous chroma blending: pixels transition smoothly from the grayscale LUT at chroma 15 to hue-safe inverted colors at chroma 55, using smoothstep interpolation for antialiased syntax edges.
