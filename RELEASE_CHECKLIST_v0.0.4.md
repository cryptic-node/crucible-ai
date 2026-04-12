# Release Checklist — Grokenstein v0.0.4

## 1. Create a new branch from v0.0.3-dev

```bash
git checkout v0.0.3-dev
git pull origin v0.0.3-dev
git checkout -b v0.0.4-dev
```

## 2. Copy this kit into the repo root
Copy these files and folders into the root of your existing Grokenstein repo.

## 3. Run tests

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
pytest -q
```

## 4. Manual smoke test

```bash
python -m grokenstein.main --id mysession --workspace ./workspace
```

Inside the CLI:

```text
hello Grokenstein
write hello-from-v0.0.4 to note.txt
!pending
!approve
!fs read note.txt
run pwd
!pending
!approve
!history
```

## 5. Commit the iteration

```bash
git add .
git commit -m "Grokenstein v0.0.4 governed runtime foundation kit"
```

## 6. Tag the release

```bash
git tag -a v0.0.4 -m "Grokenstein v0.0.4 governed model runtime"
git push origin v0.0.4-dev
git push origin v0.0.4
```

## 7. Create the GitHub release
If you have GitHub CLI installed:

```bash
gh release create v0.0.4 \
  --title "Grokenstein v0.0.4" \
  --notes-file Grokenstein_v0.0.4_iteration_plan.md
```

If not, create the release in the GitHub web UI from tag `v0.0.4` and paste the top section of the plan file into the release notes.

## 8. Preserve the plan file
Keep `Grokenstein_v0.0.4_iteration_plan.md` in the repo root so every iteration has a permanent planning artifact.
