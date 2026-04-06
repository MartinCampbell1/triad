# Codex Desktop App Design System

Extracted from Codex Desktop (openai-codex-electron v26.325.31654).
CSS framework: **Tailwind CSS v4** with custom design tokens.
Color scheme: **dark-first** (uses `prefers-color-scheme:dark` with lightningcss).

---

## 1. Color Palette (Raw Primitives)

All colors are defined as CSS custom properties on `:root`.

### Gray Scale

| Token        | Hex       | Usage                          |
|-------------|-----------|--------------------------------|
| `--gray-0`   | `#fff`    | White / light surface          |
| `--gray-50`  | `#f9f9f9` | Light surface-under            |
| `--gray-100` | `#ededed` | Light editor background        |
| `--gray-300` | `#afafaf` | Secondary text (light)         |
| `--gray-500` | `#5d5d5d` | Tertiary text, muted           |
| `--gray-600` | `#414141` | Dark muted                     |
| `--gray-750` | `#282828` | Dark elevated primary          |
| `--gray-800` | `#212121` | Dark editor/elevated bg        |
| `--gray-900` | `#181818` | **Dark main surface**          |
| `--gray-1000`| `#0d0d0d` | Near-black, primary buttons    |

### Brand / Accent Blues

| Token        | Hex       | Usage                          |
|-------------|-----------|--------------------------------|
| `--blue-50`  | `#e5f3ff` | Light accent background        |
| `--blue-100` | `#99ceff` | Dark text accent               |
| `--blue-300` | `#339cff` | **Primary accent / brand blue**|
| `--blue-400` | `#0285ff` | Brighter blue (links, focus)   |
| `--blue-900` | `#00284d` | Dark accent background         |

### Semantic Colors

| Token        | Hex       | Usage                          |
|-------------|-----------|--------------------------------|
| `--green-300`| `#40c977` | Success (dark theme)           |
| `--green-400`| `#04b84c` | Success secondary              |
| `--green-500`| `#00a240` | Success (light theme)          |
| `--red-300`  | `#ff6764` | Error (dark theme)             |
| `--red-400`  | `#fa423e` | Error badge/danger             |
| `--red-500`  | `#e02e2a` | Error (light theme)            |
| `--red-600`  | `#ba2623` | Deletion decoration            |
| `--orange-300`| `#ff8549`| Warning (dark theme)           |
| `--orange-400`| `#fb6a22`| Warning secondary              |
| `--orange-500`| `#e25507`| Warning (light theme)          |
| `--yellow-300`| `#ffd240`| Accent yellow (dark)           |
| `--yellow-400`| `#ffc300`| Accent yellow (light)          |
| `--purple-300`| `#ad7bf9`| Accent purple (dark)           |
| `--purple-400`| `#924ff7`| Accent purple (light)          |
| `--pink-400` | `#ff66ad` | Accent pink                    |

---

## 2. Dark Theme Semantic Tokens

This is the primary theme. All resolved hex values are included for direct use.

### Backgrounds

| Semantic Token                          | Resolved Value (Dark)       | Hex Approximation |
|----------------------------------------|-----------------------------|--------------------|
| `--color-background-surface`           | `var(--gray-900)`           | `#181818`          |
| `--color-background-surface-under`     | `black`                     | `#000000`          |
| `--color-background-elevated-primary`  | `var(--gray-750)`           | `#282828`          |
| `--color-background-elevated-secondary`| gray-0 at 3% opacity       | near-transparent   |
| `--color-background-editor-opaque`     | `var(--gray-800)`           | `#212121`          |
| `--color-background-accent`            | `var(--blue-900)`           | `#00284d`          |
| `--color-background-button-primary`    | `var(--gray-1000)`          | `#0d0d0d`          |

### Text

| Semantic Token                      | Resolved (Dark)                     | Hex Approximation |
|------------------------------------|-------------------------------------|--------------------|
| `--color-text-foreground`          | `var(--gray-0)`                     | `#ffffff`          |
| `--color-text-foreground-secondary`| gray-0 at 70%                       | `#ffffffb3`        |
| `--color-text-foreground-tertiary` | gray-0 at 50%                       | `#ffffff80`        |
| `--color-text-accent`             | `var(--blue-100)`                   | `#99ceff`          |
| `--color-text-error`              | `var(--red-300)`                    | `#ff6764`          |
| `--color-text-success`            | `var(--green-300)`                  | `#40c977`          |
| `--color-text-warning`            | `var(--orange-300)`                 | `#ff8549`          |

