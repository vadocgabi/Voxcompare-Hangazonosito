"""VoxCompare - Hangazonosító - launcher.

    python main.py                          start the application
    python main.py --compare A.wav B.wav    headless comparison (prints the score)
    python main.py --version
"""
import sys
import warnings

warnings.filterwarnings("ignore")  # third-party deprecation noise (torch, torchaudio, speechbrain)


def main(argv: list) -> int:
    if "--version" in argv:
        from voxcompare import __version__
        print(f"VoxCompare {__version__}")
        return 0
    if argv[:1] == ["--compare"]:
        from voxcompare.engine import main_compare
        return main_compare(argv[1:])
    from voxcompare.ui import run
    run()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
