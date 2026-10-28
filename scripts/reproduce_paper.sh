#!/usr/bin/env bash
set -euo pipefail
# Reproduces synthetic computations, job-shop benchmark comparisons, sensitivity,
# fault injection, MILP subsets, holdout tests, multi-seed ARK and figures.
# CPU intensive; archived publication results can vary by software version where
# exact MIP solver algorithm selection and floating-point behavior differ.
cd "$(dirname "$0")/../research"
python run_experiments.py
python run_sensitivity.py
python external_benchmarks.py
python fault_injection.py
python exact_subset.py
python holdout_test.py
python ark_multiseed.py
python bootstrap_diagnostic.py
python figures_new.py
