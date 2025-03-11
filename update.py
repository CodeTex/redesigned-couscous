import argparse
import json
import os
import shutil
import sys
import tempfile
import zipfile

# Define constants for folder names
INSTALLED_DIR_NAME = "_installed_"
UNINSTALLED_DIR_NAME = "_uninstalled_"
DEPENDENCY_FILE = "dependencies.json"


def get_installed_updates(updates_dir):
    """Return a list of all zip files in the installed directory."""
    installed_dir = os.path.join(updates_dir, INSTALLED_DIR_NAME)

    if not os.path.exists(installed_dir):
        os.makedirs(installed_dir)
        print(f"Created directory: {installed_dir}")
        return []

    zip_files = [
        (f, os.path.join(installed_dir, f))
        for f in os.listdir(installed_dir)
        if f.endswith(".zip") and os.path.isfile(os.path.join(installed_dir, f))
    ]
    return zip_files


def get_available_updates(updates_dir):
    """Return a list of all zip files in the updates directory and uninstalled directory."""
    if not os.path.exists(updates_dir):
        print(f"Error: Updates directory '{updates_dir}' does not exist.")
        sys.exit(1)

    # Check for zip files in the root updates directory
    root_zips = [
        (f, os.path.join(updates_dir, f))
        for f in os.listdir(updates_dir)
        if f.endswith(".zip") and os.path.isfile(os.path.join(updates_dir, f))
    ]

    # Check for zip files in the _uninstalled_ directory
    uninstalled_dir = os.path.join(updates_dir, UNINSTALLED_DIR_NAME)
    if not os.path.exists(uninstalled_dir):
        os.makedirs(uninstalled_dir)

    uninstalled_zips = [
        (f, os.path.join(uninstalled_dir, f))
        for f in os.listdir(uninstalled_dir)
        if f.endswith(".zip") and os.path.isfile(os.path.join(uninstalled_dir, f))
    ]

    # Return a list of tuples: (display_name, full_path)
    return root_zips + uninstalled_zips


def load_dependencies(updates_dir):
    """Load dependency information from JSON file."""
    dependency_file = os.path.join(updates_dir, DEPENDENCY_FILE)
    if os.path.exists(dependency_file):
        try:
            with open(dependency_file, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"Warning: Could not parse {dependency_file}. Starting with empty dependencies.")
            return {"dependencies": {}, "dependents": {}}

    return {"dependencies": {}, "dependents": {}}


def save_dependencies(updates_dir, dependency_data):
    """Save dependency information to JSON file."""
    dependency_file = os.path.join(updates_dir, DEPENDENCY_FILE)
    with open(dependency_file, "w") as f:
        json.dump(dependency_data, f, indent=2)


def update_dependencies(updates_dir, update_name, dependencies):
    """Update dependency information for an update."""
    dependency_data = load_dependencies(updates_dir)

    # Update the dependencies for this update
    dependency_data["dependencies"][update_name] = dependencies

    # Update the reverse-lookup (dependents) information
    for dep in dependencies:
        if dep not in dependency_data["dependents"]:
            dependency_data["dependents"][dep] = []
        if update_name not in dependency_data["dependents"][dep]:
            dependency_data["dependents"][dep].append(update_name)

    save_dependencies(updates_dir, dependency_data)


def get_dependents(updates_dir, update_name):
    """Get all updates that depend on the given update."""
    dependency_data = load_dependencies(updates_dir)
    return dependency_data["dependents"].get(update_name, [])


def get_dependencies(updates_dir, update_name):
    """Get all dependencies for the given update."""
    dependency_data = load_dependencies(updates_dir)
    return dependency_data["dependencies"].get(update_name, [])


