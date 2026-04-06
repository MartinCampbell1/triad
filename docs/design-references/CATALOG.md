# Codex Desktop App — Screenshot Catalog

Reference screenshots from Codex Desktop App (April 2026) for building Triad Desktop Client.

**How to use:** When implementing a UI component, open the relevant screenshot(s) to see exactly how Codex renders it. Match colors, spacing, typography, layout, and behavior as closely as possible.

---

## Key Screens Identified

### Main Chat View + Sidebar
- `02.01.54.png` — **Main chat with active session.** Shows: sidebar with project groups (FounderOS, mymacagent, autopilot, multi-agent), session list with message counts, main transcript area with assistant response, bottom composer with model selector (GPT-5.4), permission mode indicator (Полный доступ), terminal drawer with "Загружен 1 терминал".
- `02.02.03.png` — **New chat / empty state.** Shows: "Давайте построим" welcome screen, project name below, "Toggle /Fast" notification banner, plugins promotion banner (blue "NEW" pill), composer at bottom.
- `02.03.02.png` — **Project context menu.** Shows: right-click on project in sidebar revealing options: Open in Finder, Создать постоянное рабочее дерево, Изменить имя, Archive threads, Удалить. Also shows Toggle /Fast promotion.

### Plugins & Skills System  
- `02.02.15.png` — **Plugins marketplace (grid view).** Shows: "Make Codex work your way" header, search bar, Featured section with plugin cards (GitHub, Slack, Notion, Linear, Gmail, Google Calendar, Google Drive, Figma, Vercel), Coding section below.
- `02.02.24.png` — **Plugins marketplace (sidebar collapsed variant).** Same grid but with full sidebar visible — shows all project groups and sessions.
- `02.02.32.png` — **Plugins > Manage > Plugins tab.** Shows: installed plugins (Figma, GitHub, Notion) with toggle switches, tab bar (Plugins 3 | Apps 0 | MCPs 5 | Skills 20).
- `02.02.38.png` — **Plugins > Manage > MCPs tab.** Shows: MCP servers list (Chrome Devtools, Configured Tools, Figma, Magic 21st, Search Server) with settings gear + toggle switches.
- `02.02.42.png` — **Plugins > Manage > Skills tab.** Shows: skills list with toggle switches and "Разрешить" permission badges. Skills include: Code Connect Components, Create Design System Rules, Create New Figma File, Generate Figma Design, etc.
- `02.02.47.png` — **(Similar to 02.02.42)** Skills tab continued.

### Chat with Code / Terminal / Diff
- `02.03.42.png` — **Active coding session with terminal.** Shows: transcript with assistant's response including file operations (tool cards), "Загружен 1 терминал" terminal drawer, composer at bottom. Sidebar shows user accounts section at bottom.
- `02.03.48.png` — **Chat with tool execution.** Shows: assistant running commands and reading files — file counts badges on messages (3 файла, 1 поиск), terminal active.
- `02.04.37.png` — **Chat with file analysis.** Shows: assistant analyzing code, reading files, running git commands. Messages have "Изучено" (examined) counts.
- `02.04.43.png` — **Chat with code suggestions.** Shows: plan/analysis text from assistant, "Продвинуться к" dropdown menu with options: Локальный проект (checked), Подключить веб-сайт, Открыть в облаке, Остановить память стека.

### Split View (Chat + Code Editor)
- `02.05.01.png` — **Split view: chat + file preview.** Shows: left panel is chat transcript, right panel shows code file (bootstrap.js) with syntax highlighting. "Непоставленный" (unstaged) badge. Terminal drawer below.
- `02.05.17.png` — **Split view: chat + code with diff.** Shows: same split layout, right panel shows code with green highlights (additions). This is the key diff/review experience.
- `02.05.30.png` — **Commit dialog.** Shows: "Зафиксировать внесенные изменения" modal with: branch name, file changes summary (+518, -0), commit message input, checkboxes (Включить неиндексированное), action buttons (Зафиксировать, Зафиксировать и отправить, Draft).

