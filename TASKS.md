# TASKS.md - Phase 8: Dark Mode

- [x] In the Menubar, under View, create a qaction for dark mode, as a checkable item.
- [x] Dark mode on by default.
- [x] Save Dark mode state, if on or off, in Session JSON.
- [x] Dark Mode palette: Background: Deep gray-blue (#2E3440 or #1E1E2E), Default Text: Off-white / Ice (#ECEFF4)
- [x] For dark mode, process the pixmap buffer using HSL/HSV luminance
- [x] Convert RGB to HSL / HSV: Inspect each pixel's Lightness (L) and Saturation (S).
- [x] Handle the Page Canvas: If a pixel has near-zero saturation (S < 0.1) and very high lightness (L > 0.9), it is white paper—remap it directly to your target dark charcoal/slate hex.
- [x] Handle Default Body Text: If S < 0.1 and L < 0.15, it is black body text—remap it to light cream/gray.
- [x] Handle Syntax Highlights: If S greather or equal to 0.1, it is a colored token (a keyword, string, or function name). Keep the original Hue (H) unchanged, but clamp the Lightness (L) into an accessible mid-to-high range ($0.55 \le L \le 0.75$) so dark colors like navy or dark maroon remain legible against the dark background without shifting into entirely different hues.
- [x] Explain changes, how it was implmented, and suggest improvements.
- [x] Vectorize with a Precomputed 256-Value LUT (Look-Up Table)
- [x] Preserve Color Saturation Smoothly Without Edge Clipping
- [x] fix colored code in dark mode