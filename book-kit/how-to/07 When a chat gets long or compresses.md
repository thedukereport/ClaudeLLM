# When a chat gets long or compresses

A chat holds a limited amount of conversation. When it fills up, Claude compresses the earlier part into a summary and keeps going. A summary keeps the gist and loses detail: the rules the chat read at the start, the rulings you gave, the exact place it stopped. The system plans for this. The hand-off files and the rule files hold what a chat needs, so a new chat can pick up the work in minutes.

The prompts for each step are in `Chat Prompts.md` in your vault. Set it up once: replace `<VAULT>` with the full path to your vault and `<PAGE URL>` with your review page's link.

## Keep sessions short

One task per session: one chapter for the Editor, one chapter's items for the Fact-checker, one chapter's cleared cards for Production, one fault for Systems. The Start prompts end with "write your hand-off file and stop". A chat that stops after one task seldom compresses.

## The three prompts

1. **Start:** the first message of a new chat. It names the role, the files to read in order, and the one task to take.
2. **Recover:** paste it when the chat says it compacted or summarized the conversation. The chat re-reads the Standing Rules, its role's rules and its hand-off file, then continues the same task.
3. **Close:** paste it when you want the chat to stop cleanly: at the end of the day, before you switch models, or when the chat goes wrong. It writes its hand-off file (what it finished, what is half-done and where, any read not yet logged, the next step), sets its WORKING line to say what it is doing, and stops.

## When to start fresh rather than Recover

- It repeats a mistake you already corrected.
- It forgets a ruling you gave.
- It compacts again within minutes.

Then:

1. Send **Close** and wait for it to write its hand-off file.
2. Open `Handoffs/<Role>.md` and check the top: today's date, the WORKING line, and the next step.
3. Rename the old chat "<Role> - Retired".
4. Open a new chat in the same project, name it for the role, and paste **Start**.
5. Check its first reply: it names the files it read and the task it is taking from the hand-off. If it starts work without that, tell it to read the files first.

## Keep the hand-off files short

A new chat reads its hand-off file whole, so the file holds the current state only, under 2,000 words. When it grows past that, ask the Managing Editor or the role itself to move the history into a dated log beside it (`Handoffs/Editor — Log 2026-10-13.md`), with one line per open item pointing to the log.
