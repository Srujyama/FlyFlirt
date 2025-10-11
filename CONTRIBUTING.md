# Contributing to FlyFlirt

Thank you for your interest in contributing to **FlyFlirt**, a toolkit for Drosophila behavior analysis.  
We welcome bug reports, feature requests, code improvements, and documentation edits.

---

## How You Can Contribute

- Report reproducible bugs and issues.
- Propose or implement new features.
- Improve documentation and readability.
- Optimize or refactor analysis routines.
- Add or improve automated tests.

---

## Contribution Workflow

1. **Fork the repository**

   Click **Fork** in the top-right corner of the repository page.

2. **Clone your fork**
   ```bash
   git clone https://github.com/yourusername/FlyFlirt.git
   cd FlyFlirt
   ```

3. **Create a new branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

4. **Install in editable mode**
   ```bash
   pip install -e .
   ```

5. **Make and test your changes**

   - Follow the project’s style and structure.
   - Add docstrings and type hints for clarity.
   - Ensure your code runs without errors or regressions.

6. **Commit and push**
   ```bash
   git add .
   git commit -m "Add short description of change"
   git push origin feature/your-feature-name
   ```

7. **Submit a pull request**

   Open a pull request to the `main` branch with:
   - A concise summary of your change.
   - Any related issue numbers (e.g., `Fixes #12`).
   - Notes on testing or reproducibility if relevant.

---

## Code Style

- Follow **PEP 8** formatting.
- Use clear, descriptive variable names.
- Include **type hints** where possible.
- Keep lines under 100 characters.
- Write **docstrings** for all public functions and classes.
- Avoid global variables; encapsulate logic in functions or classes.

---

## Testing

Unit and functional tests should go in the `tests/` directory.

Run tests locally before submitting:
```bash
pytest
```

If adding new functionality:
- Include a small, representative test video or dataset if applicable.
- Add assertions verifying correct output behavior.

---

## Communication

If you are considering a major feature, open an **Issue** first to discuss it.  
Use clear, concise language and link related commits or documents when possible.

---

## License

By contributing to this repository, you agree that your contributions will be licensed under the same [MIT License](LICENSE) as the rest of the project.

---

## Acknowledgment

FlyFlirt is a collaborative, open-source project intended for reproducible behavioral analysis in research.  
Every contribution helps improve accessibility, accuracy, and scientific transparency.
