# Four Puzzle — Claude Code Task File

## Overview
Rebuild `daily/index.html` as a proper Wordle-style 5×5 grid puzzle based on the
"four is the magic number" mechanic. Reorganize site structure so the daily puzzle
is the main landing page, with the explorer (`index.html`) accessible as `/magic`.
Add a first-visit onboarding modal that teaches the mechanic before revealing the puzzle.

**All work is vanilla HTML/CSS/JS — no framework, no build step.**
The existing visual design language (dark theme, Cinzel + JetBrains Mono fonts, gold
tokens) must be preserved and extended consistently across all pages.

---

## File Structure (target state)

```
/
├── index.html          ← REBUILD: daily puzzle (main landing page)
├── magic/
│   └── index.html      ← MOVE: current index.html goes here (explorer, mostly untouched)
├── daily/
│   └── index.html      ← DELETE or leave as redirect to /
├── vercel.json         ← UPDATE: routing rules
├── main.py             ← leave untouched
└── requirements.txt    ← leave untouched
```

---

## Step 1 — Move the Explorer

1. Create `magic/index.html` — copy current `index.html` content exactly.
2. In `magic/index.html`, update the eyebrow/back link to point to `/` with text
   `← daily puzzle`.
3. Leave all other logic untouched.

---

## Step 2 — Update vercel.json

```json
{
  "buildCommand": null,
  "outputDirectory": ".",
  "framework": null,
  "rewrites": [
    { "source": "/magic", "destination": "/magic/index.html" },
    { "source": "/daily", "destination": "/index.html" }
  ]
}
```

---

## Step 3 — Rebuild index.html (Daily Puzzle)

Replace root `index.html` entirely. Sections below define every part.

### 3a — Core Chain Logic (shared JS module, inline in `<script>`)

```js
// ── Number → Words ──────────────────────────────────────────────
const ONEs = ['zero','one','two','three','four','five','six','seven',
  'eight','nine','ten','eleven','twelve','thirteen','fourteen','fifteen',
  'sixteen','seventeen','nineteen','eighteen','nineteen'];
const TENs = ['','','twenty','thirty','forty','fifty','sixty','seventy','eighty','ninety'];

function toWords(n) {
  if (n < 0)    return 'negative ' + toWords(-n);
  if (n < 20)   return ONEs[n];
  if (n < 100)  { const t=TENs[Math.floor(n/10)],o=n%10; return o?t+'-'+ONEs[o]:t; }
  if (n < 1000) { const h=Math.floor(n/100),r=n%100; return ONEs[h]+' hundred'+(r?' '+toWords(r):''); }
  if (n < 10000){ const k=Math.floor(n/1000),r=n%1000; return toWords(k)+' thousand'+(r?' '+toWords(r):''); }
  return n.toString();
}

function letterCount(n) {
  return toWords(Math.abs(n)).replace(/[^a-z]/gi,'').length;
}

function buildChain(n) {
  const steps=[], seen=new Set();
  let cur=n;
  while(true) {
    if(seen.has(cur)||steps.length>30) break;
    seen.add(cur);
    const cnt=letterCount(cur);
    steps.push({value:cur, count:cnt});
    if(cnt===4) break;
    cur=cnt;
  }
  return steps; // each step: { value: number, count: number }
  // steps[i].count === steps[i+1].value (the chain link)
}
```

### 3b — Daily Puzzle Generation

```js
// ── Seeded PRNG (Mulberry32) ─────────────────────────────────────
function mulberry32(seed) {
  return function() {
    seed |= 0; seed = seed + 0x6D2B79F5 | 0;
    let t = Math.imul(seed ^ seed >>> 15, 1 | seed);
    t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
    return ((t ^ t >>> 14) >>> 0) / 4294967296;
  };
}

// ── Day number (UTC) ─────────────────────────────────────────────
const EPOCH = new Date('2025-01-01T00:00:00Z').getTime();
function getDayNumber() {
  return Math.floor((Date.now() - EPOCH) / 86400000);
}

function todayStr() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
}

// ── Puzzle Generation ────────────────────────────────────────────
// PuzzleRow: { cells: number[5], blanks: number[] (indices), difficulty: 1–5 }

const BLANK_PATTERNS = [
  [3, 4],   // row 1 — easiest, rightmost blanks (forward compute)
  [1, 4],   // row 2
  [0, 3],   // row 3
  [0, 2],   // row 4
  [0, 1],   // row 5 — hardest, leftmost blanks (reverse lookup)
];

function generatePuzzle(dayNumber) {
  const rng = mulberry32(dayNumber * 1000003 + 7919);

  // Build candidate pool: starting numbers whose chains have 6+ distinct steps
  // (so we can always pull a clean 5-cell window)
  const candidates = [];
  for (let n = 10; n <= 9999; n++) {
    const chain = buildChain(n);
    // Must be long enough and not trivially short
    if (chain.length < 6) continue;
    // Collect all possible 5-cell windows from this chain (excluding terminal 4)
    const usable = chain.filter(s => s.value !== 4);
    for (let start = 0; start <= usable.length - 5; start++) {
      const segment = usable.slice(start, start + 5).map(s => s.value);
      // All values distinct
      if (new Set(segment).size !== 5) continue;
      // No value equals 4
      if (segment.includes(4)) continue;
      // No value is 0 or negative
      if (segment.some(v => v <= 0)) continue;
      candidates.push(segment);
    }
  }

  // Pick 5 unique candidates (one per row) using seeded RNG
  const rows = [];
  const usedStarts = new Set();
  let attempts = 0;
  while (rows.length < 5 && attempts < 10000) {
    attempts++;
    const idx = Math.floor(rng() * candidates.length);
    const seg = candidates[idx];
    const key = seg[0];
    if (usedStarts.has(key)) continue;
    usedStarts.add(key);
    rows.push({
      cells: seg,
      blanks: BLANK_PATTERNS[rows.length],
      difficulty: rows.length + 1,
    });
  }

  return rows;
}
```

