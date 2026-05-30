# Changelog

All notable changes to **PyAuditor** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [v1.2.0] - 2026-05-30
### Added
- **[Engine] Smart AST Engine:** The `blocking_in_async` rule now uses a context-aware Abstract Syntax Tree visitor. It intelligently ignores blocking calls (like `time.sleep`, `requests.get`, etc.) if they are safely wrapped inside nested local functions or lambdas, which are commonly used with `run_in_executor`.
- **[Rules] False Positive Eradication:** This architectural update effectively drops the false-positive rate to near zero for modern asynchronous codebases (like J.A.R.V.I.S.).

### Changed
- **[Engine] Rule Polish:** Enhanced general underlying rule parsing logic and AST recursive visitors for deeper detection without any performance loss.

---

## [v1.0.0] - Initial Release
### Added
- **[Engine] Two-Layer Analysis:** 25-rule AST-based static analysis engine with sub-second performance.
- **[AI Integration] BYOAI (Bring Your Own AI):** Prompt generator wrapper for pasting directly into Claude/ChatGPT without requiring an API key.
- **[UI] Custom GUI:** Dark-mode professional GUI built on `tkinter` with zero third-party dependencies.
- **[Rules] Deep Categories:** Critical, Warning, Potential, and Info severity levels to surface everything from hard crashes to future tech-debt.
- **[Auto Updater] update.py:** Secure, 1-click update tool that protects personal configurations and downloads directly from GitHub without requiring Git.

---

*(Earlier developmental histories can be found within the repository commit history.)*
