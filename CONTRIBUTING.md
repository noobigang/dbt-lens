# Contributing to dbt Lens

Thank you for your interest in contributing! 🎉

## How to contribute

### 🐛 Bug reports

Please open a [GitHub Issue](https://github.com/noobigang/dbt-lens/issues) with:
- A clear title describing the bug
- Steps to reproduce the issue
- What you expected vs. what happened
- Your OS and Python version

### 💡 Feature requests

Open a GitHub Issue tagged as `enhancement`. Describe:
- The problem you're trying to solve
- How you envision it working
- Why this would be useful to other users

### 🔧 Code contributions

1. **Fork the repo** and create your branch from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Run the app locally** to test your changes:
   ```bash
   pip install -r requirements.txt
   streamlit run app.py
   ```

3. **Make your changes.** Keep these in mind:
   - All scoring logic lives in `dbtlens/scorer.py` — if you're changing the score, update the dimension weights and notes there
   - DAG rendering lives in `dbtlens/dag_renderer.py` — keep the fallback HTML clean and minimal
   - The share card generator lives in `dbtlens/card_generator.py` — PNG output must stay at 1200×630

4. **Commit** with a clear message:
   ```bash
   git commit -m "Add: feature name — brief description"
   ```

5. **Push and open a Pull Request** on GitHub.

### 📏 Code style

- Python: follow [PEP 8](https://pep8.org/)
- Variable names: descriptive, `snake_case`
- Comments: explain *why*, not *what*
- No magic numbers — use named constants for dimension weights

### ✅ Checklist before submitting a PR

- [ ] App runs without errors (`streamlit run app.py`)
- [ ] "Load example project" still produces a valid score
- [ ] No new `print()` statements left in the code
- [ ] New files are covered by the existing structure

## 🙏 Thank you

Every contribution makes dbt Lens better for the whole dbt community.