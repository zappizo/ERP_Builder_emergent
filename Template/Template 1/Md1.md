# UI Technical Specification: Finance Analytics Dashboard
**Concept by:** Bogdan Nikitin (Nixtio)

## 🖥️ Layout Architecture
- **Sidebar:** Fixed left position (`position: sticky`), width `260px`.
- **Top Bar:** Flexbox container for Search (left) and User Actions (right).
- **Grid System:** - Top: 3-column `1fr` grid for KPI Metrics.
    - Middle: `2/3` width for Main Chart, `1/3` for Portfolio Donut.
    - Bottom: Full width or `2/3` width for Transaction Table.

## 🎨 CSS Design Tokens
| Variable | Value | Usage |
| :--- | :--- | :--- |
| `--bg-main` | `#0B0E14` | Body Background |
| `--bg-card` | `rgba(22, 27, 34, 0.8)` | Card Surfaces (Glassmorphism) |
| `--border` | `#21262D` | Divider and Card Strokes |
| `--primary` | `#3B82F6` | Primary Buttons / Active States |
| `--font-main` | `'Inter', sans-serif` | Global Typography |

## 🧩 Component Details

### 1. KPI Cards
- **Effect:** Suble hover lift (`transform: translateY(-4px)`).
- **Trend Pills:** - Up: Background `rgba(16, 185, 129, 0.1)`, Text `#10B981`.
    - Down: Background `rgba(239, 68, 68, 0.1)`, Text `#EF4444`.

### 2. Analytics Chart (Area Chart)
- **Grid Lines:** Horizontal lines only, color `#21262D`.
- **Gradient Fill:** From `rgba(59, 130, 246, 0.3)` to `transparent`.
- **Interactivity:** Tooltip should follow the cursor with a blur effect (`backdrop-filter: blur(8px)`).

### 3. Transactions Table
- **Header:** Sticky header with uppercase muted text.
- **Rows:** Zebra striping or `1px` bottom border.
- **Avatar:** `32px x 32px` rounded circle for vendor logos.

## 📱 Responsiveness Requirements
- **Desktop:** Full layout as designed.
- **Tablet:** Sidebar minimizes to icons (72px width).
- **Mobile:** Sidebar hidden (accessible via Burger menu), Metric cards stack vertically.