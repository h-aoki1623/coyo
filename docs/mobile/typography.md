# Typography

Coto mobile app typography system based on the [Figma design](https://www.figma.com/design/4YmG7DmJneY2CAewswbJHT/Coto?node-id=89-1149).

## Font Families

| Language | Font | Loaded Weights |
|----------|------|----------------|
| English / Latin | Plus Jakarta Sans | Regular(400), Medium(500), SemiBold(600), Bold(700) |
| Japanese | Noto Sans JP | Regular(400), Medium(500), Bold(700) |

Fonts are loaded via `expo-font` with `@expo-google-fonts/noto-sans-jp` and `@expo-google-fonts/plus-jakarta-sans` in `App.tsx`.

## Typography Roles

Each role defines `.en` (English) and `.ja` (Japanese) variants. The only difference between the two is the font family; size, weight, and line height are shared.

| Role | Size | Weight EN | Weight JA | Line Height | Purpose |
|------|:----:|-----------|-----------|:-----------:|---------|
| `display` | 28 | Bold | Bold | Auto | Statistics numbers (turns, corrections) |
| `title` | 20 | Bold | Bold | Auto | Navigation bar screen titles |
| `headline` | 18 | Bold | Bold | Auto | Section headings, offline title |
| `bodyLarge` | 17 | SemiBold | Bold | Auto | Topic names, persona name, emphasis |
| `body` | 16 | Regular | Regular | 160% (25.6) | Chat bubbles, buttons, body text |
| `bodySmall` | 15 | Regular | Regular | 160% (24) | Record prompt, subtitles, auxiliary buttons |
| `caption` | 13 | Regular | Regular | 160% (20.8) | Explanations, subtext, stat labels |
| `captionSmall` | 12 | SemiBold | Medium | Auto | Dates, badges, section labels |

> **Note**: `bodyLarge` uses different weights for EN (SemiBold 600) and JA (Bold 700). This is intentional as Plus Jakarta Sans SemiBold is visually closer to Noto Sans JP Bold at the same size.

## Source File

`src/constants/typography.ts` exports:

- **`Fonts`** — Raw font family name strings (for edge cases)
- **`Typography`** — Role-based presets with `fontFamily`, `fontSize`, and `lineHeight`

## Usage

### Basic: Spread a preset into StyleSheet

```typescript
import { Typography } from '@/constants/typography';
import { Colors } from '@/constants/colors';

const styles = StyleSheet.create({
  // Japanese title
  greeting: {
    ...Typography.title.ja,
    color: Colors.textPrimary,
    letterSpacing: -0.3,
  },
  // English body text
  message: {
    ...Typography.body.en,
    color: Colors.textPrimary,
  },
});
```

The spread provides `fontFamily`, `fontSize`, and (for body/bodySmall/caption) `lineHeight`. Add `color`, layout, and other properties after the spread.

### Override weight for emphasis

Some components need a different weight than the preset default. Import `Fonts` alongside `Typography` and override `fontFamily`:

```typescript
import { Fonts, Typography } from '@/constants/typography';

const styles = StyleSheet.create({
  // bodySmall preset is Regular; override to Bold for emphasis
  praiseTitle: {
    ...Typography.bodySmall.ja,
    fontFamily: Fonts.notoSansJP.bold,
    color: Colors.primaryBlue,
  },
  // bodySmall preset is Regular; override to Medium for tab
  tabText: {
    ...Typography.bodySmall.ja,
    fontFamily: Fonts.notoSansJP.medium,
    color: Colors.textSecondary,
  },
});
```

### Choosing `.en` vs `.ja`

Pick the variant based on the **content language**, not the user's locale:

```typescript
// English content (AI messages, "Coto", statistics)
headerTitle: { ...Typography.bodyLarge.en, color: Colors.textPrimary },
statValue:   { ...Typography.display.en },

// Japanese content (greeting, button labels, explanations)
greeting:    { ...Typography.title.ja, color: Colors.textPrimary },
buttonLabel: { ...Typography.body.ja, color: '#FFFFFF' },
explanation: { ...Typography.caption.ja, color: Colors.textTertiary },
```