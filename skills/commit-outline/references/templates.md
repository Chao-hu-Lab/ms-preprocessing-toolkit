# Templates

## Commit Type Hints

- `feat`: new user-visible capability
- `fix`: bug fix or regression fix
- `refactor`: internal structure change without intended behavior change
- `docs`: documentation only
- `test`: tests only
- `build`: packaging or build pipeline change
- `ci`: workflow change
- `chore`: maintenance or release bookkeeping

## Subject Templates

```text
feat(scope): add <capability>
fix(scope): correct <behavior>
refactor(scope): simplify <area>
docs(scope): clarify <topic>
test(scope): cover <behavior>
build(scope): update <build behavior>
ci(scope): adjust <workflow behavior>
chore(release): bump version to <version>
```

## Commit Body Template

Use when needed:

```text
- <primary change>
- <secondary change>
- <verification or notable constraint>
```

## PR Summary Template

```markdown
## Summary
- <what changed>
- <what changed>

## Verification
- <command/result>
- <command/result>
```

## Release Note Outline

```markdown
## Highlights
- <user-facing improvement>

## Fixes
- <bug fix>

## Verification
- <high-level test or release verification note>
```
