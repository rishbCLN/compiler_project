# Disabled workflows

GitHub Actions only runs workflow files in `.github/workflows/`. The CI
workflow was moved here to turn it off. To turn it back on:

    git mv .github/workflows-disabled/ui.yml .github/workflows/ui.yml