### 3c — Validation Logic

```js
// A guessed value g at blank index i is correct when:
// - Left neighbor exists and letterCount(left) === g  (g is what left maps to)
// - Right neighbor exists and letterCount(g) === right (g maps to right)
// Both conditions apply when both neighbors are present.

function validateGuess(cells, blanks, index, guessedValue) {
  const left  = index > 0    ? cells[index - 1] : null;
  const right = index < 4    ? cells[index + 1] : null;
  let ok = true;
  if (left  !== null && !blanks.includes(index - 1)) ok = ok && (letterCount(left) === guessedValue);
  if (right !== null && !blanks.includes(index + 1)) ok = ok && (letterCount(guessedValue) === right);
  return ok;
}
```

### 3d — localStorage Schema

```js
// Key: "four-puzzle-YYYY-MM-DD"
// Value (JSON):
// {
//   date: string,
//   rowResults: Array<'solved' | 'solved-mistakes' | 'failed' | 'pending'>,
//   guesses: number[][]  // per-row guess history (for mistake tracking)
//   completed: boolean,
//   score: number  // 0–5
// }

const STORAGE_KEY = () => `four-puzzle-${todayStr()}`;
const ONBOARD_KEY = 'four-onboarded';
```

---

## Step 4 — UI Spec

### 4a — Design Tokens
Reuse all CSS variables from the existing pages:
```css
--bg: #06060e; --surface: #0b0b18; --border: #1c1c30;
--gold: #c9a84c; --gold-hi: #f0cc70; --gold-lo: #7a6030;
--text: #ddd4bc; --muted: #6a6250; --dim: #2e2c24;
--green: #4ecb8d; --yellow: #c9a84c; --red: #e06060;
--glow: 0 0 18px rgba(201,168,76,0.35), 0 0 60px rgba(201,168,76,0.12);
```
Include ghost "4" background element, scanlines overlay, noise overlay — same as
existing pages.
Include same Google Fonts: Cinzel + JetBrains Mono.

### 4b — Page Layout

```
┌─────────────────────────────────┐
│  eyebrow: "FOUR · #[day]"       │
│  h1: Daily Four                 │
│  date: YYYY-MM-DD               │
├─────────────────────────────────┤
│  ROW 1  [ ]→[11]→[ ]→[3]→[5]  ✓│
│  ROW 2  [  ]→[  ]→[  ]→[  ]→[]│
│  ROW 3  ...                     │
│  ROW 4  ...                     │
│  ROW 5  ...                     │
├─────────────────────────────────┤
│  END STATE (hidden until done)  │
│  Score: X/5                     │
│  🟩🟨🟥🟩🟩                      │
│  [Copy Result] [New puzzle in X]│
├─────────────────────────────────┤
│  footer: "how does this work? →"│
│          christopherjharper.com │
└─────────────────────────────────┘
```

### 4c — Row Component

Each row:
- 5 cells (56×56px on desktop, 48×48px on mobile) connected by `→` arrows
- **Given cell**: `background: var(--surface)`, muted border, shows number, not editable
- **Blank cell**: white/light background, prominent border, number `<input>`, editable
- **Check button** (right of row): "Check" — validates all blanks in the row simultaneously
- On **correct**: all cells flip green (same tile-flip animation as existing daily page),
  checkmark appears, row locked
- On **incorrect**: red shake animation on wrong cells, wrong guess attempt counted
- After first incorrect: "Reveal" button appears alongside "Check"
- On **Reveal**: show answer in muted italic, mark row as failed, lock row

