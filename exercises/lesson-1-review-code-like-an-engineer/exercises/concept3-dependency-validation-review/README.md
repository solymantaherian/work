# Concept 3: Dependency Validation Review

## Exercise Overview

Review a file-processing module for dependency and structural issues. The sample in `starter/file_processor.py` loads several file formats with pandas and cleans numeric columns with scikit-learn.

This exercise teaches dependency validation the way it actually goes in practice: **you verify every import, and sometimes they all check out.** A clean import audit is not a passing review — it means the defects are somewhere else, and you still have to go find them. The sample here imports only real, correctly-used libraries, and it still has bugs that will crash on real uploads.

## Learning Objectives

- Verify that imported libraries exist, are maintained, and are used with correct signatures
- Recognize phantom libraries and the naming patterns that produce them
- Spot the subtler dependency problems that survive an import check: undeclared requirements, optional engines, and dependency weight that isn't justified
- Apply a structural review (organization, error handling, testability) after the import audit comes back clean
- Resist confirmation bias — don't manufacture a finding because you expected one

## 🤖 AI-Specific Focus

Patterns commonly found in AI-generated code. Pay attention to:

- Library imports and dependencies, including ones that are real but undeclared
- Function signatures and keyword arguments — real library, wrong or defaulted parameter
- Code that looks polished (type hints, full docstrings, logging) but whose steps don't compose correctly
- Docstrings that describe intended behavior rather than actual behavior
- Context awareness and completeness — functions defined but never wired in

## Instructions

### Step 1: Audit the Dependencies

Work through the imports at the top of `starter/file_processor.py` before reading any function bodies. For each one, establish that the package exists, that the symbol is importable from that module path, and that it is called with a signature the library actually accepts.

```bash
cd concept3-dependency-validation-review/starter

# Are the packages installed, and at what versions?
python -c "import importlib.metadata as md; [print(p, md.version(p)) for p in ['pandas','scikit-learn']]"

# Do the specific symbols resolve from the specific module paths?
python -c "from sklearn.impute import SimpleImputer; from sklearn.preprocessing import StandardScaler; print('symbols OK')"

# Does the real signature match how the code calls it?
python -c "import inspect; from sklearn.impute import SimpleImputer; print(inspect.signature(SimpleImputer.__init__))"
```

**Expected output:** every import resolves, and every call site matches a real signature. Record that result and move on — the import audit is one pass of the review, not the whole review.

Then ask the questions an import check *cannot* answer:

- Is there a `requirements.txt` or `pyproject.toml` in this directory declaring these packages? What Python version does the type-hint syntax require?
- `load_file` advertises four formats. Which of them work with pandas alone, and which silently need an extra engine package? Try each format in this environment and see what happens.
- Is the heaviest dependency earning its place, or is it doing something the lighter dependency already does?

### Step 2: Review the Code

1. **Open** `starter/file_processor.py`
2. **Apply** the engineering code review framework:
   - Structure & Organization
   - Naming & Clarity
   - Error Handling
   - Dependency Validation
3. **Trace the order of operations** inside each function. After one step has run, does the next step still do what its comment claims? Look especially at any step that fills in missing data followed by a step that removes missing data.
4. **Run the functions on awkward input** rather than reading only. A column that is entirely empty, a column where every value is identical, a list where one path doesn't exist, a path that is a directory. Construct small frames and call the functions directly.
5. **Follow the return value.** If you pass five files and get fewer results back, what does the caller know about which ones failed?
6. **Check for unused code.** Is every function defined in the module actually called by something?

### Step 3: AI Pattern Detection

Apply the AI-specific checks:

- Library names that sound "too good to be true" — generic quality words bolted onto a function (`advanced_*`, `*_pro`, `fast_*`, `quick_*`)
- Parameters that sound too convenient — `auto_detect`, `optimization_level`, anything promising magic
- Real libraries used at their defaults where the default is wrong for the use case
- Surface polish (docstrings, type hints, structured logging) standing in for correctness
- Broad `except Exception` blocks that log and continue, hiding the failure from the caller

For reference, these are the phantom-library patterns this lesson warns about. Confirm for yourself that they don't exist, so you know what a true negative looks like:

```bash
python -c "
for m in ['advanced_file_processor','data_cleaner_pro']:
    try: __import__(m); print(m,'IMPORTS')
    except ImportError as e: print(m,'->',e)
"
```

