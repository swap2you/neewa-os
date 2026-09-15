# Memory Architecture

Do not train/fine-tune NEEWA on raw chat history as the primary memory method.

## Layers

### Owner memory
Stable preferences, goals, working style, boundaries.

### Project memory
Architecture, decisions, state, constraints, acceptance criteria.

### Experience memory
Provider performance, recurring failures, useful patterns, lessons.

### Job memory
Per-job objective, worker, evidence, cost, outcome.

## Portability
Critical memory is stored as versioned Markdown/YAML/JSON in Git or approved durable storage.

A future replacement agent must be able to reconstruct state without proprietary chat history.
