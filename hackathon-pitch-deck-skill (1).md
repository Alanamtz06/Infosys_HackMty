---
name: hackathon-pitch-deck
description: "Use this skill when the user asks to build a pitch deck for a hackathon, app demo, or product presentation in WWDC/Apple Keynote-style. Trigger when user says: 'pitch deck', 'presentación de hackathon', 'keynote para mi app', 'slides para presentar', 'WWDC-style deck', or references building a .pptx/.key for a software project. The output is a .pptx (Office format, opens in Keynote, PowerPoint, LibreOffice) generated programmatically with pptxgenjs + animation injection. This is NOT for normal corporate slides — it's specifically for tech product pitches with iPhone mockups, framework logos, dramatic typography, and Magic Move transitions."
---

# Hackathon Pitch Deck Skill

Generates polished WWDC-style pitch decks for software products, hackathons, and app demos. Output is a `.pptx` that opens cleanly in Keynote, PowerPoint, or LibreOffice.

## When to use

- User is preparing a 5-15 minute pitch for a hackathon, demo day, or investor meeting.
- The deck needs iPhone mockups (with screenshots framed), Apple framework logos, big typography, and dramatic moments.
- User wants programmatic control: edit code, regenerate the .pptx, iterate fast.
- User wants Magic Move / fade / push transitions between slides.

**Don't use for:** normal corporate slides, financial reports, status updates, anything where you'd start from a corporate template.

## Architecture

```
project/
├── build.js                    # main: defines slides with pptxgenjs
├── add-animations.py           # injects <p:transition> XML per slide
├── compose.js                  # composes screenshots into iPhone frame
├── gen-icons.py                # (optional) generates custom isometric framework icons
├── assets/
│   ├── iphone-frame.png        # transparent iPhone frame (1470x3000)
│   ├── apple-logos/            # official Apple framework logos
│   └── ...
├── screenshots/
│   ├── raw/                    # raw simulator screenshots
│   └── *-framed.png            # composed (iPhone frame + screenshot)
└── output.pptx                 # final deck
```

## Iteration loop

```bash
node build.js                                              # regenerate .pptx
python3 add-animations.py                                  # inject transitions
soffice --headless --convert-to pdf output.pptx           # for visual QA
pdftoppm -jpeg -r 100 output.pdf slide                    # JPG per slide
# Visual QA via subagent (see below)
```

## Step 1 — Get the pitch script first

Before writing any code, ask the user for:
- The pitch script or 1-2 minute description of the product.
- Number of slides target (rule of thumb: 1 slide per 15-25 seconds, so 10-min pitch = ~25-40 slides).
- Brand color or palette (default: Apple-style with one bold accent).
- Whether they have screenshots ready (or the app builds in Xcode).

The script drives everything. Don't start designing slides without it.

## Step 2 — Slide structure (recommended)

A WWDC-style pitch follows this beat:

1. **Hero** (1 slide) — name + 1-line tagline + app icon
2. **Hook** (3-4 slides) — emotional question, dramatic phrase, build suspense
3. **Problem** (3-7 slides) — big stat, human angle, fears/quotes
4. **Proto-persona** (3-5 slides) — story of one user, paso a paso (Magic Move)
5. **Insight** (1-2 slides) — pivot from problem to solution, dark bg
6. **Solution headline** (1 slide) — name + 3-word formula
7. **Three moments** (3 slides) — full-bleed colored backgrounds
8. **Demos** (8-15 slides) — one feature per slide, iPhone framed screenshot
9. **Tech stack** (1-2 slides) — Apple framework logos grid, dark bg
10. **HCAI / Privacy** (1-2 slides) — principles
11. **Value for sponsor/business** (3-5 slides) — dashboard, KPIs, ROI
12. **Bento** (1 slide) — everything-in-one summary
13. **Cierre** (1 slide) — emotional close, no "thanks" slide

## Step 3 — Use the templates

Copy from `~/.claude/skills/hackathon-pitch-deck/templates/` to the project directory:

