# Testing Agent Guide
Agents must read this file before making changes within this directory scope.

## Scope
This file applies to all test code under `tests/`.

The root `AGENTS.md` still applies. This guide adds test-specific rules.

## Testing Principles
- Test behavior, not implementation details.
- Keep tests fast, deterministic, and independent of local hardware.
- Prefer simple `unittest` tests that match the existing suite.
- Use focused test doubles for external dependencies.

## Strategy
- Gesture detection and landmark math -> pure unit tests with synthetic landmarks.
- Gesture session state -> deterministic tests with explicit timestamps.
- Configuration parsing -> isolated environment dictionaries.
- Crop, projection, and zoom math -> deterministic frame or geometry fakes.
- Application orchestration -> use fakes for OpenCV, TV adapters, MediaPipe, audio, and task boundaries as needed.

## Rules
- Do not require a real webcam, TV, microphone, network, certificates, downloaded model, or MediaPipe runtime in normal tests.
- Do not add sleeps or timing-dependent tests when explicit timestamps can be passed.
- Do not over-mock pure domain behavior.
- Keep helper fixtures local unless multiple test modules need them.
- Preserve clear test names that describe observable behavior.

## Validation
Run the full suite before concluding test-related changes:

```bash
python -m unittest discover -s tests
```
