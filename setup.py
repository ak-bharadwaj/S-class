import shutil
from pathlib import Path
from setuptools import setup
from setuptools.command.build_py import build_py

ROOT = Path(__file__).resolve().parent


class CustomBuildPy(build_py):
    def run(self):
        super().run()
        build_lib = Path(self.build_lib)

        # Clean up any stale build directories
        for stale_dir in [build_lib / "sclass" / "10-CONFORMANCE", build_lib / "sclass" / "20-RUNTIME"]:
            if stale_dir.exists():
                shutil.rmtree(stale_dir)

        # 1. Package under sclass/kernel
        kernel_dir = build_lib / "sclass" / "kernel"
        kernel_dir.mkdir(parents=True, exist_ok=True)
        init_file = kernel_dir / "__init__.py"
        init_file.write_text(
            '"""Verbatim canonical kernel package namespace."""\n'
            'import sys\n'
            'from pathlib import Path\n'
            '\n'
            '# Ensure local kernel directory is in sys.path for direct module resolution\n'
            '_kernel_dir = str(Path(__file__).resolve().parent)\n'
            'if _kernel_dir not in sys.path:\n'
            '    sys.path.insert(0, _kernel_dir)\n'
            '\n'
            '# Fallback for state-machines.v6.0.1.json when installed from wheel\n'
            '_orig_read_text = Path.read_text\n'
            '\n'
            'def _kernel_read_text(self, *args, **kwargs):\n'
            '    try:\n'
            '        return _orig_read_text(self, *args, **kwargs)\n'
            '    except FileNotFoundError:\n'
            '        if "10-CONFORMANCE" in str(self) and "state-machines.v6.0.1.json" in str(self):\n'
            '            alt = Path(__file__).resolve().parent / "state-machines.v6.0.1.json"\n'
            '            if alt.exists():\n'
            '                return _orig_read_text(alt, *args, **kwargs)\n'
            '        raise\n'
            '\n'
            'Path.read_text = _kernel_read_text\n',
            encoding="utf-8",
        )

        # Ship exactly ONE copy of each kernel module and only data files needed at runtime
        kernel_files = [
            (ROOT / "10-CONFORMANCE" / "sclass_semantics_v6_0_1.py", kernel_dir / "sclass_semantics_v6_0_1.py"),
            (ROOT / "10-CONFORMANCE" / "sclass_kernel_v6_0_1.py", kernel_dir / "sclass_kernel_v6_0_1.py"),
            (ROOT / "20-RUNTIME" / "sclass_runtime_v6_0_1.py", kernel_dir / "sclass_runtime_v6_0_1.py"),
            (ROOT / "10-CONFORMANCE" / "c1-vectors.v6.0.1.json", kernel_dir / "c1-vectors.v6.0.1.json"),
            (ROOT / "10-CONFORMANCE" / "state-machines.v6.0.1.json", kernel_dir / "state-machines.v6.0.1.json"),
        ]
        for src, dst in kernel_files:
            shutil.copy2(src, dst)


setup(
    cmdclass={
        "build_py": CustomBuildPy,
    }
)