```bash
cp ~/.claude/skills/hackathon-pitch-deck/templates/build.js .
cp ~/.claude/skills/hackathon-pitch-deck/templates/add-animations.py .
cp ~/.claude/skills/hackathon-pitch-deck/templates/compose.js .
npm install pptxgenjs
```

The `build.js` template has:
- Palette object (PAL) with WWDC-friendly colors
- Helper functions: `bg`, `eyebrow`, `title`, `caption`, `card`, `phone`, `footer`
- 5 sample slide types: hero, full-bleed colored, demo with phone, tech stack with logos, bento

Modify slide-by-slide. Don't fight the helpers — they encode lessons learned about font sizes, margins, and contrast.

## Step 4 — Apple framework logos

Bajar oficiales de Apple developer:

```bash
mkdir -p assets/apple-logos
cd assets/apple-logos
for fw in swiftui healthkit swiftdata watchos widgetkit apple-intelligence cloudkit avfoundation sirikit activitykit; do
  curl -sSL -o "$fw-96x96_2x.png" "https://developer.apple.com/assets/elements/icons/$fw/$fw-96x96_2x.png"
done
```

Algunos frameworks no tienen logo oficial separado (ej. Foundation Models, Speech). Sustitutos válidos:
- Foundation Models → Apple Intelligence
- Speech → SiriKit
- Live Activities → ActivityKit

## Step 5 — iPhone frames

El frame transparente (`iphone-frame.png` en `templates/assets/`) es 1470x3000 con screen rect en (75, 66, 1319, 2867). Para componer un screenshot:

```bash
node compose.js screenshots/raw/foo.png screenshots/foo-framed.png
```

Screenshots del simulador iOS típicamente vienen en aspect 0.46 (iPhone 17 Pro: 1206x2622), que coincide con el screen rect del frame.

## Step 6 — Fonts

**Default:** Helvetica Neue (preinstalado en macOS, garantizado).

**Si la app usa fuentes custom (ej. Poppins):**
1. Instalar las TTF en `~/Library/Fonts/` antes de generar.
2. Si la fuente tiene variantes Italic, descargar también de Google Fonts:
   ```bash
   curl -sSL -o ~/Library/Fonts/Poppins-Italic.ttf https://github.com/google/fonts/raw/main/ofl/poppins/Poppins-Italic.ttf
   ```
3. Cambiar `FONT_HEAD` y `FONT_BODY` en `build.js`.

**Cuidado:** comillas tipográficas en italic pueden generar artefactos en LibreOffice render. Si pasa, usar comillas rectas o quitar italic.

## Step 7 — Animaciones (Magic Move)

`add-animations.py` inyecta XML `<p:transition>` después de generar el .pptx. Tipos disponibles:

- `fade` — para slides reflexivas (hero, insight, cierre)
- `push` — para listas y demos
- `morph` — Magic Move; PowerPoint 365 y Keynote lo soportan, los elementos comunes entre slides consecutivos animan suavemente

**Para que Magic Move funcione bien:**
- Slides consecutivos deben tener elementos del mismo nombre/posición/forma.
- Ejemplo: 3 slides de Mariana proto-persona con la silueta en la misma posición y solo el texto cambia → morph hace zoom suave entre frames.
- Ejemplo: 3 slides verde/amarillo/rojo del umbral → morph anima el cambio de color de fondo.

## Step 8 — QA visual obligatorio

**No declares done sin QA visual.** Render todos los slides como JPG y pasa por subagent:

```bash
soffice --headless --convert-to pdf output.pptx
pdftoppm -jpeg -r 100 output.pdf slide
```

Luego invoca un subagent (Explore o general-purpose) con prompt tipo:

```
Visually inspect <N> slides of a pitch deck. Find issues:
- Text cut off at edges
- Overlapping elements
- Mid-word line breaks
- Floating commas/quotes (italic font artifacts)
- Footer collisions
- Low contrast (gray on cream, dark on dark)
- Mockups distorted or stretched
- Anything that looks AI-generated

Read these files: <list of slide-NN.jpg paths>
Reply: "Slide N: OK" or "Slide N: <specific issue>"
```

