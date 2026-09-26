# 2026-09-25 — Developer environment

## 14:28 — VS Code chat terminal intermittently reported "the terminal was closed" while commands had already run

### Objective

Fix the intermittent `run_in_terminal` failure in Copilot Chat: a command would report
`ERROR while calling tool: The terminal was closed` even though the command had executed and its
output was visible in the terminal panel. Manually killing the terminal and re-running the same
command succeeded, which pointed at terminal/shell state rather than at the commands themselves.
Roughly 1 in 4 calls failed, including simple ones (`wc -l`, `rm`, a Python script) and always
against commands with no side-effect problem of their own.

### Solution

VS Code shell integration was installed but never completed, because `~/.bashrc` overwrote
`PROMPT_COMMAND`.

VS Code injects a script that installs a prompt hook (`__vsc_prompt_cmd`). That hook is what emits
the `OSC 633;D;<exitcode>` (command finished) and `633;P;<property>` (capabilities) sequences. The
Kali prompt block in `~/.bashrc` destroyed the hook:

```bash
[ "$NEWLINE_BEFORE_PROMPT" = yes ] && PROMPT_COMMAND="PROMPT_COMMAND=echo"
```

That assignment is self-consuming: at the first prompt bash runs `PROMPT_COMMAND=echo`, after which
`PROMPT_COMMAND` is just `echo`. Consequences observed in VS Code's own log:

- `Shell integration failed to add capabilities within 10 seconds`
- `RunInTerminalTool: Finished ... with exitCode `undefined`` on **every** run

Without a completion signal the chat tool's `rich` execute strategy cannot confirm the command
finished, so it eventually disposes the terminal handle and reports it as closed — while the output
remains on screen. That is exactly the reported symptom.

Two earlier attempts had failed for a reason worth recording: appending a corrected value *below*
line 106 was not enough, because line 106 had already destroyed the hook, so the append preserved a
worthless value. The clobbering line itself had to go.

Edits applied to `~/.bashrc`:

1. Commented out line 106 (the clobbering assignment).
2. Added an append-only block at the end of the file, so the blank line before the prompt is kept
   without discarding an existing hook:
   `PROMPT_COMMAND="__newline_before_prompt${PROMPT_COMMAND:+; $PROMPT_COMMAND}"`
3. Guarded the ssh-agent block so it no longer runs on every shell start:
   `if ! ssh-add -l >/dev/null 2>&1; then eval "$(ssh-agent -s)" >/dev/null; ssh-add ... ; fi`
4. Left the manual `source "$(code --locate-shell-integration-path bash)"` block commented out —
   automatic injection demonstrably works (all 20 `__vsc_*` functions are defined), and sourcing it
   as well would install the hook twice.

### Actions Performed

1. Read the Copilot session debug log and VS Code's window log
   (`~/.config/Code/logs/20260925T124506/{terminal.log,ptyhost.log}`) and `~/.config/Code/User/settings.json`
   (`terminal.integrated.shellIntegration.enabled: true`, no custom profiles).
2. Wrote diagnostics to files and read them with the file reader instead of relying on terminal
   capture, because capture was the broken part (`/tmp/termdiag.txt`, `/tmp/termdiag2.txt`,
   `/tmp/termdiag3.txt`).
3. Read `~/.bashrc` and identified the `PROMPT_COMMAND` clobber at line 106.
4. Confirmed the mechanism from inside a tool terminal: hook defined but not referenced.
5. User commented line 106, added the append-only block, and guarded the ssh-agent block.
6. Re-tested in fresh terminals and re-ran the command shapes that had previously failed.
7. Checked `terminal.log` for new capability warnings and for recorded exit codes.

### Verification Output

Before the fix, inside a tool-created terminal (raw file content; the `633` sequences appear
unsanitised):

```
]633;E;echo "term=$TERM_PROGRAM";bdcba652-...]633;C
PROMPT_COMMAND=[echo]
hook __vsc_prompt_cmd: defined
hook referenced by PROMPT_COMMAND: NO
```

After the fix, same test in a new terminal:

```
]633;E;echo "term=$TERM_PROGRAM";d1a5c795-...]633;C
PROMPT_COMMAND=[__newline_before_prompt; __vsc_prompt_cmd]
hook defined: yes
hook referenced: YES
```

Capability warnings in `terminal.log` — only three, all before the fix, none after:

```
80:2026-09-25 13:17:13.644 [warning] Shell integration failed to add capabilities within 10 seconds []
118:2026-09-25 13:17:45.730 [warning] Shell integration failed to add capabilities within 10 seconds []
139:2026-09-25 13:18:15.427 [warning] Shell integration failed to add capabilities within 10 seconds []
```

Post-fix: five consecutive tool commands returned cleanly, including the two shapes that had been
failing (a `{ ... } > /tmp/file` digest containing `$(...)`, and `.venv/bin/python -c ...`).

Outstanding: `RunInTerminalTool: Finished ... exitCode `undefined`` still appears for post-fix runs.
It is not yet established whether that is a logging quirk of the `rich` strategy or a functional gap;
the authoritative check is the terminal tab hover, which reports shell integration quality
(**Rich** = command detection working ideally, **Basic** = location detected but no exit status) and
whether command decorations appear.

### References Used

1. VS Code — Terminal Shell Integration (installation, quality levels, `OSC 633` sequences, and the
   documented cause "*`$PROMPT_COMMAND` is in an unsupported format*"):
   <https://code.visualstudio.com/docs/terminal/shell-integration>
2. VS Code — Terminal Basics (profiles, default shell, and where the tool terminals come from):
   <https://code.visualstudio.com/docs/terminal/basics>
3. GNU Bash Reference Manual — Shell Variables (`PROMPT_COMMAND`, including its array behaviour in
   bash 5.1+):
   <https://www.gnu.org/software/bash/manual/bash.html#Bash-Variables>

### Optional steps

- Hover the tab of a new terminal and use *Show Details* to confirm quality is **Rich** with exit
  status support; command decorations (blue/red markers) should now appear where they never did.
- Add a comment above the append-only block warning that `PROMPT_COMMAND` must be appended to, never
  assigned, so a future prompt tweak does not silently disable shell integration again.
- Tighten the ssh-agent guard to check for the specific keys (see Possible problems) if they ever
  seem missing.
- If `exitCode undefined` persists while the terminal hover shows Rich, consider reporting it
  upstream to microsoft/vscode with the log excerpt.

### Possible problems

- Any future prompt/framework change that *assigns* `PROMPT_COMMAND` instead of appending to it will
  break shell integration again. The Kali `NEWLINE_BEFORE_PROMPT=yes` default does exactly this, so
  a distro update could reintroduce the line.
- Only `bash` was fixed. `~/.zshrc` also customises heavily (`prompt elite2` plus a custom `PROMPT`,
  `bindkey -v`, autosuggestions, syntax highlighting); if zsh ever becomes the VS Code default
  profile, the same class of problem needs checking there.
- The ssh-agent guard uses "agent has no identities" as its condition. If an agent is already running
  that holds *unrelated* keys, `originals` will not be added, which is a behaviour change from
  the previous always-run version.
- ssh-agents accumulate: every shell that does not inherit `SSH_AUTH_SOCK` starts a new agent, and
  nothing kills the old ones.
- The chat tool creates a new terminal per command, so each command pays bash startup plus a 5 s wait
  for shell integration. Startup cost can be reduced by keeping `~/.bashrc` light (the removed
  unconditional `ssh-agent` + two `ssh-add` calls were part of that cost).
