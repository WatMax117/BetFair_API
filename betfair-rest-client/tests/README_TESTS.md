# Risk module tests

Run from `betfair-rest-client` directory:

```bash
pip install -r requirements-dev.txt
pytest tests/test_risk.py -v --tb=short
```

## Expected output (all 6 tests PASSED)

```
tests/test_risk.py::test_normal_market_three_runners PASSED
tests/test_risk.py::test_swapped_runner_order PASSED
tests/test_risk.py::test_empty_or_missing_available_to_back PASSED
tests/test_risk.py::test_missing_one_selection_two_runners PASSED
tests/test_risk.py::test_depth_limit_levels_four_plus_ignored PASSED
tests/test_risk.py::test_golden_sample_real_world_json PASSED
======================== 6 passed in X.XXs ================================
```

## Run via Docker (if Python not installed locally)

```bash
docker build -t betfair-rest-client-test .
docker run --rm betfair-rest-client-test python -m pytest tests/test_risk.py -v --tb=short
```

(Ensure the Dockerfile COPY includes the `tests/` directory.)
