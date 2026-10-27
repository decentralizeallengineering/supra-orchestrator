# supra-orchestrator

Templates and a small standard-library CLI for running a fleet of Claude Code sessions with a clear chain of command: the person (principal), a proxy session that acts for them, a governor session that splits the work, and worker sessions that do it.

Why: long-running fleets drift. Orders get paraphrased, workers report "done" for things the person cannot see working, and peers cite the person's wishes without proof. This keeps one ledger of the person's exact words, one short state file, and one append-only facts file.

## Install

    pip install .          # or run `python -m supra` from a checkout

Python 3.9 or newer, no dependencies.

## Rules

1. Every order quotes the person verbatim. `supra order new` refuses empty words and stores them unchanged, in quotes.
2. An order is DONE only when the person's own path shows it (their install, their button, their document). `order state ... done` requires `--evidence`; anything weaker is reported as "UNVERIFIED on the person's path".
3. A peer who writes that the person said something must attach the quote. No quote, no authority.

## Configure

All files live in `$SUPRA_HOME` (default: the current directory). `$SUPRA_STATE_MAX` sets the STATE.md line limit (default 150). `$SUPRA_NOW` (`YYYY-MM-DD HH:MM`) fixes the clock for tests.

`supra init <dir>` copies the templates without overwriting: `PROXY-CLAUDE.md`, `GOVERNOR-CLAUDE.md` (rename each to `CLAUDE.md` in that session's directory), `INTENT.md`, `ORDERS.md`, `STATE.md`, `FACTS.md`.

## Commands

- `supra order new "<exact words>" [--owner SESSION]` adds a row (id, date, verbatim words, owner, state) and prints its id.
- `supra order state <id> open|done|blocked [--evidence TEXT]`; evidence is required for done and blocked.
- `supra state add "<line>"` appends to STATE.md. The line must end with `RESULT: DONE|FAILED|BLOCKED - <evidence>`. Past the limit, the oldest entries move to STATE-ARCHIVE.md.
- `supra facts add "<text>"` appends a dated line to FACTS.md. There is no edit or delete command.
- `supra audit [--hours N]` lists orders open longer than N hours (default 24) and DONE rows without evidence. Exit status 1 if it finds anything.

## Example

    export SUPRA_HOME=$PWD/fleet && supra init "$SUPRA_HOME"
    supra order new "Make the installer work on a clean machine." --owner worker-a
    supra state add "Installer builds RESULT: DONE - pytest 12 passed, commit 1a2b3c4"
    supra order state O1 done --evidence "clean-machine install ran, window shows 2.0"
    supra audit

## Tests

    python -m pytest tests

## License

Apache-2.0. See LICENSE and NOTICE.
