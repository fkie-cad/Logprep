{
  description = "logprep allows to collect, process and forward log messages from various data sources";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";

    pyproject-nix = {
      url = "github:pyproject-nix/pyproject.nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    uv2nix = {
      url = "github:pyproject-nix/uv2nix";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    pyproject-build-systems = {
      url = "github:pyproject-nix/build-system-pkgs";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.uv2nix.follows = "uv2nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs =
    {
      self,
      nixpkgs,
      pyproject-nix,
      uv2nix,
      pyproject-build-systems,
      ...
    }:
    let
      inherit (nixpkgs) lib;
      forAllSystems = lib.genAttrs lib.systems.flakeExposed;

      workspace = uv2nix.lib.workspace.loadWorkspace { workspaceRoot = ./.; };

      overlay = workspace.mkPyprojectOverlay {
        sourcePreference = "wheel";
      };

      editableOverlay = workspace.mkEditablePyprojectOverlay {
        root = "$REPO_ROOT";
      };

      overlayWithVersion =
        final: prev:
        let
          version = if self ? rev then builtins.substring 0 7 self.rev else "0.0.0";
        in
        {
          logprep = prev.logprep.overrideAttrs (old: {
            env = (old.env or { }) // {
              SETUPTOOLS_SCM_PRETEND_VERSION = version;
            };
          });
        };

      pythonSets = forAllSystems (
        system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
          pythons = pyproject-nix.lib.util.filterPythonInterpreters {
            inherit (workspace) requires-python;
            inherit (pkgs) pythonInterpreters;
          };
          mkSet =
            python:
            (pkgs.callPackage pyproject-nix.build.packages {
              inherit python;
            }).overrideScope
              (
                lib.composeManyExtensions [
                  pyproject-build-systems.overlays.wheel
                  overlay
                  overlayWithVersion
                ]
              );

        in
        builtins.listToAttrs (
          map (python: {
            name = "python${lib.replaceStrings [ "." ] [ "" ] python.pythonVersion}";
            value = mkSet python;
          }) pythons
        )
      );
    in
    {
      devShells = forAllSystems (
        system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
          sets = pythonSets.${system};

          mkShellFor =
            pyVer: pythonSet:
            let
              pythonSetEditable = pythonSet.overrideScope editableOverlay;
              virtualenv = pythonSetEditable.mkVirtualEnv "logprep-dev-${pyVer}" workspace.deps.all;
            in
            pkgs.mkShell {
              packages = [
                virtualenv
                pkgs.uv
                pkgs.kubernetes-helm
                pkgs.basedpyright
              ];

              env = {
                UV_NO_SYNC = "1";
                UV_PYTHON = pythonSet.python.interpreter;
                UV_PYTHON_DOWNLOADS = "never";
              };

              shellHook = ''
                unset PYTHONPATH
                export REPO_ROOT=$(git rev-parse --show-toplevel)
              '';
            };

          shells = builtins.mapAttrs mkShellFor sets;
        in
        shells
        // {
          default = lib.head (lib.attrValues shells);
        }
      );

      packages = forAllSystems (
        system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
          sets = pythonSets.${system};

          mkEnv = pyVer: pythonSet: pythonSet.mkVirtualEnv "logprep-${pyVer}" workspace.deps.default;

          envs = builtins.mapAttrs mkEnv sets;

          dockerImages = builtins.mapAttrs (
            pyVer: env:
            pkgs.dockerTools.buildLayeredImage {
              name = "logprep";
              tag = pyVer;

              created = "now";
              contents = [ env ];

              config = {
                Entrypoint = [ "logprep" ];
              };
            }
          ) envs;

        in
        envs
        // {
          default = lib.head (lib.attrValues envs);

          docker = dockerImages;
        }
      );
    };
}
