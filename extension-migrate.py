#!/usr/bin/env python
import argparse
import fnmatch
import os
import re
import subprocess
import sys

# Define command-line arguments
parser = argparse.ArgumentParser()
parser.add_argument("-b", "--source_branch", help="Source Branch.", required=True)
parser.add_argument(
    "-f",
    "--file_filter",
    help="Name to use to filter files, also the name of the extension.",
    required=True,
)
parser.add_argument("-n", "--dry_run", help="Dry run.", action="store_true")
parser.add_argument("-e", "--extra_files", nargs="+", help="Extra files.", required=False)
parser.add_argument("-d", "--extension_dir", help="Extension directory.", required=True)
parser.add_argument("-z", "--debug", help="Display extra debugging info", action="store_true")
args = parser.parse_args()


def run_command(cmd, fatal=True):
    cmd_list = cmd.split(" ")
    ret = subprocess.run(cmd_list)
    if ret.returncode != 0 and fatal:
        print(f"Failure: {ret.stderr}")
        sys.exit(ret.returncode)
    return


def _exists_and_not_ignored(path, patterns_to_ignore):
    if os.path.exists(path) and not any(fnmatch.fnmatch(path, pattern) for pattern in patterns_to_ignore):
        return True
    return False


# Clone salt repository
print("Cloning Salt")
previous_cwd = os.getcwd()
run_command("git clone git@github.com:saltstack/salt.git --single-branch", fatal=False)

os.chdir("salt")

# Create the filter-source branch
print("Checking out filter-source branch")
run_command("git checkout -b filter-source", fatal=False)

print("Calculating files")
files_to_migrate = []
patterns_to_ignore = [
    "./.github/*",
    "./doc/ref/*/all*",
    "./salt/__init__.py",
    "./salt/cache/__init__.py",
    "./salt/cloud/__init__.py",
    "./salt/engines/__init__.py",
    "./salt/output/__init__.py",
    "./salt/pillar/__init__.py",
    "./tests/unit/conftest.py",
]
for root, dirs, files in os.walk("."):
    path = root.split(os.sep)
    full_path = os.path.join(*path)
    for _file in fnmatch.filter(files, f"*{args.file_filter}*"):
        dirname_full_path_file = os.path.dirname(f"{full_path}/{_file}")
        if any(fnmatch.fnmatch(f"{full_path}/{_file}", pattern) for pattern in patterns_to_ignore):
            continue
        files_to_migrate.append(f"{full_path}/{_file}")
        if _exists_and_not_ignored(f"{dirname_full_path_file}/conftest.py", patterns_to_ignore):
            files_to_migrate.append(f"{dirname_full_path_file}/conftest.py")
        if _exists_and_not_ignored(f"{dirname_full_path_file}/__init__.py", patterns_to_ignore):
            files_to_migrate.append(f"{dirname_full_path_file}/__init__.py")
        parent_dirname_full_path_file = os.path.dirname(f"{dirname_full_path_file}")
        if _exists_and_not_ignored(f"{parent_dirname_full_path_file}/__init__.py", patterns_to_ignore):
            files_to_migrate.append(f"{parent_dirname_full_path_file}/__init__.py")

    for _dir in fnmatch.filter(dirs, f"*{args.file_filter}*"):
        if any(fnmatch.fnmatch(f"{full_path}/{_dir}", pattern) for pattern in patterns_to_ignore):
            continue
        files_to_migrate.append(f"{full_path}/{_dir}")

    for _file in fnmatch.filter(files, "*conftest.py*"):
        file_full_path = f"{full_path}/{_file}"
        if file_full_path in (
            "./tests/pytests/unit/conftest.py",
            "./tests/pytests/integration/conftest.py",
            "./tests/pytests/functional/conftest.py",
        ):
            files_to_migrate.append(f"{full_path}/{_file}")

# Add any extra files
if args.extra_files:
    for extra_file in args.extra_files:
        if os.path.exists(extra_file):
            files_to_migrate.append(extra_file)
        else:
            print(f"{extra_file} does not exist, skipping")

old_files = []
new_files = []

for file in files_to_migrate:
    new_file = re.sub(r"\.\/", "", file)
    old_files.append(new_file)

    # swap doc for docs
    new_file = re.sub("^doc/", "docs/", new_file)

    # swap salt path for extension path
    new_file = re.sub("^salt", f"src/saltext/{args.file_filter}", new_file)

    new_files.append(new_file)

print("Filtering files")
cmd = "git filter-repo"
for count in range(len(old_files)):
    cmd += f" --path {old_files[count]}"
cmd += " --refs refs/heads/filter-source --force"

if args.debug:
    print(cmd)

if args.dry_run:
    print("Would have run git filter-repo to filter files")
else:
    run_command(cmd)

print("Renaming Paths")
cmd = "git filter-repo"
for count in range(len(old_files)):
    cmd += f" --path-rename {old_files[count]}:{new_files[count]}"
cmd += " --force"

if args.debug:
    print(cmd)

if args.dry_run:
    print("Would have run git filter-repo to rename paths")
    print("Would have checked out filter-target branch")
    print("would have added the repo-source remote")
    print("Would have fetched repo-source remote")
    print("Would have created the branch-source branch")
    print("Would have merged branch-source into extension")
else:
    run_command(cmd)

    os.chdir(previous_cwd)

    # Change into the extension directory
    os.chdir(args.extension_dir)

    # Create the filter-target branch
    print("Checking out filter-target branch")
    run_command("git checkout -b filter-target")

    print("Adding repo-source remote")
    run_command("git remote add repo-source ../salt", fatal=False)

    print("Fetch repo-source remote")
    run_command("git fetch repo-source")

    print("Creating the branch-source branch")
    run_command("git branch branch-source remotes/repo-source/filter-source")

    print("Merge branch-source into extension")
    run_command("git merge branch-source --allow-unrelated-histories")

print("Success!")