def check_unused_dependencies(updates_dir, removed_update):
    """Check for unused dependencies after removing an update."""
    dependency_data = load_dependencies(updates_dir)
    installed_updates = [name for name, _ in get_installed_updates(updates_dir)]

    # Get the dependencies of the removed update
    removed_deps = dependency_data["dependencies"].get(removed_update, [])
    unused_deps = []

    # For each dependency, check if it's still needed by any installed update
    for dep in removed_deps:
        # Skip if the dependency is not installed
        if dep not in installed_updates:
            continue

        # Check if any other installed update depends on this
        still_needed = False
        for dependent in dependency_data["dependents"].get(dep, []):
            if dependent != removed_update and dependent in installed_updates:
                still_needed = True
                break

        if not still_needed:
            unused_deps.append(dep)

    return unused_deps


def select_dependencies(updates_dir, update_name):
    """Allow user to select dependencies for an update from installed updates."""
    installed_updates = [name for name, _ in get_installed_updates(updates_dir)]

    if not installed_updates:
        print("No installed updates to select as dependencies.")
        return []

    print(f"\nSelect dependencies for {update_name}:")
    for i, update in enumerate(installed_updates, 1):
        print(f"{i}. {update}")

    print("\nEnter numbers for dependencies (e.g., '1,3,5' or '2-4'), or leave empty for none.")
    print("Enter 'cancel' to abort the installation.")

    selection = input("\nYour selection: ").strip()

    if selection.lower() == "cancel":
        return None

    if not selection:
        return []

    selected_indices = parse_selection(selection, len(installed_updates))
    return [installed_updates[i - 1] for i in selected_indices]


def display_update_folders(zip_files, mode):
    """Display numbered list of update folders for user selection."""
    if mode == "install":
        print("\nAvailable update folders to install:")
        action_text = "install"
        all_command = "install-all"
    else:  # mode == "remove"
        print("\nInstalled update folders to remove:")
        action_text = "remove"
        all_command = "remove-all"

    for i, (zip_name, _) in enumerate(zip_files, 1):
        print(f"{i}. {zip_name}")

    print(f"\nEnter numbers to select folders to {action_text} (e.g., '1,3,5' or '2-4' or '1,3-5').")
    print("Enter 'all' to select all folders.")
    print(
        f"Or type '{all_command}' to {action_text} all {'available' if mode == 'install' else 'installed'} updates at once."
    )
    print("Type 'graph' to display dependency graph.")


def parse_selection(selection_str, max_num):
    """Parse user selection string into a list of indices."""
    if selection_str.lower() == "all":
        return list(range(1, max_num + 1))

    selected = set()
    for part in selection_str.split(","):
        if "-" in part:
            try:
                start, end = map(int, part.split("-"))
                if 1 <= start <= end <= max_num:
                    selected.update(range(start, end + 1))
            except ValueError:
                print(f"Ignoring invalid range: {part}")
        else:
            try:
                num = int(part)
                if 1 <= num <= max_num:
                    selected.add(num)
            except ValueError:
                print(f"Ignoring invalid number: {part}")

    return sorted(list(selected))


