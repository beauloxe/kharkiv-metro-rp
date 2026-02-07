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

test:
    uv run pytest

lint:
    uv run ruff check .

format:
    uv run ruff format .

clean:
    rm -rvf .pytest_cache .ruff_cache .mypy_cache
