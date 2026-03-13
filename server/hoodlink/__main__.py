import argparse
import os
import sys

_LIME = "\033[38;5;154m"
_RESET = "\033[0m"

_BANNER = """\
 ██╗  ██╗ ██████╗  ██████╗ ██████╗ ██╗     ██╗███╗   ██╗██╗  ██╗
 ██║  ██║██╔═══██╗██╔═══██╗██╔══██╗██║     ██║████╗  ██║██║ ██╔╝
 ███████║██║   ██║██║   ██║██║  ██║██║     ██║██╔██╗ ██║█████╔╝
 ██╔══██║██║   ██║██║   ██║██║  ██║██║     ██║██║╚██╗██║██╔═██╗
 ██║  ██║╚██████╔╝╚██████╔╝██████╔╝███████╗██║██║ ╚████║██║  ██╗
 ╚═╝  ╚═╝ ╚═════╝  ╚═════╝ ╚═════╝ ╚══════╝╚═╝╚═╝  ╚═══╝╚═╝  ╚═╝\
"""


def main() -> None:
    color = _LIME if sys.stderr.isatty() else ""
    reset = _RESET if sys.stderr.isatty() else ""
    print(f"\n{color}{_BANNER}{reset}\n", file=sys.stderr)

    parser = argparse.ArgumentParser(
        prog="hoodlink-server", description="HoodLink bridge server"
    )
    parser.add_argument(
        "--api-key",
        metavar="KEY",
        help="API key for authenticating requests (overrides HOODLINK_API_KEY)",
    )
    args = parser.parse_args()

    if args.api_key:
        os.environ["HOODLINK_API_KEY"] = args.api_key

    # Import after env vars are set so Settings() picks them up
    import uvicorn

    from hoodlink.config import settings
    from hoodlink.main import app

    uvicorn.run(app, host=settings.host, port=settings.port, log_level=settings.log_level)


if __name__ == "__main__":
    main()