def analyze_update_zip(update_zip_path, primary_folder):
    """
    Analyzes files in the zipped update folder and removes corresponding files from the primary folder.
    Returns lists of successfully removed files, not found files, and files that couldn't be removed.
    """
    if not os.path.exists(update_zip_path):
        print(f"Error: Update zip file '{update_zip_path}' does not exist.")
        return [], [], [(update_zip_path, "File not found")]

    if not os.path.exists(primary_folder):
        print(f"Error: Primary folder '{primary_folder}' does not exist.")
        return [], [], [(primary_folder, "Directory not found")]

    # Lists to track results
    removed_files = []
    not_found_files = []
    failed_to_remove = []

    try:
        # Open the zip file
        with zipfile.ZipFile(update_zip_path, "r") as zip_ref:
            # Get the list of files in the zip
            file_list = zip_ref.namelist()

            # Process each file in the zip
            for zip_path in file_list:
                # Skip directories
                if zip_path.endswith("/"):
                    continue

                # Construct the corresponding path in the primary folder
                primary_file_path = os.path.join(primary_folder, zip_path)

                # Check if the file exists in the primary folder
                if os.path.exists(primary_file_path):
                    try:
                        # Remove the file
                        os.remove(primary_file_path)
                        removed_files.append(primary_file_path)

                        # Check if the directory is now empty and remove it if it is
                        dir_path = os.path.dirname(primary_file_path)
                        while dir_path != primary_folder and os.path.exists(dir_path):
                            if not os.listdir(dir_path):
                                os.rmdir(dir_path)
                                dir_path = os.path.dirname(dir_path)
                            else:
                                break

                    except Exception as e:
                        failed_to_remove.append((primary_file_path, str(e)))
                else:
                    not_found_files.append(primary_file_path)

    except zipfile.BadZipFile:
        print(f"Error: '{update_zip_path}' is not a valid zip file.")
        failed_to_remove.append((update_zip_path, "Invalid zip file"))
    except Exception as e:
        print(f"Error processing '{update_zip_path}': {str(e)}")
        failed_to_remove.append((update_zip_path, str(e)))

    return removed_files, not_found_files, failed_to_remove


def apply_update_zip(update_zip_path, primary_folder):
    """
    Extracts files from the zipped update folder and copies them to the primary folder.
    Returns lists of successfully copied files, existing files that were overwritten, and failed files.
    """
    if not os.path.exists(update_zip_path):
        print(f"Error: Update zip file '{update_zip_path}' does not exist.")
        return [], [], [(update_zip_path, "File not found")]

    if not os.path.exists(primary_folder):
        print(f"Error: Primary folder '{primary_folder}' does not exist.")
        return [], [], [(primary_folder, "Directory not found")]

    # Lists to track results
    copied_files = []
    overwritten_files = []
    failed_files = []

    try:
        # Create a temporary directory for extraction
        with tempfile.TemporaryDirectory() as temp_dir:
            # Extract the zip file to the temporary directory
            with zipfile.ZipFile(update_zip_path, "r") as zip_ref:
                zip_ref.extractall(temp_dir)

            # Walk through all files in the extracted structure
            for root, _, files in os.walk(temp_dir):
                # Calculate the relative path
                rel_path = os.path.relpath(root, temp_dir)

                for file in files:
                    # Source file path in the temp directory
                    source_file_path = os.path.join(root, file)

                    # Target file path in the primary folder
                    if rel_path == ".":
                        target_file_path = os.path.join(primary_folder, file)
                    else:
                        target_file_path = os.path.join(primary_folder, rel_path, file)

                    # Create directories if they don't exist
                    os.makedirs(os.path.dirname(target_file_path), exist_ok=True)

                    try:
                        # Check if file already exists
                        if os.path.exists(target_file_path):
                            shutil.copy2(source_file_path, target_file_path)
                            overwritten_files.append(target_file_path)
                        else:
                            shutil.copy2(source_file_path, target_file_path)
                            copied_files.append(target_file_path)
                    except Exception as e:
                        failed_files.append((target_file_path, str(e)))

    except zipfile.BadZipFile:
        print(f"Error: '{update_zip_path}' is not a valid zip file.")
        failed_files.append((update_zip_path, "Invalid zip file"))
    except Exception as e:
        print(f"Error processing '{update_zip_path}': {str(e)}")
        failed_files.append((update_zip_path, str(e)))

    return copied_files, overwritten_files, failed_files


