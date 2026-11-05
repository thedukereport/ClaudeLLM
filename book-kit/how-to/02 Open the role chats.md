# Open the role chats

The system is seven roles. You are the Author; Claude plays the other six, one session each, so each session keeps to one job and starts from its own rules.

1. **Open Claude Code in your vault folder**: the Claude desktop app's Code tab, or `claude` in a terminal from the vault.
2. **Open six sessions** there and name each for its role: Fact-checker, Editor, QA, Production, Managing Editor, Systems.
3. **Set up `Chat Prompts.md`** in your vault: replace `<VAULT>` with the full path to your vault.
4. **Open each chat** by pasting its **Start** prompt from `Chat Prompts.md`. (`Methodology/Roles.md` has a shorter "Open with" line for each role.)
5. **One task per session.** Each Start prompt ends with "write your hand-off file and stop". When a chat compresses, goes wrong or finishes, use **Recover** or **Close**: `07 When a chat gets long or compresses.md` says which.

## How the chats talk to each other

They do not, directly. Each role writes to the files it owns (the table in `Roles.md` says which) and leaves work for another role in that role's hand-off file, `Handoffs/<Role>.md`, under **Inbox**. You never copy messages between chats. When you want a chat to act now, tell it in one line in its own chat.

## Your one queue

The card desk, http://127.0.0.1:8766 (`tools/card-desk.py`), is the one place you rule. It shows one card at a time; "Next card" takes you down the queue.

- **Waiting for you:** each card with the current text and the proposed text in full, and the paragraphs around them. Approve it; or edit the text in the box and press "Send my edits for checking"; or write a directive. Your words are kept in your browser until you press a button.
- **Reopen?:** a card that would change a line you already approved, in full, with "Reopen this line" and "Keep it closed". A line you approved comes back here only when a reading shows it wrong.
- **With Claude:** the cards that are not ready, each with its reason: a fact with no logged read, a banned word, a prose audit no second session has done, a note your rules send back, a card the chapter has moved under, or your own edits waiting to be checked. You never have to rule on these.
- **Approved, going in** and **In the book:** what Production will apply, and what it has.
- **Asks:** questions only you can answer, each saying what happens if you say nothing. They are kept on file in `Fact Check/Asks.md`.
- **Sources to get:** only works the library cannot produce, as "I cannot find these. Can you get them?" A cited work in the library that nobody has read yet goes to the Fact-checker to read; it never comes to you.

Nothing else asks you to rule.

## Keep the hand-offs short

A hand-off file holds the current state only, under 2,000 words: the role's WORKING line, the rules in force, what waits on you, the next session's work in order, and the open Inbox items. When it grows past that, move the history into a dated log file beside it (`Handoffs/Editor — Log 2026-10-13.md`) and leave one line per open item pointing to the log.

## Scheduled tasks

When the chats are running, add two scheduled tasks, each with a prompt that names its role and tells it to follow its protocol in the vault: the **Watcher** (`Fact Check/Watcher/Watcher Protocol.md`), which checks each role's work and writes directives to `Fact Check/Watcher/Directives.md`, and the **nightly fact-check agent** (`Fact Check/Agent Protocol.md`). The Managing Editor routes the directives.