### Borders

| Semantic Token               | Resolved (Dark)                        | Hex Approximation  |
|------------------------------|----------------------------------------|--------------------|
| `--color-border`             | white at 8% opacity                    | `#ffffff14`        |
| `--color-border-heavy`       | white at 16% opacity                   | `#ffffff29`        |
| `--color-border-light`       | white at 4% opacity                    | `#ffffff0a`        |
| `--color-border-focus`       | `var(--blue-300)`                      | `#339cff`          |

### Icons

| Semantic Token           | Resolved (Dark)        |
|-------------------------|------------------------|
| `--color-icon-primary`  | white at 90% opacity   |
| `--color-icon-secondary`| white at 70% opacity   |
| `--color-icon-tertiary` | white at 50% opacity   |

---

## 3. Typography

### Font Stacks

```css
/* System sans-serif (UI text) */
--font-sans-default: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
--font-sans: var(--vscode-font-family, var(--font-sans-default));

/* Monospace (code, diffs, terminal) */
--font-mono-default: ui-monospace, "SFMono-Regular", "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
--font-mono: var(--vscode-editor-font-family, var(--font-mono-default));
```

**Key takeaway**: Codex uses the system font stack. No custom web fonts for UI text. Only KaTeX math fonts are bundled.

### Font Sizes

| Token          | Size   | Usage                                  |
|---------------|--------|----------------------------------------|
| `--text-xs`   | `10px` | Tiny labels, badges                    |
| `--text-sm`   | `12px` | Small text, code editor default        |
| `--text-base` | `13px` | **Default UI text size**               |
| `--text-lg`   | `16px` | Larger body text                       |
| `--text-xl`   | `28px` | Large headings                         |
| `--text-2xl`  | `36px` | Hero headings                          |
| `--text-3xl`  | `48px` | Display headings                       |
| `--text-4xl`  | `72px` | Jumbo display                          |

**Chat-specific**:
- Chat font size: `13px` (fallback)
- Chat code font size: `12px` (fallback)
- Diffs font size: `11px` (chat code size minus 1px)

### Font Weights

| Token                   | Value |
|------------------------|-------|
| `--font-weight-light`  | `300` |
| `--font-weight-normal` | `400` |
| `--font-weight-medium` | `500` |
| `--font-weight-semibold`| `600`|
| `--font-weight-bold`   | `700` |

### Line Heights

| Token               | Value   |
|---------------------|---------|
| `--leading-tight`   | `1.25`  |
| `--leading-snug`    | `1.375` |
| `--leading-normal`  | `1.5`   |
| `--leading-relaxed` | `1.625` |

### Letter Spacing

| Token              | Value      |
|-------------------|------------|
| `--tracking-tight` | `-0.025em` |
| `--tracking-normal`| `0em`      |
| `--tracking-wide`  | `0.025em`  |

---

## 4. Spacing System

Base unit: `--spacing: 0.25rem` (4px)

All spacing is computed as multiples of 4px:

| Multiplier | Value  | CSS                             |
|-----------|--------|----------------------------------|
| 0.5       | 2px    | `calc(var(--spacing) * 0.5)`     |
| 1         | 4px    | `calc(var(--spacing) * 1)`       |
| 1.5       | 6px    | `calc(var(--spacing) * 1.5)`     |
| 2         | 8px    | `calc(var(--spacing) * 2)`       |
| 2.5       | 10px   | `calc(var(--spacing) * 2.5)`     |
| 3         | 12px   | `calc(var(--spacing) * 3)`       |
| 4         | 16px   | `calc(var(--spacing) * 4)`       |
| 5         | 20px   | `calc(var(--spacing) * 5)`       |
| 6         | 24px   | `calc(var(--spacing) * 6)`       |
| 8         | 32px   | `calc(var(--spacing) * 8)`       |
| 10        | 40px   | `calc(var(--spacing) * 10)`      |
| 16        | 64px   | `calc(var(--spacing) * 16)`      |

### Key Layout Spacings

| Property                        | Value  |
|--------------------------------|--------|
| Conversation block gap         | `12px` |
| Tool-to-assistant gap          | `16px` |
| Panel padding (compact)        | `12px` |
| Panel padding (normal)         | `20px` |
| Row horizontal padding         | `8px`  |
| Row vertical padding           | `4-5px`|

