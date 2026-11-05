# Cards

`cards.jsonl` holds every card the author rules on, one line per card version, and only grows. `tools/cards.py` is the one way a version goes in (`tools/cards.py add <card.json> --why "<reason>"`), and `tools/card-desk.py` is where the author rules on them (http://127.0.0.1:8766). Each press of the author's is a `decision.recorded` event in `Fact Check/events/`; `tools/cards.py fold` reads the card as it stands now. Never edit this file by hand.
