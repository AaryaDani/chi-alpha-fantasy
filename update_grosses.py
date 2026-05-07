name: Update Box Office Grosses

on:
  schedule:
    # Runs every day at 8:00 AM UTC (4 AM ET / 3 AM CT)
    - cron: '0 8 * * *'
  workflow_dispatch:
    # Also allows manual trigger from GitHub Actions tab

env:
  FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true

jobs:
  update-grosses:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repo
        uses: actions/checkout@v4
        with:
          token: ${{ secrets.GITHUB_TOKEN }}

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Fetch latest grosses from Google Sheet and patch index.html
        run: python update_grosses.py

      - name: Check for changes
        id: changes
        run: |
          if git diff --quiet index.html; then
            echo "changed=false" >> $GITHUB_OUTPUT
          else
            echo "changed=true" >> $GITHUB_OUTPUT
          fi

      - name: Commit and push if changed
        if: steps.changes.outputs.changed == 'true'
        run: |
          git config user.name  "Box Office Bot"
          git config user.email "bot@chi-alpha-fantasy.com"
          git add index.html
          git commit -m "📊 Auto-update from Google Sheet $(date -u +'%Y-%m-%d')"
          git push
