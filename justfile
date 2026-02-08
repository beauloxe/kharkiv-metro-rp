alias m := metro
alias mb := metro-bot
alias mm := metro-mcp
alias l := lint
alias f := format
alias c := clean
alias d := demo


_default:
    @just --list

# Run metro cli
metro *args:
    uv run metro {{args}}

# Run metro-bot
metro-bot:
    uv run metro-bot

# Run metro-mcp
metro-mcp:
    uv run metro-mcp

# test:
#     uv run pytest

# Lint with `ruff check`
lint *args:
    uv run ruff check . {{args}}

# Format code with `ruff format`
format:
    uv run ruff format .

vhs-script := '
    Set FontFamily "IosevkaTerm Nerd Font Mono"
    Set TypingSpeed 0.02

    Set Padding 16
    Set BorderRadius 12
    Set Margin 8
    Set WindowBar RingsRight

    Set LetterSpacing 2
    Set FontSize 18
    Set Width 1100
    Set Height 600

    Type "metro route салтівська турбоатом -t 07:25 -s weekday -f full"
    Sleep 0.5s
    Enter

    Sleep 2s

    Type "metro route салтівська турбоатом -t 07:25 -s weekday -f simple"
    Sleep 0.5s
    Enter

    Sleep 4s

    Type "metro route салтівська турбоатом -t 07:25 -s weekday -f full --compact"
    Sleep 0.5s
    Enter

    Sleep 2s

    Type "metro route салтівська турбоатом -t 07:25 -s weekday -f simple --compact"
    Sleep 0.5s
    Enter

    Sleep 10s
'

_pre-demo:
    just metro config set preferences.route.compact false

[working-directory: 'assets']
_demo-dark: _pre-demo
    #!/usr/bin/env vhs
    Output route_demo.gif
    Set Theme "GruvboxDarkHard"
    Set MarginFill "#0D1117"

    {{vhs-script}}

[working-directory: 'assets']
_demo-light: _pre-demo
    #!/usr/bin/env vhs
    Output route_demo_light.gif
    Set Theme "Gruvbox Light"
    Set MarginFill "#FFFFFF"

    {{vhs-script}}

# Generate demo GIFs in assets/
demo: _demo-dark _demo-light

# Clean all cache directories
clean:
    @rm -rvf dist
    @find . -type d \(     \
      -name "dist"          \
      -o -name "__pycache__" \
      -o -name ".ruff_cache"  \
      -o -name ".pytest_cache" \
      -o -name ".mypy_cache" \) \
      -prune -exec rm -rvf {} +