### Step 4: Run the Solution Tests

```bash
cd ../solution
pytest test_real_dependencies.py -v
```

**Expected output:** 15 tests pass. These exercise real libraries only, with specific exception types and logging rather than `print()`.

### Step 5: Compare and Learn

Read `solution/file_processor.py` alongside your review notes. It demonstrates the target patterns — verified imports, `logging` instead of `print()`, specific exception types, and input validation before processing.

Note that it is **not** a line-for-line fix of the starter: it has no scikit-learn step, its cleaning function is named `clean_dataframe` rather than `clean_dataset`, and it has no `load_file`. Read it for the patterns, not as an answer key for the starter's defects. Several of the starter's most serious problems live in code the solution simply doesn't contain, which is a useful lesson in itself — a reference implementation only protects you where it overlaps with what you shipped.

## Review Template

### Dependency Analysis

**Import verification** — confirm each, don't assume:

- [ ] `os` — real? Std lib ✅ / ❌
- [ ] `logging` — real? Std lib ✅ / ❌
- [ ] `pandas` — real? ✅ / ❌ — version: \_\_\_\_
- [ ] `sklearn.impute.SimpleImputer` — real, and importable from that path? ✅ / ❌
- [ ] `sklearn.preprocessing.StandardScaler` — real, and importable from that path? ✅ / ❌
- [ ] Every call site matches the real signature? ✅ / ❌

**Phantom library detection:**

- [ ] Any import that cannot be resolved to a package on PyPI: \_\_\_\_\_\_\_\_
- [ ] Any import resolved to a package that is unmaintained or deprecated: \_\_\_\_\_\_\_\_
- [ ] Result of this audit: All real / Some fake / Uncertain

**Beyond the import check:**

- [ ] Dependencies declared in a manifest? Which are missing: \_\_\_\_\_\_\_\_
- [ ] Minimum Python version implied by the syntax, and is it stated anywhere: \_\_\_\_\_\_\_\_
- [ ] Optional engines needed by advertised formats, and which are actually installed: \_\_\_\_\_\_\_\_
- [ ] Is each dependency's weight justified by what it's used for: \_\_\_\_\_\_\_\_
- [ ] Import-time side effects on the importing application: \_\_\_\_\_\_\_\_

### AI-Specific Red Flags

**Missing context:**

- [ ] Does the code match what was requested?
- [ ] Is any expected functionality missing?
- [ ] Are there unexplained gaps in logic, or functions that are never called?

**Plausible but wrong:**

- [ ] Libraries that sound real but aren't
- [ ] Function calls with incorrect signatures
- [ ] Real functions left at a default that's wrong for this use case
- [ ] Outdated or deprecated patterns
- [ ] Docstrings that describe intent rather than actual behavior

### Code Quality Issues

**Correctness:**

- [ ] Does any operation undo, mask, or invalidate a previous one? Where: \_\_\_\_\_\_\_\_
- [ ] What happens on an all-empty column? A constant column? \_\_\_\_\_\_\_\_
- [ ] Does any step fabricate data the caller can't distinguish from real data? \_\_\_\_\_\_\_\_

**Error handling:**

- [ ] Generic exception handling: \_\_\_\_\_\_\_\_
- [ ] Missing specific error types: \_\_\_\_\_\_\_\_
- [ ] Are failures reported to the caller, or only to the log? \_\_\_\_\_\_\_\_
- [ ] Can the caller tell which inputs succeeded? \_\_\_\_\_\_\_\_
- [ ] Are tracebacks preserved for unexpected errors? \_\_\_\_\_\_\_\_

**Logging and debugging:**

- [ ] `print()` used where logging belongs: \_\_\_\_\_\_\_\_
- [ ] Logging configured at import time in library code: \_\_\_\_\_\_\_\_
- [ ] Missing debug information: \_\_\_\_\_\_\_\_

**Function design and testability:**

- [ ] Do functions mix I/O, transformation, and logging in ways that make them hard to test?
- [ ] Are fitted objects or intermediate state discarded when the caller needs them?
- [ ] Is input validated at the boundary, or does a bad value fail deep inside a library?
- [ ] Could you test the failure paths without capturing log output?

**Input handling:**

