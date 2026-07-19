# ============================================================
# KiyoDesk Initial Project Setup
# Version : 1.0
# Author  : ChatGPT
# ============================================================

Write-Host ""
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host "       KIYODESK PROJECT INITIALIZER"
Write-Host "===============================================" -ForegroundColor Cyan
Write-Host ""

# ------------------------------------------------------------
# Check Git
# ------------------------------------------------------------

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "Git is not installed." -ForegroundColor Red
    Write-Host "Download Git from:"
    Write-Host "https://git-scm.com/downloads"
    Pause
    exit
}

Write-Host "Git found." -ForegroundColor Green

# ------------------------------------------------------------
# User Information
# ------------------------------------------------------------

$GitUser = Read-Host "GitHub Name"
$GitEmail = Read-Host "GitHub Email"
$GitHubUser = Read-Host "GitHub Username"

# ------------------------------------------------------------
# Configure Git
# ------------------------------------------------------------

git config --global user.name "$GitUser"
git config --global user.email "$GitEmail"
git config --global init.defaultBranch main
git config --global core.autocrlf true
git config --global pull.rebase false

Write-Host "Git configured." -ForegroundColor Green

# ------------------------------------------------------------
# Initialize Git
# ------------------------------------------------------------

if (-not (Test-Path ".git")) {
    git init
    Write-Host "Git repository initialized." -ForegroundColor Green
}
else {
    Write-Host "Git repository already exists." -ForegroundColor Yellow
}

# ------------------------------------------------------------
# Folder Structure
# ------------------------------------------------------------

$Folders = @(
"backend",
"frontend",
"docs",
"docs\architecture",
"docs\strategy",
"docs\runtime",
"docs\roadmap",
"docs\api",
"prompts",
"tests",
"scripts",
"docker",
".github",
".github\ISSUE_TEMPLATE",
".github\workflows"
)

foreach ($Folder in $Folders)
{
    New-Item -ItemType Directory -Force -Path $Folder | Out-Null
}

Write-Host "Folder structure created." -ForegroundColor Green

# ------------------------------------------------------------
# .gitignore
# ------------------------------------------------------------

@'
# Python
__pycache__/
*.py[cod]
*.pyo
*.pyd
*.egg-info/
.venv/
venv/

# Environment
.env
.env.*

# SQLite
*.db
*.sqlite3

# Node
node_modules/

# React
dist/
build/

# Logs
*.log

# Cache
.pytest_cache/
.mypy_cache/
.ruff_cache/

# IDE
.vscode/
.idea/

# OS
Thumbs.db
.DS_Store

# Coverage
.coverage
htmlcov/
'@ | Set-Content ".gitignore"

Write-Host ".gitignore created."

# ------------------------------------------------------------
# README
# ------------------------------------------------------------

@'
# KiyoDesk

## Trading Intelligence Platform

### Features

- ICT Strategy Engine
- Trading Runtime
- Trade Opportunities
- Trade Journal
- Analytics
- CCXT Integration
- Historical Backtesting
- Confidence Engine
- Market Regime
- Replay
- AI Assistant

Status:
Under Development
'@ | Set-Content README.md

# ------------------------------------------------------------
# PROJECT CONTEXT
# ------------------------------------------------------------

@'
# PROJECT CONTEXT

Project:
KiyoDesk

Vision:
Trading Intelligence Platform

Architecture

Providers

↓

Trading Runtime

↓

Strategy Engine

↓

Trade Opportunities

↓

Trade Journal

↓

Analytics

Future

Confidence Engine

Market Regime

Replay

AI Assistant
'@ | Set-Content PROJECT_CONTEXT.md

# ------------------------------------------------------------
# CHANGELOG
# ------------------------------------------------------------

@'
# Changelog

## v0.1.0

Initial repository
'@ | Set-Content CHANGELOG.md

# ------------------------------------------------------------
# CONTRIBUTING
# ------------------------------------------------------------

@'
# Contributing

Create a feature branch before development.

Never commit directly to main.
'@ | Set-Content CONTRIBUTING.md

Write-Host "Project files created." -ForegroundColor Green

# ------------------------------------------------------------
# Initial Commit
# ------------------------------------------------------------

git add .

git commit -m "Initial commit - KiyoDesk"

# ------------------------------------------------------------
# Remote
# ------------------------------------------------------------

$RepoURL = "https://github.com/$GitHubUser/kiyodesk.git"

git remote remove origin 2>$null

git remote add origin $RepoURL

git branch -M main

Write-Host ""
Write-Host "================================================"
Write-Host "Before continuing ensure that:"
Write-Host ""
Write-Host "A PRIVATE GitHub repository named 'kiyodesk'"
Write-Host "already exists."
Write-Host "================================================"
Write-Host ""

Pause

git push -u origin main

# ------------------------------------------------------------
# Feature Branch
# ------------------------------------------------------------

git checkout -b feature/backtesting-engine

Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host " KiyoDesk setup completed successfully!"
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""

git status

Write-Host ""
Write-Host "Repository : $RepoURL"
Write-Host "Branch     : feature/backtesting-engine"
Write-Host ""