alias m := metro
alias mb := metro-bot
alias mm := metro-mcp

default:
    @just --list

metro *args:
    uv run metro {{args}}

metro-bot:
    uv run metro-bot

metro-mcp:
    uv run metro-mcp

# test:
#     uv run pytest

lint:
    uv run ruff check .

format:
    uv run ruff format .

clean:
    @rm -rvf dist
    @find . -type d \(      \
      -name "__pycache__"    \
      -o -name ".ruff_cache"  \
      -o -name ".pytest_cache" \
      -o -name ".mypy_cache" \) \
      -prune -exec rm -rvf {} +
