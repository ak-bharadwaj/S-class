import shutil
from pathlib import Path
from setuptools import setup
from setuptools.command.build_py import build_py

ROOT = Path(__file__).resolve().parent


class CustomBuildPy(build_py):
    def run(self):
        super().run()
        build_lib = Path(self.build_lib)

        # 1. Package under sclass/kernel
        kernel_dir = build_lib / "sclass" / "kernel"
        kernel_dir.mkdir(parents=True, exist_ok=True)
        init_file = kernel_dir / "__init__.py"
        if not init_file.exists():
            init_file.write_text('"""Verbatim canonical kernel package namespace."""\n', encoding="utf-8")

        # 2. Package under sclass/10-CONFORMANCE and sclass/20-RUNTIME so parents[1] / "10-CONFORMANCE" resolves
        conf_dir = build_lib / "sclass" / "10-CONFORMANCE"
        conf_dir.mkdir(parents=True, exist_ok=True)
        runt_dir = build_lib / "sclass" / "20-RUNTIME"
        runt_dir.mkdir(parents=True, exist_ok=True)

        conformance_dir = ROOT / "10-CONFORMANCE"
        for item in conformance_dir.iterdir():
            if item.is_file():
                shutil.copy2(item, kernel_dir / item.name)
                shutil.copy2(item, conf_dir / item.name)

        runtime_dir = ROOT / "20-RUNTIME"
        for item in runtime_dir.iterdir():
            if item.is_file():
                shutil.copy2(item, kernel_dir / item.name)
                shutil.copy2(item, runt_dir / item.name)


setup(
    cmdclass={
        "build_py": CustomBuildPy,
    }
)