### Bottom Bar / Controls
- `02.03.55.png` — **Bottom bar detail.** Shows: user accounts section in sidebar, settings link, composer with model selector.
- `02.04.01.png` — **Minimal sidebar with accounts.** Shows: sidebar bottom section — user accounts and settings navigation.
- `02.04.04.png` — **Compact sidebar items.** Shows: session items with small message count badges.
- `02.04.10.png` — **Session badges.** Shows: sessions with numeric badges (7s, 4s etc).
- `02.04.13.png` — **Similar to 02.04.10** — sidebar with sessions and badges.
- `02.04.16.png` — **Sidebar with project groups expanded.** Shows full session list under different project groups.

### Settings / Users
- `02.04.24.png` — **User input context.** Shows chat + dropdown for "Продвинуться к" options.
- `02.04.27.png` — **Similar to 02.04.24.**
- `02.04.29.png` — **Compact state.**
- `02.07.38.png` — **Users page.** Shows: "ПОМОГИ МНЕ" section with user list, chat view with technical content (Hysteria VPN setup instructions, links, code blocks).

### Other Views
- `02.03.13.png` — **Chat with navigation.** Shows: back/forward arrows in title bar, project name, session title.
- `02.03.21.png` — **Chat session mid-conversation.** Shows: sidebar with session list, transcript with file operations.
- `02.03.30.png` — **Sidebar with multiple project groups.** Shows: project grouping and session counts.
- `02.05.38.png` — **Split view variant.**
- `02.05.45.png` — **Split view variant.**
- `02.05.51.png` — **Split view with different content.**
- `02.06.11.png` — **Chat with file changes.** Shows: "Изменён 1 файл" badge, file path reference, usage stats panel (47% использовано, остаток 53%).
- `02.06.20.png` — **Similar to 02.06.11** with usage stats.
- `02.07.23.png` — **Session list with "Помоги мне" section.**

---

## UI Elements Inventory (for component matching)

### Sidebar
- Width: ~260px (expanded), collapsible
- Background: very dark (#181818 or similar)
- Project groups with disclosure triangles (▶/▼)
- Session items: truncated title + message count badge (right-aligned, subtle gray)
- Hover state: slightly lighter background
- Active item: highlighted background
- "Новая беседа" button at top
- "Навыки и приложения" / "Автоматизации" quick links
- Bottom: user account selector + "Настройки" link

### Title Bar
- Custom title bar (no standard macOS title bar)
- Traffic lights (close/minimize/zoom) on far left
- Back/forward navigation arrows
- Session/page title centered
- Action buttons right: "Переместить в рабочее дерево", "Совершить" (commit)
- Right corner: usage counter, user avatar

### Transcript
- Full-width messages (no bubbles, no max-width)
- Assistant text: white on dark background, standard body font
- Tool cards: subtle bordered cards, slightly lighter background
- File operation badges: "Изучено 1 файл, 2 поисков" counts
- Code blocks: monospace, dark background, copy button
- Messages flow top-to-bottom, newest at bottom

### Composer
- Dark elevated background (slightly lighter than main)
- Multiline textarea, auto-expands
- Left: + button (attach), model selector (GPT-5.4 ▾), reasoning effort (Очень высокий ▾)
- Right: send button (blue circle with arrow)
- Below: permission mode indicator (Местный ▾, Полный доступ ▾)
- Below: project path reference

### Terminal Drawer
- Bottom panel, expandable
- Tab: "Загружен 1 терминал" with count
- Dark background, monospace font
- Standard terminal emulator appearance

### Split View (Chat + Code)
- Resizable split: chat on left, code/diff on right
- Code panel: syntax-highlighted file viewer
- File path in header: "Непоставленный" (unstaged) status badge
- Line numbers on left
- Green highlighting for additions, red for deletions

### Commit Dialog
- Modal overlay with dark background
- Branch name + file change stats
- Commit message textarea
- Toggle: "Включить неиндексированное"
- Buttons: Зафиксировать, Зафиксировать и отправить, Draft, Просмотреть изменения

### Model Selector
- Dropdown in composer
- Shows model name (GPT-5.4)
- Reasoning effort selector alongside (Очень высокий)
