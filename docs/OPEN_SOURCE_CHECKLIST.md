# Open Source Checklist

Use this checklist before changing the repository visibility from private to public.

1. Confirm the working tree only contains changes you intend to publish with `git status --short`.
2. Confirm local secret-bearing files stay untracked: `.env*`, `.claude/`, `.aws/`, `.ssh/`, `.netrc`, `.npmrc`, `*.pem`, `*.key`, and related certificate or keystore files.
3. Confirm repository-side GitHub settings are clean:
   - `gh secret list --repo MartinCampbell1/triad --app actions`
   - `gh secret list --repo MartinCampbell1/triad --app dependabot`
   - `gh secret list --repo MartinCampbell1/triad --app codespaces`
   - `gh variable list --repo MartinCampbell1/triad`
   - `gh api repos/MartinCampbell1/triad/environments`
   - `gh api repos/MartinCampbell1/triad/keys`
4. Make sure the `Secret Scan` GitHub Actions workflow is green on the branch you are about to merge or publish.
5. Review docs and screenshots for anything private or machine-specific before pushing.
6. If a real secret is ever found, rotate it first and only then rewrite history or purge the file.
