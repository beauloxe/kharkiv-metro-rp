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
    Set FontFamily "Maple Mono"
    Set TypingSpeed 0.02

    Set Padding 16
    Set BorderRadius 12
    Set Margin 2
    Set WindowBar RingsRight

    # Set LetterSpacing 2
    Set FontSize 18
    Set Width 1200
    Set Height 800

    Type "# 1. Побудова маршруту (route)"
    Enter

    Type "metro route салтівська турбоатом -t 07:25 -s weekday -f full"
    Sleep 0.5s
    Enter

    Sleep 2s

    Type "metro route салтівська турбоатом -t 07:25 -s weekday -f simple"
    Sleep 0.5s
    Enter

    Sleep 4s

    Hide
    Type "clear"
    Enter
    Show

    Type "# 1.1. Компактний режим (-c/--compact)"
    Enter

    Type "metro route салтівська турбоатом -t 07:25 -s weekday -f full --compact"
    Sleep 0.5s
    Enter

    Sleep 1s

    Type "metro route салтівська турбоатом -t 07:25 -s weekday -f simple --compact"
    Sleep 0.5s
    Enter

    Sleep 2s

    Hide
    Type "clear"
    Enter
    Show

    Type "# 2. Розклад станції (schedule)"
    Enter

    Type "metro schedule київська -s weekday"
    Sleep 0.5s
    Enter

    Sleep 2s

    Type "metro schedule київська -s weekend"
    Sleep 0.5s
    Enter

    Sleep 4s
    
    Hide
    Type "clear"
    Enter
    Show

    Type "# 3. Список станцій (stations)"
    Enter

    Type "metro stations"
    Sleep 0.5s
    Enter

    Sleep 1s

    # Hide
    # Type "clear"
    # Enter
    # Show

    Type "# 3.1. Список станцій на лінії (-l/--line)"
    Enter

    Type "metro stations -l s"
    Sleep 0.5s
    Enter

    Sleep 2s

    Type "metro stations -l k"
    Sleep 0.5s
    Enter

    Sleep 8s
'

[working-directory: 'assets']
_demo-dark:
    #!/usr/bin/env vhs
    Output route_demo.gif
    Set Theme "GruvboxDarkHard"
    Set MarginFill "#0D1117"
    {{vhs-script}}

[working-directory: 'assets']
_demo-light:
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
