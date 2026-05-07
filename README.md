# Chi Alpha Fantasy · Box Office 2026

A fantasy box office league tracker with live gross updates, trades, waiver wire, and two leagues.

## 🚀 Setup (one-time)

### 1. Create a GitHub repo
- Go to [github.com](https://github.com) → **New repository**
- Name it `chi-alpha-fantasy` (or anything you like)
- Set it to **Public** or **Private** — both work
- **Don't** initialize with a README (you'll push these files)

### 2. Push these files
```bash
git init
git add .
git commit -m "Initial deploy"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/chi-alpha-fantasy.git
git push -u origin main
```

### 3. Connect Netlify to GitHub
- Go to [app.netlify.com](https://app.netlify.com) → **Add new site** → **Import from Git**
- Choose **GitHub** → select your `chi-alpha-fantasy` repo
- Build settings:
  - **Build command:** *(leave blank)*
  - **Publish directory:** `.`
- Click **Deploy site**

Netlify will now auto-deploy every time the GitHub repo changes.

### 4. Enable auto-updates
The GitHub Action in `.github/workflows/update-grosses.yml` runs daily at 8 AM UTC and:
1. Scrapes the latest 2026 grosses from [The Numbers](https://www.the-numbers.com/market/2026/top-grossing-movies)
2. Patches `index.html` with updated values
3. Commits and pushes the change
4. Netlify picks up the commit and redeploys automatically

No extra setup needed — GitHub Actions is free for public repos and includes 2,000 free minutes/month for private repos.

## 🔄 Manual update trigger
Go to your GitHub repo → **Actions** tab → **Update Box Office Grosses** → **Run workflow** → **Run workflow**

## ✏️ Making manual changes
1. Edit `index.html` locally or via Claude
2. Push to GitHub
3. Netlify redeploys automatically in ~30 seconds

## 📁 Files
| File | Purpose |
|------|---------|
| `index.html` | The entire app — all data, logic, and styles in one file |
| `update_grosses.py` | Daily scraper that patches grosses from The Numbers |
| `.github/workflows/update-grosses.yml` | GitHub Actions schedule |
| `netlify.toml` | Netlify deploy config |
