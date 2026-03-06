# Colors

Coyo mobile app color system based on the [Figma design](https://www.figma.com/design/4YmG7DmJneY2CAewswbJHT/Coto?node-id=89-1149).

## Architecture

Two-layer design: **Primitive** (raw palette) and **Semantic** (role-based tokens).

```
Primitive (unexported)          Semantic (exported)
─────────────────────           ───────────────────
primary.500  #3B82F6   ──────▶  buttonPrimaryBg
neutral.900  #1E293B   ──────▶  textPrimary
status.error #EF4444   ──────▶  statusError
```

- **Primitive** — Base palette values matching Figma "Color Styles > Primitive". Not exported; internal to `colors.ts`.
- **Semantic** — Role-based tokens referencing Primitives. Exported as `Colors` and consumed by all components.

> **Rule**: Components must use `Colors.semanticName`, never raw hex values or Primitive references directly.

## Primitive Palette

### Primary (Blue)

| Token | Value | Swatch |
|-------|-------|--------|
| `primary.500` | `#3B82F6` | ![#3B82F6](https://via.placeholder.com/16/3B82F6/3B82F6.png) |
| `primary.400` | `#60A5FA` | ![#60A5FA](https://via.placeholder.com/16/60A5FA/60A5FA.png) |
| `primary.300` | `#93C5FD` | ![#93C5FD](https://via.placeholder.com/16/93C5FD/93C5FD.png) |
| `primary.200` | `#BFDBFE` | ![#BFDBFE](https://via.placeholder.com/16/BFDBFE/BFDBFE.png) |
| `primary.100` | `#DBEAFE` | ![#DBEAFE](https://via.placeholder.com/16/DBEAFE/DBEAFE.png) |
| `primary.50`  | `#EFF6FF` | ![#EFF6FF](https://via.placeholder.com/16/EFF6FF/EFF6FF.png) |

### Neutral (Slate)

| Token | Value | Swatch |
|-------|-------|--------|
| `neutral.900` | `#1E293B` | ![#1E293B](https://via.placeholder.com/16/1E293B/1E293B.png) |
| `neutral.800` | `#334155` | ![#334155](https://via.placeholder.com/16/334155/334155.png) |
| `neutral.600` | `#64748B` | ![#64748B](https://via.placeholder.com/16/64748B/64748B.png) |
| `neutral.500` | `#94A3B8` | ![#94A3B8](https://via.placeholder.com/16/94A3B8/94A3B8.png) |
| `neutral.400` | `#CBD5E1` | ![#CBD5E1](https://via.placeholder.com/16/CBD5E1/CBD5E1.png) |
| `neutral.300` | `#E2E8F0` | ![#E2E8F0](https://via.placeholder.com/16/E2E8F0/E2E8F0.png) |
| `neutral.200` | `#F0F4F8` | ![#F0F4F8](https://via.placeholder.com/16/F0F4F8/F0F4F8.png) |
| `neutral.50`  | `#FAFBFD` | ![#FAFBFD](https://via.placeholder.com/16/FAFBFD/FAFBFD.png) |

### Status

| Token | Value | Swatch |
|-------|-------|--------|
| `status.success`   | `#22C55E` | ![#22C55E](https://via.placeholder.com/16/22C55E/22C55E.png) |
| `status.warning`   | `#F59E0B` | ![#F59E0B](https://via.placeholder.com/16/F59E0B/F59E0B.png) |
| `status.error`     | `#EF4444` | ![#EF4444](https://via.placeholder.com/16/EF4444/EF4444.png) |
| `status.successBg` | `#F0FDF4` | ![#F0FDF4](https://via.placeholder.com/16/F0FDF4/F0FDF4.png) |
| `status.warningBg` | `#FFFBEB` | ![#FFFBEB](https://via.placeholder.com/16/FFFBEB/FFFBEB.png) |
| `status.errorBg`   | `#FEF2F2` | ![#FEF2F2](https://via.placeholder.com/16/FEF2F2/FEF2F2.png) |

### Other

| Token | Value |
|-------|-------|
| `white` | `#FFFFFF` |

## Semantic Tokens

### Surface

| Token | Value | Primitive | Purpose |
|-------|-------|-----------|---------|
| `surfacePrimary` | `#FAFBFD` | `neutral.50` | Main screen background |
| `surfaceCard` | `#FFFFFF` | `white` | Card background |
| `surfaceElevated` | `#F0F4F8` | `neutral.200` | Elevated surfaces, badge backgrounds |
| `borderDefault` | `#E2E8F0` | `neutral.300` | Default border |
| `borderSubtle` | `#F0F4F8` | `neutral.200` | Card / subtle border |

### Text

| Token | Value | Primitive | Purpose |
|-------|-------|-----------|---------|
| `textPrimary` | `#1E293B` | `neutral.900` | Primary body text, headings |
| `textSecondary` | `#64748B` | `neutral.600` | Secondary text, descriptions |
| `textTertiary` | `#94A3B8` | `neutral.500` | Placeholder, muted text |
| `textInverse` | `#FFFFFF` | `white` | Text on dark/colored backgrounds |

### Button

| Token | Value | Primitive | Purpose |
|-------|-------|-----------|---------|
| `buttonPrimaryBg` | `#3B82F6` | `primary.500` | Primary button background |
| `buttonGhostText` | `#3B82F6` | `primary.500` | Ghost button text color |
| `buttonGhostBorder` | `#BFDBFE` | `primary.200` | Ghost button border |
| `buttonDangerText` | `#EF4444` | `status.error` | Danger button text |
| `buttonDangerBg` | `#FEF2F2` | `status.errorBg` | Danger button background |

### Chat

| Token | Value | Primitive | Purpose |
|-------|-------|-----------|---------|
| `chatAiBubbleBg` | `#FFFFFF` | `white` | AI message bubble background |
| `chatAiBubbleBorder` | `#F0F4F8` | `neutral.200` | AI message bubble border |

### Correction

| Token | Value | Primitive | Purpose |
|-------|-------|-----------|---------|
| `correctionHighlightText` | `#166534` | (direct) | Corrected word text |
| `correctionHighlightBg` | `#BBF7D0` | (direct) | Corrected word background |

### Topic

| Token | Value | Purpose |
|-------|-------|---------|
| `topicSports` | `#2563EB` | Sports topic icon/text |
| `topicSportsBg` | `#DBEAFE` | Sports topic card background |
| `topicBusiness` | `#16A34A` | Business topic icon/text |
| `topicBusinessBg` | `#DCFCE7` | Business topic card background |
| `topicPolitics` | `#7C3AED` | Politics topic icon/text |
| `topicPoliticsBg` | `#EDE9FE` | Politics topic card background |
| `topicTechnology` | `#DC2626` | Technology topic icon/text |
| `topicTechnologyBg` | `#FEE2E2` | Technology topic card background |
| `topicEntertainment` | `#D97706` | Entertainment topic icon/text |
| `topicEntertainmentBg` | `#FEF3C7` | Entertainment topic card background |

### Status

| Token | Value | Primitive | Purpose |
|-------|-------|-----------|---------|
| `statusSuccess` | `#22C55E` | `status.success` | Success icon, positive indicator |
| `statusWarning` | `#F59E0B` | `status.warning` | Warning icon, caution indicator |
| `statusError` | `#EF4444` | `status.error` | Error icon, negative indicator |
| `statusSuccessBg` | `#F0FDF4` | `status.successBg` | Success background |
| `statusWarningBg` | `#FFFBEB` | `status.warningBg` | Warning background |
| `statusErrorBg` | `#FEF2F2` | `status.errorBg` | Error background |

### Accent

| Token | Value | Primitive | Purpose |
|-------|-------|-----------|---------|
| `accentBg` | `#EFF6FF` | `primary.50` | Info cards, pressed states |
| `accentBorder` | `#BFDBFE` | `primary.200` | Accent borders (cards, banners) |
| `accentMuted` | `#60A5FA` | `primary.400` | Waveform bars, decorative elements |

### Misc

| Token | Value | Primitive | Purpose |
|-------|-------|-----------|---------|
| `chevron` | `#CBD5E1` | `neutral.400` | Navigation chevron icons |

## Source File

`src/constants/colors.ts` exports:

- **`Colors`** — Semantic role-based tokens (the only export; use this in all components)

The `Primitive` const is intentionally unexported to enforce semantic usage.

## Usage

### Basic: Use semantic tokens in StyleSheet

```typescript
import { Colors } from '@/constants/colors';

const styles = StyleSheet.create({
  container: {
    backgroundColor: Colors.surfacePrimary,
  },
  heading: {
    color: Colors.textPrimary,
  },
  description: {
    color: Colors.textSecondary,
  },
});
```

### Buttons

```typescript
const styles = StyleSheet.create({
  primaryButton: {
    backgroundColor: Colors.buttonPrimaryBg,
  },
  primaryButtonText: {
    color: Colors.textInverse,
  },
  dangerButton: {
    backgroundColor: Colors.buttonDangerBg,
    borderColor: Colors.statusError,
  },
  dangerButtonText: {
    color: Colors.buttonDangerText,
  },
});
```

### Topic cards

```typescript
// Each topic has a foreground (icon/text) and background pair
const styles = StyleSheet.create({
  sportsCard: {
    backgroundColor: Colors.topicSportsBg,
  },
  sportsLabel: {
    color: Colors.topicSports,
  },
});
```

### Status indicators

```typescript
const styles = StyleSheet.create({
  successBanner: {
    backgroundColor: Colors.statusSuccessBg,
    borderColor: Colors.statusSuccess,
  },
  errorBanner: {
    backgroundColor: Colors.statusErrorBg,
    borderColor: Colors.statusError,
  },
});
```

## Adding New Colors

1. If the color is a new base hue, add it to `Primitive` (unexported).
2. Create a semantic token in `Colors` that references the Primitive.
3. Name the token as `{category}{Role}` (e.g., `buttonSecondaryBg`, `textLink`).
4. Update this document with the new token.

> **Never** add raw hex values directly to `Colors` unless there is no logical Primitive grouping (like the correction highlight colors).
