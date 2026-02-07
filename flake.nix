{
  description = "Kharkiv Metro Route Planner";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = inputs @ {
    nixpkgs,
    flake-utils,
    ...
  }:
    flake-utils.lib.eachDefaultSystem (system: let
      pkgs = nixpkgs.legacyPackages.${system};
      python = pkgs.python311;
      pyPkgs = python.pkgs;

      kharkiv-metro-core = pyPkgs.buildPythonPackage {
        pname = "kharkiv-metro-core";
        src = ./packages/kharkiv-metro-core;
        version = "0.1.0";
        format = "pyproject";
        nativeBuildInputs = [pyPkgs.hatchling];
        propagatedBuildInputs = with pyPkgs; [
          aiohttp
          beautifulsoup4
          requests
          toml
          tzdata
        ];
      };

      kharkiv-metro-cli = pyPkgs.buildPythonPackage {
        pname = "kharkiv-metro-cli";
        src = ./packages/kharkiv-metro-cli;
        version = "0.1.0";
        format = "pyproject";
        nativeBuildInputs = [pyPkgs.hatchling];
        propagatedBuildInputs = with pyPkgs; [
          click
          rich
          kharkiv-metro-core
        ];
        meta.mainProgram = "metro";
      };

      kharkiv-metro-bot = pyPkgs.buildPythonPackage {
        pname = "kharkiv-metro-bot";
        src = ./packages/kharkiv-metro-bot;
        version = "0.1.0";
        format = "pyproject";
        nativeBuildInputs = [pyPkgs.hatchling];
        propagatedBuildInputs = with pyPkgs; [
          aiogram
          python-dotenv
          kharkiv-metro-core
        ];
        meta.mainProgram = "metro-bot";
      };

      kharkiv-metro-mcp = pyPkgs.buildPythonPackage {
        pname = "kharkiv-metro-mcp";
        src = ./packages/kharkiv-metro-mcp;
        version = "0.1.0";
        format = "pyproject";
        nativeBuildInputs = [pyPkgs.hatchling];
        propagatedBuildInputs = with pyPkgs; [
          mcp
          kharkiv-metro-core
        ];
        meta.mainProgram = "metro-mcp";
      };
    in {
      packages = {
        default = kharkiv-metro-cli;
        core = kharkiv-metro-core;
        cli = kharkiv-metro-cli;
        bot = kharkiv-metro-bot;
        mcp = kharkiv-metro-mcp;
      };

      apps = {
        default = flake-utils.lib.mkApp {
          drv = kharkiv-metro-cli;
        };
        metro = flake-utils.lib.mkApp {
          drv = kharkiv-metro-cli;
        };
        metro-bot = flake-utils.lib.mkApp {
          drv = kharkiv-metro-bot;
        };
        metro-mcp = flake-utils.lib.mkApp {
          drv = kharkiv-metro-mcp;
        };
      };

      devShells.default = pkgs.mkShellNoCC {
        packages = with pkgs; [
          just
          uv
          ruff
          python
          # for demo in assets/
          bashInteractive # see https://github.com/charmbracelet/vhs/issues/458
          vhs
        ];
      };
    });
}
