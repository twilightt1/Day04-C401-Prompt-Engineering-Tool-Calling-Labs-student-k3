---
name: save_digest
track: bonus
kind: action
provider: local filesystem
requires_env: []
inputs: [markdown, filename, confirmed]
outputs: [status, path, bytes, preview]
side_effect: local_file_write
requires_confirmation: true
---
# save_digest

Writes a finished markdown digest to `outputs/<filename>.md`.

The confirmation boundary matches `send`: with `confirmed` false the tool writes
nothing and returns `status: "needs_confirmation"` together with a preview and
the path it would write. Only an explicit `confirmed: true` produces a file. The
preview exists so the user can approve the actual content rather than approving
blind.

`filename` arrives from the model and is not trusted. It is reduced to a
basename, stripped to `[A-Za-z0-9._-]`, forced to a `.md` suffix, and the
resolved path is asserted to sit directly inside `outputs/`. When any of that
changed the input, the result carries `sanitized: true`. An empty `filename`
becomes `digest-<YYYYMMDD-HHMMSS>.md`.

Saving an empty digest is an error rather than an empty file - it usually means
the digest step upstream was skipped.