---

## 5. Border Radius

All radii scale via `--corner-radius-scale` (1.0 default, 1.25 enlarged mode).

| Token          | Base     | Default (px) | Enlarged (px) |
|---------------|----------|--------------|---------------|
| `--radius-2xs` | 0.125rem | 2px          | 2.5px         |
| `--radius-xs`  | 0.25rem  | 4px          | 5px           |
| `--radius-sm`  | 0.375rem | 6px          | 7.5px         |
| `--radius-md`  | 0.5rem   | 8px          | 10px          |
| `--radius-lg`  | 0.625rem | 10px         | 12.5px        |
| `--radius-xl`  | 0.75rem  | 12px         | 15px          |
| `--radius-2xl` | 1rem     | 16px         | 20px          |
| `--radius-3xl` | 1.25rem  | 20px         | 25px          |
| `--radius-4xl` | 1.5rem   | 24px         | 30px          |
| `--radius-full`| 9999px   | pill         | pill          |

Common usage:
- Buttons: `rounded-lg` to `rounded-xl` (10-12px)
- Cards/panels: `rounded-2xl` to `rounded-3xl` (16-20px)
- Hotkey shell: `--radius-4xl` (24px)
- Avatars, pills: `rounded-full`
- Code blocks: `rounded-xl` (12px)

---

## 6. Shadows

```css
/* Elevation levels */
--shadow-sm:  0px 1px 2px -1px rgba(0, 0, 0, 0.08);
--shadow-md:  0px 2px 4px -1px rgba(0, 0, 0, 0.08);
--shadow-lg:  0px 4px 8px -2px rgba(0, 0, 0, 0.10);
--shadow-xl:  0px 8px 16px -4px rgba(0, 0, 0, 0.12);
--shadow-2xl: 0px 16px 32px -8px rgba(0, 0, 0, 0.19);

/* Combined elevation + border */
elevated-ring: 0px 0px 0px 0.5px var(--color-token-border), var(--shadow-xl);

/* Focus ring (blue glow) */
focus-ring: 0 0 0 1px rgba(59, 130, 246, 0.65), 0 0 26px rgba(59, 130, 246, 0.38);

/* Inner glow (top edge highlight) */
inset-glow: inset 0 1px 0 rgba(255, 255, 255, 0.12);

/* Sidebar depth */
sidebar-edge: -16px 0 32px rgba(0, 0, 0, 0.28);
```

---

## 7. Z-Index Scale

| Range          | Usage                     |
|---------------|---------------------------|
| -5 to -1      | Behind content             |
| 0-10          | Base content layers        |
| 20-60         | Overlays, popovers         |
| 80            | High overlays              |
| 1000          | Dropdowns, tooltips        |
| 9999-10000    | Modals, dialogs            |
| 2147483647    | Absolute top (loading bar) |

---

## 8. Animations & Transitions

### Default Transition

```css
transition-duration: 0.15s;
transition-timing-function: cubic-bezier(0.4, 0, 0.2, 1);
```

### Easing Functions

```css
--default-transition-timing-function: cubic-bezier(0.4, 0, 0.2, 1);  /* ease-in-out */
--cubic-enter: cubic-bezier(0.19, 1, 0.22, 1);                       /* snappy enter */
--ease-out: cubic-bezier(0, 0, 0.2, 1);                              /* decelerate   */
--transition-ease-basic: ease;                                         /* simple ease  */
```

### Duration Tokens

| Token                         | Value  |
|------------------------------|--------|
| `--default-transition-duration`| `0.15s`|
| `--transition-duration-relaxed`| `0.3s` |
| fast                          | `0.1s` |
| medium                        | `0.2s` |
| slow                          | `0.5s` |
| use-case transition           | `0.22s`|

### Named Animations

- **spin**: 1s linear infinite rotation
- **pulse**: 2s ease-in-out opacity pulse
- **ping**: 1s scale-out ring effect
- **loading-shimmer**: gradient sweep
- **hyperspeed-model-shimmer**: branded shimmer with 4.5s pause/run cycle
- **codex-logo-shimmer**: startup logo shimmer (2200ms)
- **toast-open / toast-close**: toast notification entry/exit
- **codex-dialog-enter**: dialog slide up + scale (0.3s, cubic-enter)

### Dialog Animation

```css
/* Entry: slide up 8px + scale from 98% */
@keyframes codex-dialog-enter {
  0%   { opacity: 0; transform: translateY(8px) scale(0.98); }
  100% { opacity: 1; transform: translateY(0) scale(1); }
}
```

