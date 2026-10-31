# Design system

One visual language for the web app, the documentation and the diagrams across all three
repositories. It aims for calm, professional B2B software with an industrial feel: generous
whitespace, restrained borders, strong tables, and no decoration that doesn't carry meaning.

## Colour

| Token | Hex | Use |
|---|---|---|
| `canvas` | `#F7F6F2` | Page background |
| `raised` | `#FFFFFF` | Cards, dialogs, sidebar |
| `surface` | `#E3E9E5` | Secondary surfaces, hover, skeletons |
| `line` / `line-strong` | `#D6DDD8` / `#B9C4BD` | Borders and input outlines |
| `ink` | `#1C2928` | Primary text |
| `ink-muted` / `ink-subtle` | `#4A5856` / `#5E6B69` | Secondary and tertiary text |
| `primary` | `#176B5B` | Primary actions, active navigation, focus rings, progress |
| `primary-soft` | `#E1EEEA` | Active navigation and selected filter backgrounds |
| `accent` | `#D9A452` | Sparingly: the "today" marker, active-nav indicator, at-risk timeline bars. Never body text. |
| Success | `#23633F` on `#E3F1E8` | Complete, approved |
| Warning | `#8A5A00` on `#FBF1DC` | At risk |
| Danger | `#B42318` on `#FDECEA` | Blocked, errors, destructive actions |
| Info | `#1F5F8B` on `#E6F0F7` | In progress, notices |

**Contrast (WCAG 2.1, computed):** ink on canvas 13.9:1 · ink-muted on canvas 6.9:1 ·
ink-subtle on canvas 5.1:1 (the lowest text pair) · white on primary 6.4:1 · primary on canvas 5.9:1 ·
warning 5.3:1 · danger 5.8:1 · success 6.2:1 · info 5.9:1. Every text pair meets AA (4.5:1).

Status is never shown by colour alone. Badges always carry a word ("Blocked", "At risk").

## Type

Geist Sans for the interface and Geist Mono for code, both self-hosted through the `geist`
package (no network request at build time). Fallbacks: Inter, then the system UI font.
Tabular figures are used for numbers in tables and metrics.

| Role | Size / weight |
|---|---|
| Page title | 24 px / 600 |
| Card title | 16 px / 600 |
| Body | 14 px / 400 |
| Labels, table headers | 14 px / 500; table headers 12 px uppercase |
| Meta text | 12 px / 400 |

## Spacing and shape

- 8-point grid: 8, 16, 24, 32 and 48 px for layout. 4 px only inside controls.
- Radius: 4 px badges, 6 px controls, 8 px cards and dialogs. No pill-shaped cards.
- One shadow for raised surfaces (`0 1px 2px` at 6% ink) and one for overlays. Borders do most of the separation.
- No gradients, no glass effects, no decorative illustrations.

## Components (`construction-ops-platform/src/components/ui`)

| Component | Notes |
|---|---|
| Navigation | Sidebar on desktop, three-column bar on mobile. The active item uses `primary-soft` with an accent indicator. |
| Card | Title, optional description and actions, optional flush body for tables |
| Table (`Table`, `Th`, `Td`) | Left-aligned text, right-aligned numbers, uppercase 12 px headers, row hover, horizontal scroll on small screens |
| Button | `btn-primary`, `btn-secondary`, `btn-ghost`, `btn-danger`, `btn-sm`. A spinner and `aria-busy` while pending. |
| Form field | Label above the input, hint below, server-side errors in one summary alert |
| Badge | Semantic tones, always with text |
| Alert | Info, success, warning, danger, with an icon |
| Dialog | Native `<dialog>`: focus trap, Escape and backdrop click close it, focus returns to the trigger. Used for forms and confirmations. |
| Empty state | Dashed outline, one sentence on what will appear and why |
| Skeleton | Loading UI for list pages only (see the Ops README on 404 status codes) |
| Icons | 14 hand-drawn 24 px stroke icons, 1.75 px stroke, `aria-hidden` |

## Diagrams

Mermaid diagrams in every README use the same palette through an init directive:

```
%%{init: {'theme':'base','themeVariables':{'primaryColor':'#E3E9E5','primaryTextColor':'#1C2928','primaryBorderColor':'#176B5B','lineColor':'#176B5B','secondaryColor':'#F7F6F2','tertiaryColor':'#FFFFFF','fontFamily':'Inter, system-ui, sans-serif'}}}%%
```

## What is deliberately absent

Product branding or a company name, stock imagery, purple "AI" styling, invented statistics,
customer logos, and deployment or usage badges.