Itera fix → rebuild → re-QA hasta limpio. Una pasada nunca es suficiente.

## Step 9 — Forzar pantallas en el simulador (para screenshots)

A menudo necesitas forzar un estado específico (ej. umbral verde con datos perfectos). Tres tácticas:

1. **Mock data flag**: si la app tiene `AppPreferences.datosMockHabilitados`, ponlo en `true` por default. Modificar el seed para hardcodear valores ideales.
2. **Uninstall + reinstall**: `xcrun simctl uninstall <UUID> <bundleId>` limpia SwiftData/UserDefaults, luego rebuild.
3. **UI automation con cliclick**: `snapshot_ui` da coordenadas internas (402x874 puntos), conviértelas a screen coords con offset de la ventana del Simulator (ej. `screen_X = win_X + 27 + sim_X; screen_Y = win_Y + 86 + sim_Y`).

**Cambios al código de la app son LOCAL ONLY** — no commitear ni pushear. Avisar al user antes y revertir cuando termine.

## Step 10 — Documentos compañeros

Para un pitch real, además del deck genera:

1. **GUION-pitch.md** — script slide-por-slide con tiempo target, lo que dice literal, tono, pausas.
2. **QnA-jueces.pdf** — preguntas y respuestas exhaustivas para Q&A. Bloques: negocio, privacidad, técnico, HCAI, datos, crisis, equipo, ODS, trampas. ~80-100 preguntas. Convertir con `pandoc + LibreOffice`:
   ```bash
   pandoc QnA.md -o QnA.html --standalone -c style.css
   soffice --headless --convert-to pdf QnA.html
   ```
3. **CAPTURAS-iphone.md** — qué pantallas debe capturar el user de su app, en orden de prioridad.

## Lessons learned (cosas que casi siempre se rompen)

- **Comillas tipográficas (« »)** en fuentes con italic incompleto generan artefactos visuales.
- **Texto en bg colored slides** (verde/amarillo/rojo full-bleed) suele desbordarse — usar fontSize ~92 max para palabras largas.
- **Watch images** vienen del Apple Sketch UI Kit con fondo blanco opaco, hay que removerlo con PIL antes de meter en slides cream.
- **iPhone screenshot aspect** debe ser 0.46-0.49; si no, el composing en frame queda distorsionado.
- **Footer + iPhone mockup** colisionan si el iPhone llega abajo. Iphone debe terminar antes de Y=6.5 con slide H=7.5.
- **Tags muy claros** (PAL.textTer #9A968D) son ilegibles en cards — usar PAL.textSec #5C5A55 mínimo.
- **Bento card "tags"** en columna gris claro casi desaparecen — siempre verificar contraste.
- **Magic Move requiere mismas formas en slides consecutivos**, si no, hace fade en lugar de transformar.
- **Cifras siempre verificar contra fuente de verdad** (la app, el repo, no asumir).
- **Versión final**: rendear 1 vez en Keynote real para confirmar fonts y transiciones (LibreOffice render no es 100% fiel a Keynote).

## Output esperado

Al terminar, el user debe tener:
- `/path/to/PITCH.pptx` — el deck final, abre en Keynote
- `/path/to/GUION-pitch.md` — script
- `/path/to/QnA.pdf` — preparación Q&A
- `/path/to/CAPTURAS-iphone.md` — guía de capturas

Y si querés ser thorough, una versión rendered como PDF para imprimir como backup.

## Templates available

- `templates/build.js` — pptxgenjs skeleton con helpers
- `templates/add-animations.py` — transitions injector
- `templates/compose.js` — iPhone frame composer
- `templates/iphone-frame.png` — transparent frame asset
- `templates/QnA-template.md` — Q&A starter
- `templates/GUION-template.md` — guion starter
