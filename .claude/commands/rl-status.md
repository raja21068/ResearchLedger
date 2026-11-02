---
description: What is ResearchLedger doing, and what is waiting for me? Then act on it from here.
---

Helper: `python webapi/rl_cli.py`
(written `RL`).

1. Run `RL status` and `RL decisions`. If `API_DOWN`, tell the user to run
   `& .\start_web.ps1` and stop.
2. Show a short plain list: what is working now, and each decision waiting (paper, what it is, one line why).
   If the worker is offline and tasks are waiting, say that `/rl-worker` (or `/rl`) in this console will do them.
3. If something waits, ask with AskUserQuestion which one to handle (up to 4 options, plus "Nothing now").
   For the chosen one, show its state (`RL loop <project> <loop>` for loops) and ask what to do, offering only the
   actions that fit: Approve and run / Continue / Accept result / One more round / Try again / Stop.
   Run only the action the user picks (`RL loop … <action>`, or `RL approve <project> <stage>` for a paper stage).
   Never approve anything on the user's behalf. If the action starts agent work, offer to do it here with `/rl-worker`.
