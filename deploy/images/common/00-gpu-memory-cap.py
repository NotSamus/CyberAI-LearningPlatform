# Executed at kernel start (see gpu/Dockerfile): soft per-student VRAM cap when several students share one GPU.
# A determined student can remove it; the hard limits are the session cap and the idle culler.
import os

_frac = float(os.environ.get("GPU_MEM_FRACTION", "0") or 0)
if 0 < _frac < 1:
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.set_per_process_memory_fraction(_frac, 0)
    except Exception:
        pass
