"""Make every pip-installed NVIDIA runtime (CUDA 12 for faster-whisper/ctranslate2, CUDA 13 for onnxruntime-gpu,
cuDNN 9) loadable on Windows. Import this BEFORE onnxruntime / faster_whisper."""
import os
import pathlib
import site

_done = False


def setup():
    global _done
    if _done or os.name != "nt":          # only Windows needs the DLL search path
        _done = True
        return
    for base in site.getsitepackages() + [site.getusersitepackages()]:
        nv = pathlib.Path(base) / "nvidia"
        if not nv.exists():
            continue
        for b in list(nv.glob("*/bin")) + list(nv.glob("*/bin/x86_64")) + list(nv.glob("*/*/bin")):
            if b.is_dir():
                os.add_dll_directory(str(b))
                os.environ["PATH"] = str(b) + os.pathsep + os.environ["PATH"]
    _done = True


setup()
