# Docs Agent Guide
Agents must read this file before making changes within this directory scope.

## Scope
This file applies to everything under `docs/`.

The root `AGENTS.md` still applies. This guide adds documentation-specific rules.

## Docs Purpose
The `docs/` directory is for durable project knowledge that does not belong in inline comments or the concise root `README.md`.

Use `docs/` for:
- architecture and layer boundaries
- runtime configuration
- local development workflow
- gesture behavior and command mappings
- operational notes for webcam, model files, certificates, TV pairing, and voice capture

## Documentation Boundaries
- Keep `README.md` as the quick project entry point.
- Document concepts, behavior, setup, configuration, and decisions rather than repeating code structure.
- Do not include secrets, local certificate contents, machine-specific paths, or environment-specific credentials.
- Do not duplicate configuration defaults or gesture mappings unless the documentation is the canonical user-facing explanation.
- Prefer updating an existing document over creating an overlapping new one.

## Change Guidelines
- Update docs when behavior, environment variables, setup, gesture semantics, pairing behavior, or architecture boundaries change.
- Remove or correct stale guidance when docs and implementation disagree.
- Keep examples short, valid, and directly useful.
- Request approval before broad documentation taxonomy changes.

## Style
- Keep Markdown portable and readable in GitHub.
- Use direct headings and short sections.
- Prefer practical guidance over exhaustive implementation detail.
- Link to canonical source or official docs when external behavior matters.
