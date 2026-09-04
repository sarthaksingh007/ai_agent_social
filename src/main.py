"""
Entry point — SETUP VERIFICATION ONLY (agents come later).

Running this confirms the foundation works:
  1. Environment variables are loaded.
  2. The Groq key is present.
  3. PostgreSQL is reachable and the `posts` table exists.
"""
from src import config
from src.db import ping


def main() -> None:
    print("=" * 55)
    print(" Social Media Agency Pipeline — setup check")
    print("=" * 55)

    problems = config.check()

    # Database
    try:
        ping()
        print("[ok]   PostgreSQL reachable, `posts` table present")
    except Exception as exc:  # noqa: BLE001
        problems.append(f"Database not ready: {exc}")

    if problems:
        print("\n[!] Setup incomplete:")
        for p in problems:
            print(f"    - {p}")
        print("\nFix the above, then re-run.")
        return

    print(f"[ok]   LLM model: {config.LLM_MODEL}")
    print("\nSetup looks good.")


if __name__ == "__main__":
    main()
