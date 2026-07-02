# King Synapse Demo

This is a small, disposable run of the CLI. It uses `KING_SYNAPSE_DB` so the
demo does not touch your normal memory database.

## 1. Use A Temporary Database

```powershell
$env:KING_SYNAPSE_DB = "$env:TEMP\king-synapse-demo\synapse.sqlite"
```

Check where the CLI will write:

```bash
kr where
```

Example output:

```text
C:\Users\...\AppData\Local\Temp\king-synapse-demo\synapse.sqlite
```

## 2. Write A Tiny Cognitive Chain

```bash
kr write "Skipped water before the scooter commute lowered mood." --kind state --scope user
kr write "Tired mood narrows commute attention and raises fall risk." --kind fact --scope user
kr write "Future commute mistakes increase when attention narrows." --kind fact --scope user
```

Example output:

```text
written 01KWGHE4AYYDB9KGVKZGYFDWPK
written 01KWGHE4DJ7RVNS4F9NSZFY8AC
written 01KWGHE4FWTWJ9VB2694TV9YSE
```

## 3. Recall Visible Memories

```bash
kr recall "water commute attention" --explain
```

Example output:

```text
#1 01KWGHE4AYYDB9KGVKZGYFDWPK  [state/user, 2026-07-02 04:29]
    Skipped water before the scooter commute lowered mood.
    Sources:          F
    FTS Rank:         1
    RRF Score:        0.0164
    Final Score:      0.0082

#2 01KWGHE4FWTWJ9VB2694TV9YSE  [fact/user, 2026-07-02 04:29]
    Future commute mistakes increase when attention narrows.

#3 01KWGHE4DJ7RVNS4F9NSZFY8AC  [fact/user, 2026-07-02 04:29]
    Tired mood narrows commute attention and raises fall risk.
```

This is still ordinary recall: it finds the visible memories that match the
query.

## 4. Trace The Current Thought

```bash
kr trace "forgot water before commute while tired" --auto-context --predict
```

Example output:

```text
Context: state=[tired] goal=[commute,forgot,tired,water,while]
Dominant:
  [0.7000 src=Visible rank=1 visible=0.0082 latent=- inhibit=0.0000]
  01KWGHE4  Skipped water before the scooter commute lowered mood.

Suppressed:
  [0.6887 src=Visible rank=2 visible=0.0081 latent=- inhibit=0.0113]
  01KWGHE4  Tired mood narrows commute attention and raises fall risk.

  [0.6778 src=Visible rank=3 visible=0.0079 latent=- inhibit=0.0222]
  01KWGHE4  Future commute mistakes increase when attention narrows.

Stats: visible=3 latent=0 combined=3 suppressed=2
Prediction: (none)
```

The trace report separates the winning candidate from the candidates that were
close, but did not win.

## 5. Learn After The Report

```bash
kr trace "forgot water before commute while tired" --auto-context --predict --reinforce --reinforce-k 3
```

Example output:

```text
Dominant:
  01KWGHE4  Skipped water before the scooter commute lowered mood.

Suppressed:
  01KWGHE4  Tired mood narrows commute attention and raises fall risk.
  01KWGHE4  Future commute mistakes increase when attention narrows.

Prediction:
  [0.0091 depth=1 mod=1.65]
  path=01KWGHE4 -> 01KWGHE4
  match=goal:commute,goal:tired,state:tired
  Tired mood narrows commute attention and raises fall risk.

  [0.0069 depth=1 mod=1.25]
  path=01KWGHE4 -> 01KWGHE4
  match=goal:commute
  Future commute mistakes increase when attention narrows.

reinforced 6 edge updates (0 skipped)
```

The CLI shortens memory ids in trace output. In this tiny run the ids share the
same prefix because the memories were written seconds apart; the underlying
stored ids are still distinct.

The important behavior is the order:

1. recall reports the current visible candidates;
2. trace chooses a dominant candidate and keeps suppressed candidates visible;
3. reinforcement happens after the report, so learning does not rewrite the
   explanation that was just produced.

## 6. Clean Up

```powershell
$env:KING_SYNAPSE_DB = $null
Remove-Item "$env:TEMP\king-synapse-demo" -Recurse -Force
```
