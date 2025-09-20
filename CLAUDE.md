# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Setup with uv

This codebase uses traditional pip installation but can be adapted to use `uv`:

```bash
# Traditional setup
cd PufferLib
pip install -e .
python setup.py build_ext --inplace --force

# With uv (preferred)
cd PufferLib
uv pip install -e .
uv run python setup.py build_ext --inplace --force
```

## Core Commands

**Training:**
```bash
uv run puffer train puffer_drone_pp                    # Basic training
uv run puffer train puffer_drone_pp --wandb           # With WandB logging
uv run puffer train puffer_drone_pp --neptune         # With Neptune logging
```

**Evaluation:**
```bash
uv run puffer eval puffer_drone_pp --model-file-path /path/to/model.pt
```

**Build C/C++ Extensions:**
```bash
uv run python setup.py build_ext --inplace --force
```

**Export to ONNX:**
```bash
uv run python export_onnx.py checkpoint.pt --output-dir onnx_export
```

## Architecture Overview

### Main Components
- **PufferLib Core**: High-performance RL library with C/C++ accelerated environments
- **Ocean Environments**: Custom C environments with Raylib rendering and Box2D physics
- **Drone Package Delivery**: Implemented in `/PufferLib/pufferlib/ocean/drone_pickplace/`

### Key Directories
- `/PufferLib/pufferlib/` - Main library code
- `/PufferLib/pufferlib/ocean/drone_pickplace/` - Drone environment implementation
- `/PufferLib/pufferlib/config/ocean/` - Environment configuration files
- `/PufferLib/examples/` - Usage examples

### Build System
- `setup.py` automatically downloads and builds Raylib and Box2D dependencies
- C/C++ extensions provide high-performance environment simulation (1M+ steps/second)
- Cross-platform support (Linux, macOS)

## Drone Environment Details

**Task Goal**: Train a drone to take off, locate a DHL package, pick it up, carry it to a goal location, and drop it.

**Environment Files**:
- `drone_pickplace.py` - Python interface
- `drone_pickplace.c/.h` - C implementation
- `binding.c` - Python-C binding layer

**Observation Space** (45 values):
- Drone state (14): position, velocity, quaternion, angular velocity, gripper
- Object states (21): 3 objects with position, velocity, status
- Target zones (8): 2 targets with position and occupancy flags
- Task info (2): time remaining, progress

**Action Space** (10 discrete):
- Movement: forward, backward, left, right, up, down
- Rotation: yaw left, yaw right
- Gripper: open, close

## Configuration System

Environment configs use INI format in `/PufferLib/pufferlib/config/ocean/drone_pickplace.ini`:
- Inherits from `/config/default.ini`
- Supports hyperparameter sweeps via `[sweep.*]` sections
- Environment-specific parameters like physics, rewards, episode length

## Model Architecture

- Default Policy class with configurable hidden layer sizes
- Optional RNN support for partial observability
- Automatic mixed precision training support
- PPO algorithm with advantage calculation

## Performance Features

- Vectorized environment execution with multiprocessing
- CUDA kernels for advantage calculation
- Zero-copy memory sharing between Python and C
- C/C++ implementation for environment physics and rendering

## Development Notes

- Two drone variants exist: `puffer_drone_pickplace` (main) and `puffer_drone_pp` (alternative)
- The `.pt` files in the root are trained model checkpoints
- Build extensions after any C code changes
- Use WandB or Neptune for experiment tracking
- ONNX export supports Isaac Sim integration for real-world deployment