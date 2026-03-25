# MS Preprocessing Toolkit

This package contains a ready-to-run desktop build of MS Preprocessing Toolkit.

## Package Contents

- Windows package: a versioned `.exe`
- macOS package: a versioned `.app`
- `README.md`: quick-start instructions for end users
- `LICENSE`: license notice

## Before You Start

- Extract the zip file to a normal folder before running the application.
- Keep the packaged files in the same extracted folder.
- This desktop build does not require a separate Python installation.

## Windows

1. Extract the zip file.
2. Open the extracted folder.
3. Double-click the packaged `.exe` to start the GUI.

If Windows SmartScreen appears, choose `More info` and then `Run anyway` after confirming the publisher and file source are expected.

## macOS

1. Extract the zip file.
2. Open the extracted folder.
3. Launch the packaged `.app`.

Because this build is not code-signed, macOS may block the first launch.

- First try: right-click the app and choose `Open`.
- If macOS still blocks it: go to `System Settings > Privacy & Security`, then allow the app and try again.

## Output Files

- The application does not create the `OUTPUT` folder at startup.
- The `OUTPUT` folder is created only when you export results or explicitly use `Open Output Folder`.
- Final exported user deliverables are written into `OUTPUT`.

## Basic Workflow

1. Launch the application.
2. Load an input workbook or table file.
3. Run the required preprocessing steps.
4. Export the final `.xlsx` result when processing is complete.

## Troubleshooting

- If the app cannot open your file, verify the file format is supported and not already locked by another program.
- If macOS blocks the app, use the `Open` action from the context menu once before trying again normally.
- If you need help, check the GitHub repository issues page for the matching release version.
