# Developer Guide

This guide covers how to set up a local development environment and run the test suite for `picsl_greedy`.

## Prerequisites

- **C++ compiler** with C++17 support (GCC 9+, Clang 11+, or MSVC 2019+)
- **CMake** 3.15+
- **Python** 3.8+
- The following libraries built and installed locally (or use `FETCH_DEPENDENCIES=ON` to let CMake fetch them automatically):
  - [ITK](https://github.com/InsightSoftwareConsortium/ITK) v5.4
  - [VTK](https://github.com/Kitware/VTK) v9.3
  - [Greedy](https://github.com/pyushkevich/greedy)

## Repository Layout

```
greedy_python/
├── CMakeLists.txt          # Top-level CMake build file
├── pyproject.toml          # Python packaging (scikit-build-core)
├── external/pybind11/      # pybind11 submodule
├── src/
│   ├── GreedyPythonBindings.cxx   # C++ ↔ Python bindings
│   └── picsl_greedy/              # Python package sources
├── tests/                  # pytest test suite
└── build/                  # Recommended out-of-tree build directory
```

## Option A — Local Build Against Pre-installed Dependencies

Use this approach when ITK, VTK, and Greedy are already built and installed on your machine (the typical developer workflow).

### 1. Configure and build

```bash
cd greedy_python

cmake -S . -B build \
    -DCMAKE_BUILD_TYPE=Release \
    -DFETCH_DEPENDENCIES=OFF \
    -DITK_DIR=<path/to/itk/install>/lib/cmake/ITK-5.4 \
    -DVTK_DIR=<path/to/vtk/install>/lib/cmake/vtk-9.3 \
    -DGreedy_DIR=<path/to/greedy/install>/lib/cmake/Greedy \
    -DPython3_EXECUTABLE=$(which python3)

cmake --build build --config Release -- -j$(nproc)   # Linux
cmake --build build --config Release -- -j$(sysctl -n hw.logicalcpu)  # macOS
```

### 2. Make the extension module importable in-source

After building, copy the compiled extension into the Python package so it can be imported without installation:

```bash
cp build/_picsl_greedy.cpython-*.so src/picsl_greedy/
```

The `build/config_and_build.sh` script packages these steps (with paths set to the local machine) as a convenience reference.

## Option B — Fetch All Dependencies Automatically

CMake can clone and build ITK, VTK, and Greedy from source. This is slower but requires no pre-installed libraries.

```bash
cmake -S . -B build \
    -DCMAKE_BUILD_TYPE=Release \
    -DFETCH_DEPENDENCIES=ON \
    -DPython3_EXECUTABLE=$(which python3)

cmake --build build --config Release -- -j$(nproc)

cp build/_picsl_greedy.cpython-*.so src/picsl_greedy/
```

## Option C — Install as a Wheel (pip / scikit-build-core)

For a fully packaged install (no manual CMake steps) use `pip` with `scikit-build-core`:

```bash
# With auto-fetched dependencies
FETCH_DEPENDENCIES=ON pip install -e .

# With pre-installed dependencies
CMAKE_PREFIX_PATH=<path/to/install> pip install -e .
```

## Running the Tests

### Test data

The test suite requires test data from the [greedy](https://github.com/pyushkevich/greedy) repository. The data directory is resolved in the following order:

1. The `GREEDY_TEST_DATA_DIR` environment variable, if set.
2. The relative sibling path `../greedy/testing/data` (works when both repos are checked out side-by-side).

If the directory is not found, the affected tests are automatically skipped.

### Install test dependencies

```bash
pip install pytest SimpleITK numpy
```

### Run the full suite

With the in-source `.so` (Option A/B above), set `PYTHONPATH` so Python can find both the package sources and the compiled extension:

```bash
PYTHONPATH=src:build \
GREEDY_TEST_DATA_DIR=/path/to/greedy/testing/data \
python -m pytest tests/
```

If you used `pip install -e .` the `PYTHONPATH` override is not needed:

```bash
GREEDY_TEST_DATA_DIR=/path/to/greedy/testing/data \
python -m pytest tests/
```

### Run a specific test file

```bash
PYTHONPATH=src:build python -m pytest tests/test_registration.py -v
PYTHONPATH=src:build python -m pytest tests/test_lmshoot.py -v
PYTHONPATH=src:build python -m pytest tests/test_propagation.py -v
```

## Code Style

C++ code is formatted with `clang-format` using the project's `.clang-format` configuration:

```bash
clang-format -i src/GreedyPythonBindings.cxx
```
