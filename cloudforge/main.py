"""
cloudforge/main.py

Entrypoint for the poller loop.
"""

from cloudforge.github_app.poller import run_forever


def main() -> None:
    run_forever()


if __name__ == "__main__":
    main()