def remove_all_updates(primary_folder, updates_dir):
    """Remove all installed updates at once."""
    installed_dir = os.path.join(updates_dir, INSTALLED_DIR_NAME)
    uninstalled_dir = os.path.join(updates_dir, UNINSTALLED_DIR_NAME)

    zip_files = get_installed_updates(updates_dir)

    if not zip_files:
        print("No installed updates found.")
        return

    print(f"\nRemoving all {len(zip_files)} installed updates...")

    confirmation = input("Are you sure you want to remove ALL installed updates? (y/n): ").strip().lower()
    if confirmation != "y":
        print("Operation canceled.")
        return

    total_removed = 0
    total_not_found = 0
    total_failed = 0

    for zip_name, zip_path in zip_files:
        print(f"\nProcessing: {zip_name}")

        removed, not_found, failed = analyze_update_zip(zip_path, primary_folder)

        total_removed += len(removed)
        total_not_found += len(not_found)
        total_failed += len(failed)

        print(f"  Removed {len(removed)} files, Not found {len(not_found)}, Failed {len(failed)}")

        # Only move the zip file if at least one file was successfully removed
        if len(removed) > 0:
            try:
                shutil.move(zip_path, os.path.join(uninstalled_dir, zip_name))
                print(f"  Moved '{zip_name}' to {UNINSTALLED_DIR_NAME} folder.")
            except Exception as e:
                print(f"  Failed to move '{zip_name}': {str(e)}")
        else:
            print(f"  No files were removed for '{zip_name}', keeping it in {INSTALLED_DIR_NAME} folder.")

    print("\nAll updates removal complete!")
    print(f"Total summary: Removed {total_removed} files, Not found {total_not_found}, Failed {total_failed}")


def install_all_updates(primary_folder, updates_dir):
    """Install all available updates at once."""
    installed_dir = os.path.join(updates_dir, INSTALLED_DIR_NAME)

    zip_files = get_available_updates(updates_dir)

    if not zip_files:
        print("No updates found to install.")
        return

    print(f"\nInstalling all {len(zip_files)} available updates...")

    confirmation = input("Are you sure you want to install ALL available updates? (y/n): ").strip().lower()
    if confirmation != "y":
        print("Operation canceled.")
        return

    total_copied = 0
    total_overwritten = 0
    total_failed = 0

    for zip_name, source_path in zip_files:
        print(f"\nProcessing: {zip_name}")

        # Check for dependencies
        dependencies = select_dependencies(updates_dir, zip_name)
        if dependencies is None:  # User cancelled
            print(f"  Installation of '{zip_name}' cancelled.")
            continue

        # Update dependencies
        update_dependencies(updates_dir, zip_name, dependencies)
        print(f"  Registered dependencies: {', '.join(dependencies) if dependencies else 'None'}")

        copied, overwritten, failed = apply_update_zip(source_path, primary_folder)

        total_copied += len(copied)
        total_overwritten += len(overwritten)
        total_failed += len(failed)

        print(f"  Copied {len(copied)} new files, Overwritten {len(overwritten)}, Failed {len(failed)}")

        # Only move the zip file if at least one file was successfully copied or overwritten
        if len(copied) > 0 or len(overwritten) > 0:
            try:
                target_path = os.path.join(installed_dir, zip_name)
                # If the file already exists in the destination, add a suffix
                if os.path.exists(target_path):
                    base, ext = os.path.splitext(zip_name)
                    i = 1
                    while os.path.exists(os.path.join(installed_dir, f"{base}_{i}{ext}")):
                        i += 1
                    target_path = os.path.join(installed_dir, f"{base}_{i}{ext}")

                shutil.move(source_path, target_path)
                print(f"  Moved '{zip_name}' to {INSTALLED_DIR_NAME} folder.")
            except Exception as e:
                print(f"  Failed to move '{zip_name}': {str(e)}")
        else:
            print(f"  No files were installed for '{zip_name}', not moving it to {INSTALLED_DIR_NAME} folder.")

    print("\nAll updates installation complete!")
    print(f"Total summary: New files {total_copied}, Overwritten {total_overwritten}, Failed {total_failed}")