- [ ] What happens with `None`? With a string instead of a list? \_\_\_\_\_\_\_\_
- [ ] Are the paths constrained to an expected location, given these are "uploaded" files? \_\_\_\_\_\_\_\_
- [ ] Memory behavior with many or large files: \_\_\_\_\_\_\_\_

### Replacement Recommendations

**For any phantom library found, suggest a real alternative:**

| Phantom pattern | Real alternative |
|---|---|
| `advanced_file_processor` | `pandas` + the format engine (`openpyxl`, `pyarrow`), `chardet` for encoding |
| `data_cleaner_pro` | `pandas`, `numpy`, `scikit-learn` |
| `fast_*` / `*_master` | Profile first, then reach for the maintained library that targets the bottleneck |

**For code improvements — rank by severity, blocking first:**

1. \_\_\_\_\_\_\_\_
2. \_\_\_\_\_\_\_\_
3. \_\_\_\_\_\_\_\_

### Overall Assessment

- **AI pattern recognition:** What did the import audit actually turn up, and did you keep reviewing afterward?
- **Quality rating:** Poor / Fair / Good / Excellent
- **Primary issue:** Dependency problems / Code quality / Both
- **Recommendation:** Accept / Modify / Reject

### Self-Check

Once you've finished, compare against the count. In `starter/file_processor.py` there are:

- **0** phantom libraries and **0** incorrect signatures
- **2** defects that crash or silently corrupt data on realistic input
- **1** design flaw that makes the returned datasets unusable for their apparent purpose
- **1** function that is defined but never called
- **several** dependency-hygiene and input-validation gaps

If you found zero issues because the imports checked out, re-read Step 2. If you reported a phantom library, re-read Step 1 — a finding you can't reproduce on demand isn't a finding.

## How to Verify Libraries

1. **Check PyPI:** search for the package on [pypi.org](https://pypi.org) — note the last release date, not just that a page exists
2. **Try the import:** `python -c "import <pkg>; print(<pkg>.__version__)"`
3. **Check the specific symbol:** a real package can still lack the class or function being imported from it — `from <pkg>.<module> import <Name>`
4. **Check the signature:** `python -c "import inspect, <pkg>; print(inspect.signature(<pkg>.<Name>.__init__))"` — real library, invented keyword argument is a common failure
5. **Check the version index:** `pip index versions <pkg>` (note: `pip search` was disabled by PyPI in 2021 and no longer works)
6. **GitHub:** is there an active repository, and recent commits?
7. **Official docs:** does the documented API match the call in the code, for the version you have installed?

## Common AI Library Issues

**Phantom libraries:**

- Packages that sound plausible but don't exist
- Combinations of real words that seem legitimate
- Real packages that are abandoned or renamed

**Version mismatches:**

- Using deprecated APIs
- Mixing incompatible versions
- Invented keyword arguments on real functions
- Relying on a default that changed between versions

**Undeclared and hidden dependencies:**

- Imports with no corresponding manifest entry
- Optional engines a documented feature quietly requires
- A heavyweight dependency pulled in for something the existing one already does

**Context loss:**

- Missing imports for referenced functions
- Incomplete implementations
- Functions that don't match their names or docstrings
- Helpers defined but never wired into the code path they were written for

## Red Flag Patterns

🚩 Libraries with generic, appealing names:

- `advanced_[something]_processor`
- `[domain]_pro` or `[domain]_master`
- `fast_[operation]` or `quick_[tool]`

🚩 Function calls that seem too convenient:

- Methods with `auto_detect` parameters
- One-line solutions to complex problems
- Perfect APIs that handle everything

🚩 Polish standing in for correctness:

- Thorough docstrings on a function whose steps cancel each other out
- Type hints and structured logging around an unhandled edge case
- A `Raises:` section listing exceptions the code never raises

## Known Issue

`starter/test_phantom_libraries.py` does not currently run. It imports `ADVANCED_PROCESSOR_AVAILABLE` and `DATA_CLEANER_AVAILABLE` from `file_processor`, which don't exist in the current starter, so pytest fails at collection:

```
E ImportError: cannot import name 'ADVANCED_PROCESSOR_AVAILABLE' from 'file_processor'
```

Its assertions also expect `print()` calls and phantom imports that the current starter doesn't contain. Skip that file and use the Step 1 commands above; `solution/test_real_dependencies.py` is unaffected and passes.
