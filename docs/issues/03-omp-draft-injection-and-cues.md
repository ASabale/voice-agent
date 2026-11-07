# Lock OMP draft injection and Enter submission mechanism

Type: grilling
Status: open
Blocked by: 01, 02

## Question

Once a **Chunk** is transcribed by Handy and filtered for command phrases (`"send prompt"`, `"pause listening"`, `"cancel that"`):
- How should the controller inject the **Draft** text and the final `Enter` keystroke into `omp`?
  - **Option A**: Handy's `external_script_path` hook writes to clipboard + simulates `Cmd+V` (and `Return` when `"send prompt"` is detected), optionally bringing the `omp` Terminal window to front if unfocused.
  - **Option B**: Send keys directly to a target `tmux` pane or PTY running `omp` (`tmux send-keys -l` for chunks, `tmux send-keys Enter` on `"send prompt"`), so it works even if another window is focused.
- What exact **Audio Cues** should play on Wake, Chunk appended, Send, and Cancel?
