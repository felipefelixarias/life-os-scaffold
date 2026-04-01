# Contributing to life-os-scaffold

Thank you for your interest in contributing to life-os-scaffold! This document provides guidelines for contributing to the project.

## Development Setup

1. **Clone and setup**:
   ```bash
   git clone https://github.com/felipefelixarias/life-os-scaffold.git
   cd life-os-scaffold
   make setup
   ```

2. **Install development dependencies**:
   ```bash
   pip install -e .[dev]
   ```

3. **Run tests**:
   ```bash
   make test
   make lint
   ```

## Code Quality Standards

### Testing
- All new functionality must include tests
- Tests should cover edge cases and error conditions
- Maintain test coverage above 80%
- Run `make test` before submitting changes

### Code Style
- Use Ruff for formatting: `ruff format .`
- Follow PEP 8 conventions with 100-character line limit
- Use type hints for all function parameters and return values
- Run `ruff check .` to check for style issues

### Type Checking
- All Python code must pass mypy type checking
- Use proper type annotations
- Run `mypy 01-ops/life-os/scripts/` before submitting

## Project Structure

### Key Directories
- `01-ops/life-os/scripts/` - Core Python modules
- `.claude/commands/` - Command definitions for Claude Code
- `tests/` - Unit and integration tests
- `docs/` - Documentation files

### CSV Schemas
- All CSV files must follow the schemas defined in `validate_repo.py`
- Changes to schemas require updating validation rules
- Example data should remain minimal and generic

### Command Files
- Follow the format: `# /command-name — Description`
- Include clear step-by-step instructions
- Test commands manually before submitting
- Update command references in documentation

## Making Changes

### Before You Start
1. Check existing issues for similar requests
2. Create an issue to discuss large changes
3. Fork the repository and create a feature branch

### Development Workflow
1. Create a branch: `git checkout -b feature/your-feature-name`
2. Make your changes
3. Add/update tests for your changes
4. Run the full test suite: `make test && make lint`
5. Run type checking: `mypy 01-ops/life-os/scripts/`
6. Check code formatting: `ruff check . && ruff format --check .`
7. Commit with clear messages
8. Push and create a pull request

### Commit Messages
Use clear, descriptive commit messages:
```
Add CSV cross-reference validation

- Validate project_id references in tasks.csv
- Check goal areas align with task domains
- Add comprehensive error reporting
```

## Types of Contributions

### Bug Fixes
- Include a test that reproduces the bug
- Fix the issue with minimal changes
- Ensure all tests pass

### New Features
- Discuss in an issue first for large features
- Follow existing patterns and conventions
- Include comprehensive tests and documentation
- Update relevant command files

### Documentation
- Fix typos and improve clarity
- Add examples where helpful
- Keep documentation up-to-date with code changes

### Command Improvements
- Follow the existing command format
- Test commands thoroughly
- Update help text and documentation

## Validation and Testing

### Repository Validation
The project includes comprehensive validation:
- CSV schema validation
- Cross-reference checking
- File permissions verification
- Configuration structure validation
- Command file validation

### Running Validations
```bash
# Quick validation
make lint

# Full validation with tests
make test

# Detailed validation output
python3 01-ops/life-os/scripts/validate_repo.py --verbose
```

### Test Coverage
- Unit tests for all Python modules
- Integration tests for key workflows
- Validation tests for all CSV schemas
- Mock tests for Google Calendar integration

## Error Handling

### Best Practices
- Use proper exception handling
- Log errors with appropriate levels
- Provide helpful error messages
- Fail gracefully with meaningful feedback

### Google Calendar Integration
- Handle authentication failures gracefully
- Provide clear error messages for API issues
- Test with mocked responses

## Questions and Support

- Check existing issues and documentation first
- Create an issue for bugs or feature requests
- Join discussions on existing issues
- Be patient and respectful in all interactions

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

Thank you for helping improve life-os-scaffold!