def remove_selected_updates(primary_folder, updates_dir, selected_indices, zip_files):
    """Remove selected updates from the primary folder."""
    uninstalled_dir = os.path.join(updates_dir, UNINSTALLED_DIR_NAME)

    # Process each selected update folder
    for idx in selected_indices:
        zip_name, zip_path = zip_files[idx - 1]

        # Check if any installed updates depend on this one
        dependents = get_dependents(updates_dir, zip_name)
        installed_updates = [name for name, _ in get_installed_updates(updates_dir)]
        actual_dependents = [dep for dep in dependents if dep in installed_updates]

        if actual_dependents:
            print(f"\nWarning: The following installed updates depend on '{zip_name}':")
            for dep in actual_dependents:
                print(f"  - {dep}")
            confirmation = input("Do you still want to remove this update? (y/n): ").strip().lower()
            if confirmation != "y":
                print(f"Skipping removal of '{zip_name}'.")
                continue

        print(f"\nProcessing update: {zip_name}")

        removed, not_found, failed = analyze_update_zip(zip_path, primary_folder)

        print(f"\nSummary for {zip_name}:")
        print(f"Successfully removed {len(removed)} files")
        print(f"Files not found: {len(not_found)}")
        print(f"Failed to remove: {len(failed)}")

        # Only move the zip file if at least one file was successfully removed
        if len(removed) > 0:
            try:
                shutil.move(zip_path, os.path.join(uninstalled_dir, zip_name))
                print(f"Moved '{zip_name}' from {INSTALLED_DIR_NAME} to {UNINSTALLED_DIR_NAME} folder.")

                # Check for unused dependencies
                unused_deps = check_unused_dependencies(updates_dir, zip_name)
                if unused_deps:
                    print(f"\nThe following installed updates were only dependencies for '{zip_name}':")
                    for dep in unused_deps:
                        print(f"  - {dep}")
                    removal = input("Do you want to remove these unused dependencies? (y/n): ").strip().lower()
                    if removal == "y":
                        # Get paths for these update folders
                        installed_dir = os.path.join(updates_dir, INSTALLED_DIR_NAME)
                        for dep in unused_deps:
                            dep_path = os.path.join(installed_dir, dep)
                            if os.path.exists(dep_path):
                                print(f"\nRemoving unused dependency: {dep}")
                                dep_removed, dep_not_found, dep_failed = analyze_update_zip(dep_path, primary_folder)
                                print(
                                    f"  Removed {len(dep_removed)} files, Not found {len(dep_not_found)}, Failed {len(dep_failed)}"
                                )
                                if len(dep_removed) > 0:
                                    shutil.move(dep_path, os.path.join(uninstalled_dir, dep))
                                    print(f"  Moved '{dep}' to {UNINSTALLED_DIR_NAME} folder.")

            except Exception as e:
                print(f"Failed to move '{zip_name}': {str(e)}")
        else:
            print(f"No files were removed for '{zip_name}', keeping it in {INSTALLED_DIR_NAME} folder.")

        # Option to display detailed results
        if removed or not_found or failed:
            show_details = input("Show detailed results? (y/n): ").strip().lower()
            if show_details == "y":
                if removed:
                    print("\nRemoved files:")
                    for f in removed[:10]:  # Show first 10 files
                        print(f"  - {f}")
                    if len(removed) > 10:
                        print(f"  ... and {len(removed) - 10} more files")

                if not_found:
                    print("\nFiles not found:")
                    for f in not_found[:10]:  # Show first 10 files
                        print(f"  - {f}")
                    if len(not_found) > 10:
                        print(f"  ... and {len(not_found) - 10} more files")

                if failed:
                    print("\nFailed to remove:")
                    for f, error in failed:
                        print(f"  - {f} (Error: {error})")


