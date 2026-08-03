---
name: Forest Light Neuro-Affirming Healthcare
colors:
  surface: '#f9f9ff'
  surface-dim: '#d3daea'
  surface-bright: '#f9f9ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f0f3ff'
  surface-container: '#e7eefe'
  surface-container-high: '#e2e8f8'
  surface-container-highest: '#dce2f3'
  on-surface: '#151c27'
  on-surface-variant: '#424845'
  inverse-surface: '#2a313d'
  inverse-on-surface: '#ebf1ff'
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
  tertiary-container: '#1b1c1b'
  on-tertiary-container: '#848483'
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
  tertiary-fixed: '#e4e2e1'
  tertiary-fixed-dim: '#c7c6c5'
  on-tertiary-fixed: '#1b1c1b'
  on-tertiary-fixed-variant: '#464746'
  background: '#f9f9ff'
  on-background: '#151c27'
  surface-variant: '#dce2f3'
typography:
  headline-lg:
    fontFamily: Manrope
    fontSize: 30px
    fontWeight: '700'
    lineHeight: 40px
    letterSpacing: -0.02em
  headline-lg-mobile:
    fontFamily: Manrope
    fontSize: 24px
    fontWeight: '700'
    lineHeight: 32px
  headline-md:
    fontFamily: Manrope
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
  body-lg:
    fontFamily: Manrope
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-md:
    fontFamily: Manrope
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  label-sm:
    fontFamily: Manrope
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.05em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  base_unit: 8px
  container_max_width: 800px
  gutter: 24px
  margin_mobile: 16px
  margin_desktop: auto
---

## Brand & Style

The design system is engineered to support clinical precision within a neuro-affirming healthcare context. It prioritizes sensory-friendly interfaces that reduce cognitive load while maintaining professional authority. The aesthetic is a refined hybrid of **Minimalism** and **Modern Corporate**, utilizing a calm, nature-inspired palette to foster a sense of psychological safety for both clinicians and patients.

The emotional response is one of clarity and tranquility. By avoiding high-frequency visual patterns and aggressive shadows, the interface remains grounded and accessible. The design narrative centers on "The Guided Path"—using gentle color shifts and clear structural hierarchy to direct focus toward critical healthcare insights and session outcomes.

## Colors

The color palette is anchored in forest-inspired tonalities to evoke stability and growth. 

- **Primary Forest Green (#0B1C16)**: Used exclusively for primary actions, active navigation states, and high-level structural headings to provide a strong visual anchor.
- **Surface & Backgrounds**: The canvas uses a warm off-white (#FDFBFA) to reduce the harsh glare associated with pure white backgrounds. 
- **AI & Confidence States**: Soft Mint (#ECFDF5) and Soft Sage (#D1FAE5) indicate AI-matched content or high-confidence clinical insights, providing a subtle but clear differentiation from manual entries.
- **Clinical Alerts**: A muted Amber/Terracotta is used sparingly. It is reserved for elements requiring immediate clinical review, ensuring that "red-flag" fatigue is avoided by using a softer, yet distinct, cautionary hue.

## Typography

This design system utilizes **Manrope** for all typographic roles. Its modern, balanced proportions ensure exceptional legibility in data-dense clinical environments.

- **Headlines**: Set with tight letter-spacing and bold weights to establish clear section boundaries within the Session Log.
- **Body Text**: Optimized for long-form clinical notes with generous line heights to prevent visual crowding.
- **Labels**: Used for metadata and chip status; these are set in semi-bold with slight tracking to remain distinct at small sizes.
- **Mobile Scaling**: Headlines scale down aggressively to maintain the single-column focus without causing excessive text wrapping.

## Layout & Spacing

The design system employs a **focused single-column layout** for desktop screens (max-width 800px) to maximize clinical credibility and minimize distraction. This "centered document" approach mimics the familiarity of medical charts while optimizing for vertical scanning.

- **Grid**: A simplified 8px rhythmic grid governs all padding and margins.
- **Session Log Flow**: Items are stacked vertically with 16px to 24px gaps. 
- **Breakpoints**: 
  - **Mobile (<600px)**: Edge-to-edge cards with 16px horizontal margins.
  - **Desktop (>600px)**: Centered column with fluid side margins to maintain focus on the central narrative of the session.

## Elevation & Depth

This design system avoids heavy shadows to maintain a "light" clinical feel. 

- **Tonal Layering**: Depth is primarily communicated through color rather than shadow. The main background is #FDFBFA, while cards sit on top with a subtle 1px border (#E5E7EB).
- **Hairline Borders**: Elements are defined by crisp, 1px lines. This "low-contrast outline" approach ensures the UI feels organized but never heavy.
- **Minimal Elevation**: Only the "Active" or "Hovered" state of a card should utilize a very soft, diffused shadow (4px blur, 2% opacity) to provide tactile feedback without breaking the flat aesthetic.

## Shapes

The shape language is consistently **Rounded**, using 16px (1rem) as the standard for primary containers and cards. 

- **Cards**: 16px corner radius creates a soft, approachable container that feels less clinical and more therapeutic.
- **Chips & Buttons**: These follow a smaller 8px radius or full pill-shape to distinguish them as interactive elements within the larger cards.
- **Inputs**: 8px radius to provide a modern, friendly feel while maintaining enough structure for data entry.

## Components

- **Session Cards**: The core component. Features 16px rounded corners, a 1px #E5E7EB border, and #FDFBFA background. AI-matched cards or sections within a card transition to an #ECFDF5 background.
- **Selectable Chip Sets**: Used for categorizing session themes. These use a #D1FAE5 background when selected, with Forest Green text. Unselected states use a transparent background with a light grey border.
- **Primary Buttons**: Solid Forest Green (#0B1C16) with white text. High contrast for clear "Finish Session" or "Save" actions.
- **Input Fields**: Minimalist styling with a 1px bottom border that expands to a full 1px outline on focus.
- **Status Indicators**: Small, circular dots or subtle pill-tags. Use Sage for "Confirmed," and Amber for "Review Needed."
- **Timeline Thread**: A subtle 2px vertical line connecting session cards to visually guide the user through the chronological flow of the session log.