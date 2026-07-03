# receiptly-v0.2.2 — persist-credentials Fix

## Geändert
- .github/workflows/release.yml — persist-credentials: false entfernt
  (blockierte git-Branch-Auflistung von semantic-release gegen das Remote)
- .releaserc.json — zur Kontrolle mitgeliefert (bereits korrekt: "branches": ["main"])

## Vor dem Committen bitte verifizieren
git show origin/main:.releaserc.json
→ Falls dort noch "prerelease": "alpha" steht, war NICHT nur persist-credentials
  die Ursache — dann zusätzlich diese Datei aus dem Archiv einspielen.

## Commit-Message (reine Zeile, kein git-Wrapper)
fix(ci): remove persist-credentials false blocking semantic-release branch resolution