def install_selected_updates(primary_folder, updates_dir, selected_indices, zip_files):
    """Install selected updates to the primary folder."""
    installed_dir = os.path.join(updates_dir, INSTALLED_DIR_NAME)

    # Process each selected update folder
    for idx in selected_indices:
        zip_name, source_path = zip_files[idx - 1]

        print(f"\nProcessing update: {zip_name}")

        # Check for dependencies
        dependencies = select_dependencies(updates_dir, zip_name)
        if dependencies is None:  # User cancelled
            print(f"Installation of '{zip_name}' cancelled.")
            continue

        # Update dependencies
        update_dependencies(updates_dir, zip_name, dependencies)
        print(f"Registered dependencies: {', '.join(dependencies) if dependencies else 'None'}")

        copied, overwritten, failed = apply_update_zip(source_path, primary_folder)

        print(f"\nSummary for {zip_name}:")
        print(f"Successfully copied {len(copied)} new files")
        print(f"Overwritten existing files: {len(overwritten)}")
        print(f"Failed to copy: {len(failed)}")

        # Only move the zip file if at least one file was successfully copied or overwritten
        if len(copied) > 0 or len(overwritten) > 0:
            try:
                target_path = os.path.join(installed_dir, zip_name)
                # If the file already exists in the destination, add a suffix
                if os.path.exists(target_path):
                    base, ext = os.path.splitext(zip_name)
                    i = 1
                    while os.path.exists(os.path.join(installed_dir, f"{base}_{i}{ext}")):
                        i += 1
                    target_path = os.path.join(installed_dir, f"{base}_{i}{ext}")

                shutil.move(source_path, target_path)
                print(f"Moved '{zip_name}' to {INSTALLED_DIR_NAME} folder.")
            except Exception as e:
                print(f"Failed to move '{zip_name}': {str(e)}")
        else:
            print(f"No files were installed for '{zip_name}', not moving it to {INSTALLED_DIR_NAME} folder.")

        # Option to display detailed results
        if copied or overwritten or failed:
            show_details = input("Show detailed results? (y/n): ").strip().lower()
            if show_details == "y":
                if copied:
                    print("\nNewly copied files:")
                    for f in copied[:10]:  # Show first 10 files
                        print(f"  - {f}")
                    if len(copied) > 10:
                        print(f"  ... and {len(copied) - 10} more files")

                if overwritten:
                    print("\nOverwritten files:")
                    for f in overwritten[:10]:  # Show first 10 files
                        print(f"  - {f}")
                    if len(overwritten) > 10:
                        print(f"  ... and {len(overwritten) - 10} more files")

                if failed:
                    print("\nFailed to copy:")
                    for f, error in failed:
                        print(f"  - {f} (Error: {error})")


def display_dependency_graph(updates_dir):
    """Display ASCII dependency graph."""
    dependency_data = load_dependencies(updates_dir)
    installed_updates = [name for name, _ in get_installed_updates(updates_dir)]

    if not dependency_data["dependencies"]:
        print("\nNo dependency information available.")
        return

    print("\nDependency Graph (→ means 'depends on'):")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    # Create a sorted list of all updates with dependencies
    all_updates = sorted(dependency_data["dependencies"].keys())

    # First, print installed updates and their dependencies
    for update in all_updates:
        dependencies = dependency_data["dependencies"][update]
        if update in installed_updates:
            print(f"[INSTALLED] {update}")
            if dependencies:
                print_dependencies(dependencies, dependency_data, installed_updates, "  ", [update])
            else:
                print("  └── (no dependencies)")
            print()

    # Then, print uninstalled updates with dependencies
    uninstalled_with_deps = [
        u for u in all_updates if u not in installed_updates and dependency_data["dependencies"].get(u)
    ]
    if uninstalled_with_deps:
        print("\nUninstalled Updates with Dependencies:")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        for update in uninstalled_with_deps:
            dependencies = dependency_data["dependencies"][update]
            print(f"[UNINSTALLED] {update}")
            if dependencies:
                print_dependencies(dependencies, dependency_data, installed_updates, "  ", [update])
            print()

    input("\nPress Enter to continue...")


