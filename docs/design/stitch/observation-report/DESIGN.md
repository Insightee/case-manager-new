---
name: Forest Light High-Contrast
colors:
  surface: '#f9f9f9'
  surface-dim: '#dadada'
  surface-bright: '#f9f9f9'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f3f3f4'
  surface-container: '#eeeeee'
  surface-container-high: '#e8e8e8'
  surface-container-highest: '#e2e2e2'
  on-surface: '#1a1c1c'
  on-surface-variant: '#424845'
  inverse-surface: '#2f3131'
  inverse-on-surface: '#f0f1f1'
  outline: '#737875'
  outline-variant: '#c2c8c3'
  surface-tint: '#50625a'
  primary: '#000000'
  on-primary: '#ffffff'
  primary-container: '#0e1f19'
  on-primary-container: '#75887f'
  inverse-primary: '#b7cbc1'
  secondary: '#416656'
  on-secondary: '#ffffff'
  secondary-container: '#c3ecd7'
  on-secondary-container: '#476c5b'
  tertiary: '#000000'
  on-tertiary: '#ffffff'
  tertiary-container: '#002114'
  on-tertiary-container: '#069669'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#d3e7dd'
  primary-fixed-dim: '#b7cbc1'
  on-primary-fixed: '#0e1f19'
  on-primary-fixed-variant: '#394a43'
  secondary-fixed: '#c3ecd7'
  secondary-fixed-dim: '#a8cfbc'
  on-secondary-fixed: '#002115'
  on-secondary-fixed-variant: '#294e3f'
  tertiary-fixed: '#85f8c4'
  tertiary-fixed-dim: '#68dba9'
  on-tertiary-fixed: '#002114'
  on-tertiary-fixed-variant: '#005137'
  background: '#f9f9f9'
  on-background: '#1a1c1c'
  surface-variant: '#e2e2e2'
typography:
  headline-lg:
    fontFamily: Manrope
    fontSize: 40px
    fontWeight: '700'
    lineHeight: 48px
    letterSpacing: -0.02em
  headline-lg-mobile:
    fontFamily: Manrope
    fontSize: 30px
    fontWeight: '700'
    lineHeight: 36px
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Manrope
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  body-lg:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '400'
    lineHeight: 28px
  body-md:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  label-sm:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.05em
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  base: 8px
  gutter: 24px
  margin-mobile: 16px
  margin-desktop: 40px
  sidebar-width: 280px
---

## Brand & Style
This design system balances the authoritative weight of a deep forest palette with the pristine clarity of a high-contrast light mode. It is designed for professional environments—such as high-end SaaS, environmental consulting, or legal tech—where legibility and structural hierarchy are paramount.

The design style is **Minimalist with Tactile Accents**. It relies on expansive white space and a rigid grid to maintain order, while using deep saturated containers in the sidebar to anchor the navigation. The aesthetic response should feel organized, premium, and calm, utilizing subtle glass effects only for floating overlays to maintain a grounded, professional atmosphere.

## Colors
The palette is centered on a high-contrast foundation. The main surface is a pure `#ffffff`, ensuring maximum readability and a clean "canvas" feel. 

- **Primary Forest (#0b1c16):** Reserved for high-authority surfaces like the primary sidebar and heavy-weight buttons. 
- **Soft Mint (#d1fae5):** Used exclusively for selection states, highlights, and subtle background accents to provide a gentle visual resting place.
- **Accents:** Active icons or success states utilize a more vibrant emerald to bridge the gap between the deep forest and light mint.
- **Typography:** Contrast is strictly maintained with deep slate and charcoal tones to prevent eye strain on the white background.

## Typography
The typography system uses a tiered approach to distinguish between navigation, content, and metadata. 

**Manrope** is used for headlines to provide a modern, slightly rounded but professional geometric feel. **Inter** serves as the primary workhorse for body text, optimized for long-form reading on light surfaces. **JetBrains Mono** is utilized for labels and technical data, providing a structured, utilitarian contrast to the humanist body text. All headings should use the primary forest green or near-black slate to maintain a strong visual hierarchy.

## Layout & Spacing
The design system employs a **Fixed Grid** on desktop (12 columns) and a **Fluid Grid** on mobile (4 columns). 

The sidebar is a constant anchor at 280px, utilizing the deep forest green background to separate navigation from the main workspace. Main content is housed within a container with a maximum width of 1440px to ensure line lengths remain readable. Spacing follows a strict 8px linear scale, with 24px (3 units) being the default gutter between logical sections.

## Elevation & Depth
Depth is created primarily through **Tonal Layers** rather than heavy shadows. 

1. **Level 0 (Base):** Pure white (#ffffff) for the main workspace.
2. **Level 1 (Navigation):** Deep forest green (#0b1c16) for sidebars, providing a hard visual boundary.
3. **Level 2 (Cards/Inputs):** Defined by low-contrast outlines (#e2e8f0).
4. **Level 3 (Popovers/Modals):** Subtle ambient shadows (0px 10px 30px rgba(0,0,0,0.05)) with a background blur (8px) to signify temporary interaction layers.

## Shapes
This design system utilizes **Soft** roundedness. The 0.25rem (4px) base radius ensures that the UI feels contemporary and approachable without losing its professional, "square" architectural integrity. Larger components like cards or modals scale to 0.75rem (12px) to soften their impact against the high-contrast white background.

## Components
- **Buttons:** Primary buttons use the Forest Green background with white text. Secondary buttons use the Soft Mint background with Forest Green text.
- **Sidebar Items:** Default state is transparent; active state uses a subtle opacity shift or a left-border accent in Mint. Text in the sidebar should be light grey or white.
- **Input Fields:** Use a white background with a 1px slate border. On focus, the border transitions to Forest Green with a soft Mint outer glow.
- **Selection/Chips:** Use the Soft Mint (#d1fae5) background with the Primary Forest (#0b1c16) text for high legibility.
- **Lists:** Rows are separated by thin `#e2e8f0` borders. Hover states utilize a 50% opacity version of the Mint highlight.
- **Cards:** No background color (remains #ffffff) but defined by a light border to maintain the minimalist aesthetic.

---

## Agent implementation mandate (Observation Report)

**Source HTML is law.** For observation builder, preview, goals, and strategies:

| Do | Do not |
|----|--------|
| Copy Tailwind `className` strings from `observation_report_*/code.html` | Invent card grids, stat widgets, or new CSS namespaces (`fl-ob-*`, `ob-*`) |
| Use `@theme` tokens in `forest-light-theme.css` + utilities in `forest-light-observation.css` | Re-translate Stitch into a parallel custom stylesheet |
| Import observation CSS globally via `index.css` + route file | Rely on hub-only side imports |
| Keep `CaseProfileShell` / reports tab navigation | Rebuild Stitch full-page sidebar or top app header |
| Wire buttons to existing API handlers | Add placeholder lorem or fake demo goals/strategies in UI |
| Compare output to `screen.png` before merge | “Improve” layout with dashboard patterns |

See [`SCREEN_REFERENCE.md`](SCREEN_REFERENCE.md) for screen → component map and visual verification checklist.