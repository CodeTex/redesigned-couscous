# Custom Cyberpunk 2077 Mod Script

Since keeping track of mod dependencies and which ones are installed I've created this script which does:
- Mod installation:
  - looks into _uninstalled_ and prompts user which zipped folder to install (only works with *.zip*)
  - prompts user with a list of already installed mods to assign which are requirements (expects user to install required mods first, if not already installed)
  - tracks dependency chart in *dependencies.json*
  - extracts all mod files and inserts them into given game files location (folder structure must match)
  - moves mod into _installed_ folder 
- Mod removal:
  - prompts user with possible mods to uninstall
  - checks if any installed mod depends on said mod
  - removes all files from given game files location
  - if one of its required mods is not used by any other, also uninstall it
- Dependency Graph Visualization

## Commands

> Optimal target folder structure:
>  ```sh
>  - _installed_
>  - _uninstalled_
>  - dependency.json
>  ```

Install mod:
```sh
python update.py install <path/to/gamefiles> <path/to/target/folder>
```

Uninstall mod:
```sh
python update.py remove <path/to/gamefiles> <path/to/target/folder>
```

Show dependency graph:
```sh
python update.py graph <path/to/gamefiles> <path/to/target/folder>
```

## Dependency Graph

Is stored via a key value object of dependencies and dependants, visualization looks like this:

```sh
Dependency Graph (→ means 'depends on'):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[INSTALLED] Apartment Cats - The Glen-6276-2-1-1-1740786838.zip
  ├── ArchiveXL-4198-1-21-1-1737797101.zip [INSTALLED]
  │   └── RED4ext-2380-1-27-0-1737651915.zip [INSTALLED]
  ├── RED4ext-2380-1-27-0-1737651915.zip [INSTALLED]
  └── TweakXL-4197-1-10-8-1738500388.zip [INSTALLED]
      └── RED4ext-2380-1-27-0-1737651915.zip [INSTALLED]

[INSTALLED] ArchiveXL-4198-1-21-1-1737797101.zip
  └── RED4ext-2380-1-27-0-1737651915.zip [INSTALLED]

[INSTALLED] BrowserExtensionFramework-10038-0-9-5-1701186644.zip
  ├── Codeware-7780-1-15-0-1737651995.zip [INSTALLED]
  │   └── RED4ext-2380-1-27-0-1737651915.zip [INSTALLED]
  ├── RED4ext-2380-1-27-0-1737651915.zip [INSTALLED]
  └── redscript-1511-0-5-28-1739731226.zip [INSTALLED]

[INSTALLED] CET 1.35.0 - Patch 2.21-107-1-35-0-1737654030.zip
  └── (no dependencies)
...
```
