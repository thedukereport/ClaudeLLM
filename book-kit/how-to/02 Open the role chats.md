# Open the role chats

The system is six roles. You are the Author; Claude plays the other five, one chat each, so each chat keeps to one job and starts every session from its own rules.

1. **Make one Claude project** for the book and attach your vault folder to it.
2. **Make five chats** in that project and name each for its role: Fact-checker, Editor, Production, Managing Editor, Systems.
3. **Open each chat** by pasting its "Open with" line from `Methodology/Roles.md`. The Editor's, for example:
   > You are the Editor. Read `Methodology/Roles.md` (Editor), then `Methodology/Standing Rules.md`, then `Methodology/Rules — Editor.md`, then `Handoffs/Editor.md`, read the Source Rulings page, and take the next chapter there.
4. **Use the same line** to open each new session of that chat. One task per session; a session ends when its task ends, before the chat grows long enough to be compressed.

## How the chats talk to each other

They do not, directly. Each role writes to the files it owns (the table in `Roles.md` says which) and leaves work for another role in that role's hand-off file, `Handoffs/<Role>.md`, under **Inbox**. You never copy messages between chats. When you want a chat to act now, tell it in one line in its own chat.

## Your two queues

- **The Source Rulings page:** cards, each with the current text and the proposed text in full. You approve, edit, or send back.
- **`Fact Check/Asks.md`:** questions only you can answer, each saying what happens if you say nothing. The page shows them too, under Asks.

Nothing else asks you to rule.

## Keep the hand-offs short

A hand-off file holds the current state only, under 2,000 words: the role's WORKING line, the rules in force, what waits on you, the next session's work in order, and the open Inbox items. When it grows past that, move the history into a dated log file beside it (`Handoffs/Editor — Log 2026-10-13.md`) and leave one line per open item pointing to the log.

## Scheduled tasks

When the chats are running, add two scheduled tasks, each with a prompt that names its role and tells it to follow its protocol in the vault: the **Watcher** (`Fact Check/Watcher/Watcher Protocol.md`), which checks each role's work and writes directives to `Fact Check/Watcher/Directives.md`, and the **nightly fact-check agent** (`Fact Check/Agent Protocol.md`). The Managing Editor routes the directives.
