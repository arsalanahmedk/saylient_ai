# UI/UX Specification

Design language: **Aurora Chat**, a bold, colorful, dark theme with editorial serif headings and chat-bubble motifs.

## 1. Design tokens
| Token | Value |
|---|---|
| bg | `#0B0620` |
| surface | `#150C36` |
| border | `#2A1B5C` |
| primary | `#7C3AED` |
| secondary | `#FF4D8D` |
| accent | `#FFB020` |
| cyan | `#22D3EE` |
| text / muted | `#F8F5FF` / `#B7AEDB` |
| gradient | `linear-gradient(135deg,#7C3AED,#FF4D8D 60%,#FFB020)` |
| tone colors | polite `#34D399`, friendly `#FF4D8D`, firm `#FFB020`, formal `#22D3EE` |

## 2. Typography
Fraunces 700-800 (headings), Plus Jakarta Sans (body), JetBrains Mono (labels). H1 `clamp(2.75rem,7vw,5.5rem)`, H2 `clamp(2rem,4vw,3.5rem)`, body 17px / 1.7, labels 13px uppercase.

## 3. Components
- **Button primary:** gradient pill, glow, hover lift + shimmer, press scale .97.
- **Button secondary:** transparent glass, 1px border.
- **Tone chip, score meter, reply card, spotlight card, accordion, marquee.**
- Focus ring: 2px cyan, offset 3px.

## 4. Web app screens
Landing, Sign up, Login, Verify email, Dashboard, Compose/Analyze, History, Templates, Settings (tone, privacy, export/delete), Extension guide, Privacy/Terms.

## 5. Key flows
1. **Compose:** paste message -> pick tone -> see 3 replies, strategy, explanation, score -> copy.
2. **Extension:** shortcut -> side panel opens -> detected text shown (editable) -> suggestions -> copy / insert.
3. **Privacy:** Settings -> toggle history -> export / delete.

## 6. Motion
Fade-up on scroll, word-by-word hero reveal, typing + morph in chat mockup, count-up stats, marquee. Respect `prefers-reduced-motion`.

## 7. Accessibility
Contrast >= 4.5:1, touch targets >= 44 px, keyboard navigation, aria labels, visible focus, alt text, semantic HTML.

## 8. States
Loading skeletons, empty history, offline, model unavailable, rate limited, validation errors (friendly copy).
