# Contributing to AI-Powered Concert Stage Backdrop Generator

Thank you for your interest in contributing to the AI-Powered Concert Stage Backdrop Generator! We welcome contributions, bug reports, feature requests, and documentation improvements.

---

## Code of Conduct

Please maintain a respectful and welcoming environment for all contributors. Focus on constructive feedback and productive collaboration.

---

## How to Contribute

### 1. Reporting Bugs
Before creating a bug report, please check existing issues to avoid duplicates. When filing a bug report, include:
- Operating System and Python version
- Steps to reproduce the issue
- Relevant error logs or terminal output
- Expected vs actual behavior

### 2. Suggesting Enhancements
Feature requests are welcome! Please provide:
- A clear description of the proposed feature
- Use cases and motivation for the feature
- Possible implementation details or API changes if applicable

### 3. Submitting Pull Requests
1. **Fork the Repository**: Create your own fork of the repository on GitHub.
2. **Clone your Fork**:
   ```bash
   git clone https://github.com/your-username/stage-backdrops.git
   cd stage-backdrops
   ```
3. **Create a Feature Branch**:
   ```bash
   git checkout -b feature/your-feature-name
   ```
4. **Set Up Development Environment**:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
5. **Make Changes and Test**:
   Ensure all Python scripts execute cleanly without syntax errors:
   ```bash
   python3 -m py_compile *.py
   ```
6. **Commit Changes**: Write clear, descriptive commit messages.
7. **Push and Create PR**: Push your branch to your fork and submit a Pull Request to the `main` branch.

---

## Code Style & Standards

- **Python**: Follow PEP 8 guidelines where applicable.
- **Type Hints & Docstrings**: Keep functions well-documented with clear docstrings.
- **No Secrets in Code**: Never commit API keys or secret credentials. Use `.env` for local configuration.
