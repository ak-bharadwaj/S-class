"""Cosmic Ray CLI runner wrapper for Windows compatibility."""

import sys

import cosmic_ray.cli

if __name__ == "__main__":
    sys.argv = ["cosmic-ray"] + sys.argv[1:]
    cosmic_ray.cli.main()