Blank input constraints:
- `type="number"`, `min="1"`, `max="9999"`
- Strip leading zeros on blur
- On mobile: numeric keyboard (`inputmode="numeric"`)
- Enter key on last blank in a row = submit that row

### 4d — Row State Machine

```
pending → checking → correct   (green, locked)
                   → incorrect → pending (shake, attempt+1)
                              → revealed (on Reveal click, locked, muted)
```

Track per-row: `{ state, attempts, revealed }`

### 4e — End State

Shown after all 5 rows are either correct, incorrect-revealed, or revealed:

```
Score: 4/5

🟩🟨🟥🟩🟩

FOUR #[day_number]
4/5 · fourpuzzle.com

[Copy Result]    [Next puzzle in 08:42:17]
```

Emoji key:
- 🟩 = solved, no wrong guesses
- 🟨 = solved, had at least one wrong guess
- 🟥 = failed / revealed

Countdown timer: live, updates every second, counts down to midnight UTC.

Share text:
```
FOUR #[day_number]
🟩🟨🟥🟩🟩
[score]/5 · fourpuzzle.com
```

### 4f — Footer Links

```
how does this work? →          ← links to /magic
christopherjharper.com
```

---

## Step 5 — Onboarding Modal

### Trigger
- Check `localStorage.getItem('four-onboarded')` on load
- If not set: show modal before puzzle is visible (puzzle renders behind it)
- If set: skip modal entirely, show puzzle immediately
- Share links: no special param needed — localStorage handles it per-device

### Modal Structure (3 steps, no back button)

**Step 1 — The Explorer**
```
Title: "Before you play..."
Body:  Small interactive explorer (same logic as /magic page, mini version).
       "Try entering a number:"
       [input] [→] chain output renders inline
       "Try a few. Notice anything?"
       [Continue →] button (enabled after user tries at least 1 number)
```

**Step 2 — The Question**
```
Title: "One question."
Body:  "Every number eventually leads to 4.
        What makes 4 different from all other numbers?"

       Four answer buttons:
       [ It's even ]
       [ It's the smallest number with letters ]
       [ It's the only number whose letter count equals itself ]   ← correct
       [ It sounds like 'for' ]

       On wrong answer: button flashes red, stays selectable, try again.
       On correct: button flashes green, "That's it." message, [Play →] appears.
```

**Step 3 — Dismissed**
```
On [Play →] click:
- localStorage.setItem('four-onboarded', '1')
- Modal fades out
- Puzzle fades in
```

### Modal Styling
- Full-screen overlay, `backdrop-filter: blur(8px)`
- Dark modal card, max-width 460px, centered
- Same font/color tokens as rest of site
- Smooth fade transition in/out
- NOT dismissible by clicking outside or pressing Escape (must complete it)

---

## Step 6 — Saved State / Replay Prevention

On page load (after modal check):
1. Read `localStorage.getItem(STORAGE_KEY())`
2. If exists and `completed: true`: skip to end state, show score card
3. If exists and `completed: false`: restore partial progress (restore which rows
   are solved/failed, re-lock those rows, focus next pending row)
4. If not exists: fresh puzzle

Save to localStorage after every row completion (correct, revealed, or failed).
Mark `completed: true` when all 5 rows are in a terminal state.

---

## Step 7 — Mobile Polish

- Viewport: `width=device-width, initial-scale=1.0`
- Cell inputs: `inputmode="numeric"` pattern="[0-9]*"`
- Row scrolls horizontally if needed on very small screens (min-width: 320px support)
- Check/Reveal buttons stack below cells on screens < 400px
- Onboarding modal: full-screen on mobile (no border radius, no margin)
- Touch targets minimum 44×44px

---

## What NOT to change

- `/magic/index.html` logic — only update the back link
- `vercel.json` structure beyond the rewrites addition
- `main.py` and `requirements.txt`
- The existing CSS design tokens and visual aesthetic

---

## Definition of Done

- [x] `/` loads the daily puzzle (same puzzle for all users on a given day)
- [x] First-time visitors see the onboarding modal; returning visitors skip it
- [x] All 5 rows render with correct blank placement per difficulty pattern
- [x] Validation correctly accepts any valid number for reverse-lookup blanks
- [x] Green flip animation on correct rows, red shake on wrong guesses
- [x] Reveal shows answer and locks row
- [x] End state shows score emoji grid and copy-to-clipboard share text
- [x] Countdown timer to next puzzle
- [x] localStorage saves and restores partial/complete daily state
- [x] `/magic` loads the explorer with back link to `/`
- [x] Vercel routing works for `/magic` and `/daily` (redirects to `/`)
- [x] Mobile layout is clean at 375px viewport width
- [x] No frameworks, no build step, no external dependencies beyond Google Fonts

**Completed.** Filter condition updated to `max(seg) <= 9999`.
