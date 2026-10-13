# UAT Log

The author: *"You cannot build anything anymore without some kind of user acceptance testing. I don't need to get 300 changes into a process for you to find a bug."*

Each tool that writes more than five things records here what the author was shown and what the author said. `tools/uat.py` reads this file and refuses a bulk write for any tool with no ACCEPTED line. A count is no sample: the author sees the whole before and after of a few changes, in a file the author can open.

Add one row per sample, newest last; `tools/uat.py accept <tool> "<what the author was shown>"` writes an ACCEPTED row after the author's "ok". **verdict** is ACCEPTED (the author said "ok"), DECLINED, or PENDING (shown, no answer yet; REVIEW asks wait, so PENDING blocks).

| date | tool | what the author was shown | verdict |
|---|---|---|---|
