# Review records

Completed reviews live here, one directory per task:

```
docs/agents/reviews/
├── T2/
│   ├── attempt-1.md        first review  (CHANGES_REQUESTED)
│   ├── attempt-2.md        after repair  (PASS)
│   └── ESCALATION.md       only if 3 attempts were exhausted
└── T3/
    └── attempt-1.md
```

The blank checklist is `docs/reviews/TEMPLATE.md` — one template, no duplicates.
`./scripts/agents.sh review <role|TASK_ID>` seeds the next `attempt-N.md` from it, counts the
attempts, and refuses to start a fourth: it writes `ESCALATION.md` and stops instead.

Attempt files are the loop's state. Do not delete them to "reset" a task — that erases the
history a human needs in order to decide. Deleting `ESCALATION.md` is the deliberate,
explicit act that re-opens a stopped loop.
