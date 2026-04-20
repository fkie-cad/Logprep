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
                ]
              );

        in
        builtins.listToAttrs (
          map (python: {
            name = python.pythonVersion;
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
                pkgs.pandoc
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

          shells =
            let
              mk = pyVer: pythonSet: {
                name = "python${lib.replaceStrings [ "." ] [ "" ] pyVer}";
                value = mkShellFor pyVer pythonSet;
              };
            in
            builtins.listToAttrs (lib.mapAttrsToList mk sets);
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

          mkDist =
            pyVer: pythonSet:
            let
              base = pythonSet.logprep;

              wheel = base.override {
                pyprojectHook = pythonSet.pyprojectDistHook;
              };

              sdist = wheel.overrideAttrs (old: {
                env.uvBuildType = "sdist";
              });
            in
            pythonSet.pkgs.runCommand "logprep-dist-${pyVer}" { } ''
              mkdir -p $out/dist/

              cp ${wheel}/*.whl $out/dist/ 
              cp ${sdist}/*.tar.gz $out/dist/
            '';

          envs = builtins.mapAttrs mkEnv sets;

          dockerImages =
            let
              mk = pyVer: env: {
                name = "python${lib.replaceStrings [ "." ] [ "" ] pyVer}";
                value = pkgs.dockerTools.buildLayeredImage {
                  name = "logprep";
                  tag = "py${pyVer}";

                  extraCommands = ''
                    mkdir -p etc
                    cat > etc/passwd <<EOF
                    logprep:x:1000:1000::/home/logprep:/bin/sh
                    EOF

                    cat > etc/group <<EOF
                    logprep:x:1000:
                    EOF

                    mkdir -p home/logprep
                  '';

                  created = "now";
                  contents = [ env ];

                  config = {
                    User = "logprep";
                    WorkingDir = "/home/logprep";
                    Entrypoint = [ "logprep" ];
                  };
                };
              };

            in
            builtins.listToAttrs (lib.mapAttrsToList mk envs);

          packageEnvs =
            let
              mk = pyVer: env: {
                name = "python${lib.replaceStrings [ "." ] [ "" ] pyVer}";
                value = env;
              };
            in
            builtins.listToAttrs (lib.mapAttrsToList mk envs);

          distPackages =
            let
              mk = pyVer: pythonSet: {
                name = "python${lib.replaceStrings [ "." ] [ "" ] pyVer}";
                value = mkDist pyVer pythonSet;
              };
            in
            builtins.listToAttrs (lib.mapAttrsToList mk sets);
        in
        packageEnvs
        // {
          default = lib.head (lib.attrValues envs);

          docker = dockerImages;

          dist = distPackages;
        }
      );
    };
}