def print_dependencies(dependencies, dependency_data, installed_updates, indent, visited):
    """Recursively print dependencies with proper indentation."""
    for i, dep in enumerate(dependencies):
        is_last = i == len(dependencies) - 1
        prefix = "└── " if is_last else "├── "

        # Check for installed status
        status = "[INSTALLED]" if dep in installed_updates else "[MISSING]"

        # Check for circular dependencies
        if dep in visited:
            print(f"{indent}{prefix}{dep} {status} (circular dependency)")
            continue

        print(f"{indent}{prefix}{dep} {status}")

        # Recursively print dependencies of this dependency
        sub_deps = dependency_data["dependencies"].get(dep, [])
        if sub_deps:
            next_indent = indent + ("    " if is_last else "│   ")
            print_dependencies(sub_deps, dependency_data, installed_updates, next_indent, visited + [dep])


def main():
    parser = argparse.ArgumentParser(description="Manage updates for a primary folder.")
    parser.add_argument(
        "mode",
        choices=["install", "remove", "graph"],
        help="Operation mode: install or remove updates, or display dependency graph",
    )
    parser.add_argument("primary_folder", nargs="?", help="Path to the primary folder")
    parser.add_argument("updates_dir", nargs="?", help="Path to the updates directory")

    args = parser.parse_args()

    # Special case for 'graph' mode
    if args.mode == "graph":
        if not args.updates_dir:
            parser.error("the following arguments are required: updates_dir")
        display_dependency_graph(args.updates_dir)
        sys.exit(0)

    # For install and remove modes, both primary_folder and updates_dir are required
    if not args.primary_folder or not args.updates_dir:
        parser.error("the following arguments are required: primary_folder updates_dir")

    primary_folder = args.primary_folder
    updates_dir = args.updates_dir
    mode = args.mode

    # Check if primary folder exists
    if not os.path.exists(primary_folder):
        print(f"Error: Primary folder '{primary_folder}' does not exist.")
        sys.exit(1)

    # Ensure the required directories exist
    installed_dir = os.path.join(updates_dir, INSTALLED_DIR_NAME)
    uninstalled_dir = os.path.join(updates_dir, UNINSTALLED_DIR_NAME)

    if not os.path.exists(installed_dir):
        os.makedirs(installed_dir)

    if not os.path.exists(uninstalled_dir):
        os.makedirs(uninstalled_dir)

    # Get list of update zip files based on the mode
    if mode == "install":
        zip_files = get_available_updates(updates_dir)
        if not zip_files:
            print(f"No zip files found in '{updates_dir}' or its '{UNINSTALLED_DIR_NAME}' subfolder.")
            sys.exit(0)
    else:  # mode == "remove"
        zip_files = get_installed_updates(updates_dir)
        if not zip_files:
            print(f"No zip files found in '{os.path.join(updates_dir, INSTALLED_DIR_NAME)}'.")
            sys.exit(0)

    # Display update folders and get user selection
    display_update_folders(zip_files, mode)
    selection = input("\nYour selection: ").strip()

    # Check for special commands
    if selection.lower() == "graph":
        display_dependency_graph(updates_dir)
        # After displaying graph, re-prompt for selection
        display_update_folders(zip_files, mode)
        selection = input("\nYour selection: ").strip()

    if mode == "install" and selection.lower() == "install-all":
        install_all_updates(primary_folder, updates_dir)
        sys.exit(0)
    elif mode == "remove" and selection.lower() == "remove-all":
        remove_all_updates(primary_folder, updates_dir)
        sys.exit(0)

    selected_indices = parse_selection(selection, len(zip_files))

    if not selected_indices:
        print("No valid selections made. Exiting.")
        sys.exit(0)

    # Process selected updates based on the mode
    if mode == "install":
        install_selected_updates(primary_folder, updates_dir, selected_indices, zip_files)
    else:  # mode == "remove"
        remove_selected_updates(primary_folder, updates_dir, selected_indices, zip_files)

    print(f"\nAll selected updates {mode}ation processed.")


if __name__ == "__main__":
    main()