---

## 9. Layout

### Sidebar

```css
--spacing-token-sidebar: clamp(240px, 300px, min(520px, calc(100vw - 320px)));
```

- Minimum width: **240px**
- Default width: **300px**
- Maximum width: **520px**
- Sidebar background: `black` (dark) / `var(--gray-50)` (light)

### Thread / Conversation Area

```css
--thread-content-max-width: 48rem;   /* 768px */
--thread-composer-max-width: calc(var(--thread-content-max-width) + 1rem); /* 784px */
```

In compact/narrow mode: `500px`.

### Toolbar

```css
--height-toolbar: 56px;    /* primary toolbar */
--height-toolbar-sm: 36px; /* compact toolbar */
```

Secondary toolbar height: `46px`.

### Composer Button Heights

```css
--spacing-token-button-composer: calc(var(--spacing) * 7);    /* 28px */
--spacing-token-button-composer-sm: calc(var(--spacing) * 5); /* 20px */
```

---

## 10. Code Block Styling

```css
/* Code block background (dark theme) */
background-color: var(--color-token-text-code-block-background);
/* Resolves to: var(--color-border) which is white at 8% opacity */

/* Inline code background */
background-color: color-mix(in oklab, var(--color-token-text-code-block-background) 10%, transparent);

/* Code font */
font-family: var(--font-mono);
/* = ui-monospace, "SFMono-Regular", "SF Mono", Menlo, Consolas, "Liberation Mono", monospace */

font-size: 12px;  /* --codex-chat-code-font-size */

/* Diff code styling */
--diffs-font-family: var(--font-mono);
--diffs-font-size: calc(var(--codex-chat-code-font-size) - 1px); /* 11px */
--diffs-line-height: calc(var(--diffs-font-size, 12px) * 1.8);   /* ~21.6px */
```

### Markdown Content

- Wide blocks max width: `64rem` (1024px), expandable to `80rem` (1280px)
- Wide blocks max height: `80vh`
- Markdown content uses `overflow-wrap: anywhere`
- Fade-in animation on markdown elements: `0.2s cubic-bezier(0.37, 0.55, 0.86, 0.88)`

---

## 11. Glassmorphism / Backdrop Effects

Codex uses backdrop blur extensively for layered surfaces:

```css
/* Blur levels */
--blur-sm: 8px;
--blur-md: 12px;
--blur-lg: 16px;
--blur-xl: 24px;

/* Example: elevated surface */
backdrop-filter: blur(12px);
background: color-mix(in oklab, var(--gray-800) 96%, transparent);
```

Common patterns:
- Sidebar overlay: `backdrop-blur-md` (12px)
- Elevated panels: `backdrop-blur-sm` (8px)
- Edge fading: `1rem` to `2rem` gradient masks

---

## 12. Scrollbar Styling

```css
/* Scrollbar thumb */
background: var(--color-border);             /* white at 8% - subtle */

/* On hover */
background: var(--color-border-heavy);       /* white at 16% */

/* Hide-scrollbar pattern */
scrollbar-color: transparent transparent;    /* default hidden */
/* On container hover: reveals thumb */
```

---

## 13. Breakpoints

### Width-based (responsive)

| Name | Width      | Pixels  |
|------|-----------|---------|
| 3xs  | `15rem`   | 240px   |
| 2xs  | `20rem`   | 320px   |
| xs   | `280px`   | 280px   |
| sm   | `400px`   | 400px   |
| md   | `40rem`   | 640px   |
| lg   | `48rem`   | 768px   |
| xl   | `64rem`   | 1024px  |
| 2xl  | `80rem`   | 1280px  |
| 3xl  | `96rem`   | 1536px  |

Additional pixel breakpoints used for specific component queries:
`220px`, `260px`, `280px`, `350px`, `400px`, `440px`, `480px`, `720px`, `920px`, `1024px`

### Container Queries

The composer footer uses container queries:
```css
@container composer-footer (width <= 300px) { ... }
@container composer-footer (width <= 420px) { ... }
@container composer-footer (width <= 475px) { ... }
@container composer-footer (width >= 476px) { ... }
```

### Height-based

```css
@media (height <= 500px) { /* compact vertical layout */ }
```

---

## 14. Hotkey Window / Home Shell

The "hotkey window" (quick-access command window) has specific tokens:

```css
--hotkey-window-home-shell-background: color-mix(in oklab, var(--color-token-side-bar-background) 94%, transparent);
--hotkey-window-home-shell-border: color-mix(in srgb, var(--color-token-border) 72%, transparent);
--hotkey-window-home-shell-inline-padding: 12px;
--hotkey-window-home-shell-radius: var(--radius-4xl);  /* 24px */
--hotkey-window-home-shell-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.10);
--hotkey-window-home-shell-top-padding: 14px;
```

---

## 15. Shimmer / Brand Animation (Hyperspeed)

The "hyperspeed" shimmer is a branded loading/thinking animation:

```css
--hyperspeed-link-blue: var(--color-token-text-link-foreground);
--hyperspeed-mid-blue: color-mix(in srgb, var(--hyperspeed-link-blue) 72%, transparent);
--hyperspeed-shimmer-pause-ms: 4.5s;
--hyperspeed-shimmer-run-ms: 4.5s;

--shimmer-contrast: rgba(255, 255, 255, 0.75);  /* dark theme */
--shimmer-text-secondary: color-mix(in srgb, var(--hyperspeed-link-blue) 55%, transparent);
```

---

## 16. Startup Screen

```css
/* Logo shimmer on dark transparent background */
--startup-background: transparent;
--startup-logo-base: #adadad;

/* Logo: 56x56px SVG, fade-in 180ms ease-out with 60ms delay */
/* Shimmer: 2200ms sweep, cubic-bezier(0.4, 0, 0.2, 1), infinite */
```

---

## 17. Quick Reference: Building a Codex Clone

### Minimum CSS Variables for Dark Theme

```css
:root {
  /* Surfaces */
  --bg-primary: #181818;
  --bg-elevated: #282828;
  --bg-deep: #000000;
  --bg-editor: #212121;

  /* Text */
  --text-primary: #ffffff;
  --text-secondary: rgba(255, 255, 255, 0.70);
  --text-tertiary: rgba(255, 255, 255, 0.50);
  --text-accent: #99ceff;

  /* Borders */
  --border-default: rgba(255, 255, 255, 0.08);
  --border-heavy: rgba(255, 255, 255, 0.16);
  --border-light: rgba(255, 255, 255, 0.04);
  --border-focus: #339cff;

  /* Brand */
  --accent-blue: #339cff;
  --accent-green: #40c977;
  --accent-red: #ff6764;
  --accent-orange: #ff8549;
  --accent-yellow: #ffd240;
  --accent-purple: #ad7bf9;

  /* Buttons */
  --btn-primary-bg: #0d0d0d;
  --btn-primary-text: #ffffff;
  --btn-secondary-bg: rgba(255, 255, 255, 0.05);

  /* Typography */
  --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  --font-mono: ui-monospace, "SFMono-Regular", "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
  --font-size-base: 13px;
  --font-size-code: 12px;
  --font-size-small: 12px;

  /* Spacing (4px base) */
  --space-unit: 4px;

  /* Radius */
  --radius-sm: 6px;
  --radius-md: 8px;
  --radius-lg: 10px;
  --radius-xl: 12px;
  --radius-2xl: 16px;
  --radius-3xl: 20px;
  --radius-4xl: 24px;

  /* Layout */
  --sidebar-width: 300px;
  --toolbar-height: 56px;
  --thread-max-width: 768px;
  --conversation-gap: 12px;

  /* Transitions */
  --transition-fast: 0.15s cubic-bezier(0.4, 0, 0.2, 1);
  --transition-relaxed: 0.3s ease;
  --transition-enter: 0.3s cubic-bezier(0.19, 1, 0.22, 1);
}
```

### Visual Signature

1. **Near-black background** (`#181818`) with subtle borders (`white 8%`)
2. **Blue accent** (`#339cff`) for links, focus rings, active states
3. **System font stack** - no custom fonts, native feel
4. **13px base text size** - slightly larger than VS Code's 12px
5. **Generous border radii** - cards at 16-24px, buttons at 10-12px
6. **Backdrop blur** - glassmorphism on elevated panels (8-16px blur)
7. **Subtle animations** - 0.15s default transitions, dialog slide-up
8. **4px spacing grid** - everything aligns to 4px increments
9. **Color-mix transparency** - borders and backgrounds use `color-mix()` for subtle alpha
10. **Shimmer effects** - branded loading animation with blue gradient sweep
