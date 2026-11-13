# GARI 2.0 — Design System Specification

**Aesthetic Direction**: Framed Sheet for AgriTech (`design-taste-frontend` v2, `smb-admin` archetype)  
**Palette**: Living Foliage, Earth Ochre & Clean Sheet White  
**Target Viewports**: 1440px (Desktop Operations) & 390px (Mobile Field Workbench)

---

## 1. Visual Philosophy & Anti-Slop Principles

1. **No Cosmetic AI Gradients or Glowing Cards**:
   - Software built for agriculture must convey scientific groundedness, clarity, and reliability.
   - Depth is achieved through a single subtle tone step between the tinted frame ground and the crisp white work sheet—never gratuitous box-shadows or purple AI glows.
2. **Data Carries the Chroma**:
   - The UI chrome is neutral and quiet. Color is reserved exclusively for agronomic status (Healthy Green `#1e7b4f`, Warning Rust `#92400e`, Danger Critical `#c4242a`, Water/Farm Blue `#2f70bb`).
3. **Tabular Numerics for Figures**:
   - All hectares, plot counts, quota percentages, and confidence metrics use `font-variant-numeric: tabular-nums` to maintain aligned readability across data tables.
4. **Touch-First Field Usability (390px Mobile Viewport)**:
   - Primary interactive triggers (camera upload, dropdown pickers, action buttons) enforce a minimum 44px hit-box.
   - Text inputs avoid mobile zoom triggers with minimum 16px font sizing on mobile touch targets.

---

## 2. Design Tokens & Color Palette

```css
:root {
  /* Ground & Surfaces */
  --ground: #f6f8f6;           /* Low-chroma tinted agricultural frame */
  --surface: #ffffff;          /* White work sheet with hairline border */
  --surface-muted: #f0f4f1;    /* Subtle hover and active item backgrounds */
  --raised: #e9efe9;           /* Secondary card headers and toolbar stripes */
  --border: #e2e8e2;           /* Hairline card and divider rules */
  --rule: #ecf0ec;             /* Subtle intra-list dividers */

  /* Text & Typography */
  --text-main: #141f16;        /* High-contrast deep chlorophyll ink */
  --text-secondary: #3e5242;   /* Agronomic metadata and descriptive labels */
  --text-muted: #6b8070;       /* Timestamps, hints, and placeholder text */

  /* Agronomic Semantic Accents */
  --primary: #166534;          /* Deep Forest Green (Primary Brand) */
  --primary-hover: #14532d;    /* Deep Forest Green Pressed */
  --emerald: #10b981;          /* Active growth & verified model status */
  --positive: #1e7b4f;         /* Healthy crop / Approved case */
  --warning: #92400e;          /* Suspicious symptom / Moderate risk / HTX */
  --negative: #c4242a;         /* High-risk outbreak / Severe violation */
  --info: #1b6c80;             /* Scientific note / Expert recommendation */

  /* Status Pills */
  --pill-positive-bg: #dcfae5;
  --pill-positive-ink: #04250e;
  --pill-warning-bg: #fffbeb;
  --pill-warning-ink: #92400e;
  --pill-negative-bg: #ffedea;
  --pill-negative-ink: #831c1e;

  /* Metric & Dimensions */
  --radius-card: 10px;
  --radius-control: 8px;
  --radius-sheet: 16px;
  --row-height: 48px;
  --sidebar-width: 240px;
  --control-height: 36px;
}
```

---

## 3. Typography Stack

- **Primary Typeface**: `Be Vietnam Pro`, `IBM Plex Sans`, `-apple-system`, `BlinkMacSystemFont`, `Segoe UI`, `sans-serif`.
- **Monospace & Numerics**: `IBM Plex Mono`, `monospace` for model hashes, transaction codes, and case IDs.
- **Hierarchy Scale**:
  - Page Title: 22px / 28px, Bold 700
  - Section Headings: 16px / 22px, Semi-bold 600
  - KPI Hero Numbers: 28px / 32px, Regular 500, Tabular nums
  - Body Copy: 13.5px / 20px, Regular 400
  - Micro-metadata & Badges: 11px / 14px, Semi-bold 600

---

## 4. Component Blueprints

### 4.1 Diagnosis Context Selector (`#contextSelectorContainer`)
- **Closed State**: 44px height container, displaying current context badge (🍃 Cá nhân, 🏡 Nông trại, 🏢 Hợp tác xã), bold title, and remaining quota pill.
- **Dropdown Panel**: Positioned directly beneath trigger with 1px hairline border, subtle entry animation (`fadeInDown 0.15s`), integrated live search bar with clear button (`&times;`), and segmented groupings.
- **Empty States**: If a user belongs to no cooperatives or owns zero farms, provides helpful, inviting guidance ("Chưa có nông trại nào • + Thêm nông trại mới") instead of a desolate blank box.

### 4.2 Diagnostic Results Presentation
- **Hero Confidence Meter**: Clean radial or linear bar in forest green (`#166534`) for confident classifications (>85%), warm amber (`#d97706`) for ambiguous cases (60–85%), and neutral grey for unknown leaf inputs (<60%).
- **Agronomic Safety Banner**: Persistent, clear notice reminding users that deep-learning screening assists rather than replaces on-site agronomist inspections.
