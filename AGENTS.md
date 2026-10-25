# GitBasher contributor guidance

- Use SemVer. While pre-1.0, fixes and UI polish increment PATCH; features and substantial changes increment MINOR. Choose the 1.0 milestone explicitly with the user.
- Include a version bump when shipping a new functional revision. Do not automatically bump for every bookkeeping commit.
- Use `npm version patch --no-git-tag-version` or `npm version minor --no-git-tag-version`. Commit package.json, package-lock.json, and gitbasher/_version.py together. Do not hand-edit the generated Python version.
- Run `npm test` for relevant changes. Windows integration tests require Windows; report skips accurately.
- The settings JSON `version` field is a storage schema version, separate from the application version.
- copy.sh and copy.bat are local deployment helpers and must remain untracked.
