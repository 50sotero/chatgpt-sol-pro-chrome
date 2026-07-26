# Artifact verification

Use this reference after ChatGPT exposes downloadable files.

## Materialize the bytes

1. Read the Chrome download documentation.
2. Start the download wait before clicking the exact scoped download control.
3. Resolve the real local download path from the completed browser download.
4. Copy or move it to a collision-free user-approved destination without overwriting prior outputs.
5. Wait for the browser download event and stable local file metadata; do not use elapsed time or a partial-looking filename as proof.

An opaque URL, browser link, UI toast, or assistant statement is not a local artifact.

## Run generic checks

Run:

```powershell
python <skill-dir>\scripts\verify_artifacts.py <downloaded-file-or-directory> `
  --required report.md `
  --required run_manifest.json
```

Use `--manifest <name-or-path>` when automatic manifest discovery is ambiguous. Use `--report <path>` to persist the JSON validation receipt.

The script checks:

- file/container existence;
- safe ZIP member names and duplicate members;
- required-file membership;
- manifest-declared byte counts and SHA-256 hashes;
- JSON and JSONL syntax;
- manifest-declared JSONL/CSV row counts and optional unique keys;
- CSV readability;
- basic PDF, PNG, and JPEG signatures;
- ZIP CRC integrity.

The script supports common manifest shapes:

- `files: [{name|path, bytes|size, sha256, ...}]`
- `output_files: {"path": {bytes, sha256, ...}}`
- `artifacts: [{name|path, ...}]`

## Add task-specific checks

Generic validation cannot prove the user's semantic contract. Also check:

- exact expected filenames and no unexpected substitutions;
- required JSON fields, enums, types, and ranges;
- stable ID uniqueness and expected ID set;
- cross-file identity and count reconciliation;
- totals across summaries and time series;
- provenance, model/mode, prompt hash, and source hashes;
- reproducibility commands such as `--validate-only`;
- rendered layout and every page for PDF or visual deliverables;
- that the artifact contains the requested content rather than a placeholder.

## Repair safely

- Preserve the failed artifact and its hash.
- Return the precise validation error to the same ChatGPT conversation.
- Request a new versioned filename.
- Re-download and rerun all checks.
- Never weaken a schema or omit a required file merely to make validation pass.

Report verified, failed, and unverified properties separately.
