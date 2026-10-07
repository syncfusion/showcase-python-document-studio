# showcase-python-document-studio
Upload a Word, Excel, PowerPoint, or PDF document and classify it, convert it to PDF, or apply a watermark from a Python web application backed by a .NET Syncfusion Document Processing worker.

## Document Studio — Python + .NET web POC

Upload one document, select an operation, then download the result.

**Architecture:** browser → FastAPI → async .NET subprocess → Syncfusion libraries.
JSON travels over standard input; documents stay in a temporary server folder.
No Docker, database, job queue, or login system. The browser needs no Python, .NET or Microsoft Office installation.

## Quick start (macOS / Linux)

Prerequisites: **Python 3.10+** and the **.NET 10 SDK** (or a newer SDK with the .NET 10
runtime installed).

From this project folder:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
dotnet publish DocumentBridge/DocumentBridge.csproj -c Release -r osx-arm64 --self-contained false -o artifacts
python run.py
```

Open <http://127.0.0.1:8000>. The running server must stay open.
Use `osx-x64` for Intel Mac or `linux-x64` for a Linux x64 server instead of `osx-arm64`.
On Debian/Ubuntu, install rendering dependencies before running:

```sh
sudo apt-get install -y libfontconfig1 libfreetype6 fontconfig fonts-liberation
```

Install the fonts used in your documents for accurate PDF rendering. Rebuild the
worker on the target platform; do not copy the Mac artifacts to Linux or Windows.

## Run on a Windows machine

Use **64-bit Windows 10/11 or Windows Server**, with PowerShell. These steps run
on your Windows machine; the Azure section below deploys to a Linux host.

### 1. Install the prerequisites

- Install [Python for Windows](https://www.python.org/downloads/windows/), version
  **3.12 or newer**, including the Python launcher (`py`).
- Install the **Windows x64 .NET 10 SDK** from the [.NET 10 downloads page](https://dotnet.microsoft.com/en-us/download/dotnet/10.0).
  Choose **SDK**, not only Runtime, because the worker must be built.
- Close and reopen PowerShell after installation, then check:

```powershell
py -3 --version
dotnet --list-sdks
dotnet --list-runtimes
```

Confirm Python is 3.12+ and the runtime list contains `Microsoft.NETCore.App 10.0.x`.
Microsoft Office and Visual Studio are not required. Install any fonts your test
documents use if they are not already available on the machine.

### 2. Extract the project and open its folder

Extract `document-web-poc.zip`, for example under `C:\POC`, then open the folder
that directly contains `app.py`, `requirements.txt`, and `DocumentBridge`:

```powershell
Set-Location "C:\POC\document-web-poc"
Get-ChildItem
```

Change the example path if you extracted it somewhere else. Do not run from inside
the ZIP viewer, or from the parent folder.

### 3. Create the Python environment and install dependencies

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Wait for the installation to finish successfully. The commands use the environment's
Python directly, so you do **not** need to activate it or change PowerShell's
execution policy. An internet connection is needed for Python and NuGet downloads.

### 4. Build the Windows .NET worker

```powershell
dotnet publish .\DocumentBridge\DocumentBridge.csproj -c Release -r win-x64 --self-contained false -o .\artifacts
Test-Path .\artifacts\DocumentBridge.dll
```

The build must succeed and `Test-Path` must return `True`. Keep the entire
`artifacts` folder, including its native libraries and JSON files. Publish again
if you change the C# source. The `win-x64` target assumes x64 Windows.

### 5. Optionally configure a Syncfusion license

For evaluation, skip this step. To use a valid .NET license, set it in the same
PowerShell window before starting the app:

```powershell
$env:SYNCFUSION_LICENSE_KEY = "your-valid-license-key"
```

The page registers this same key with Essential JS 2. See **License** below.
This setting applies to this PowerShell session and the processes it launches.
Do not put your actual key into a source file or shared ZIP.

### 6. Start and verify the app

```powershell
.\.venv\Scripts\python.exe run.py
```

Keep this window open. In a browser, go to **http://127.0.0.1:8000**.
Upload a small DOCX, choose **Classify Word document**, select **Process document**,
then download the result. Next try a PDF conversion. Stop the app with **Ctrl+C**.

To start it again later, reopen PowerShell in the project folder and run the same
command; dependency installation and publishing are not needed on every launch.

### 7. Optional: share with another machine on the same network

```powershell
.\.venv\Scripts\python.exe run.py --host 0.0.0.0 --port 8000
```

Run `ipconfig` in another PowerShell window and find the active adapter's IPv4
address. Share **http://YOUR-WINDOWS-IP:8000**. The Windows firewall must allow
inbound TCP 8000 on the relevant trusted network profile. `127.0.0.1` works only
on the host itself; `0.0.0.0` is a bind address, not a browser address.

The launcher supports asynchronous subprocesses on Windows. Each accepted request
starts its own .NET process. This process keeps at most `MAX_CONCURRENT_JOBS` of
those jobs in flight (default 2) and allows `RATE_LIMIT_REQUESTS` posts per caller
per `RATE_LIMIT_WINDOW_SECONDS` (default 10 per 60 seconds).

## Host on Azure App Service — deploy from Windows, without Docker

**Choose a Linux App Service with the Python runtime.** Azure does not support
Python on the built-in Windows App Service stack. Developing and publishing from
a Windows PC is fine. This route uses Azure's managed Python hosting environment;
you do not build or manage a Docker image. [Microsoft's Python hosting guidance](https://learn.microsoft.com/en-us/azure/app-service/containers/how-to-configure-python)

The existing adapter calls `dotnet artifacts/DocumentBridge.dll`. Selecting Python
in Azure does not provision a .NET 10 runtime for this application. The included
`startup-azure.sh` supplies that runtime and Linux rendering dependencies, then
starts the Python server. No changes to `app.py` or `document_sdk.py` are needed.


### 1. Prepare Azure access

On your Windows PC, install the [Azure CLI](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli-windows).
Open a new PowerShell window in the project folder. Use an Azure subscription
where you can create a resource group and an App Service plan:

```powershell
az version
az login
az account list --output table
az account set --subscription "YOUR-SUBSCRIPTION-ID"
```

Replace `YOUR-SUBSCRIPTION-ID`. Run the remaining blocks in this same PowerShell
window so the variables remain available. After every Azure command, check that it
succeeds before continuing.

### 2. Select names and create the Python/Linux web app

Replace the app name below with a globally unique name containing lowercase
letters, numbers and hyphens. Adjust the region to one available in your subscription.
The **B1 plan is a paid plan**; it is a simple starting point for this POC, not a
capacity guarantee for large documents or many simultaneous users.

```powershell
$resourceGroup = "rg-document-poc"
$planName = "plan-document-poc"
$appName = "YOUR-GLOBALLY-UNIQUE-APP-NAME"
$location = "centralindia"

az webapp list-runtimes --os linux --output table
$pythonRuntime = "PYTHON:3.12"
```

Confirm that `PYTHON:3.12` appears in the runtime list. If not, set `$pythonRuntime`
to an available Python version **3.12 or newer**, using the exact displayed value.

```powershell
az group create --name $resourceGroup --location $location
az appservice plan create --resource-group $resourceGroup --name $planName --location $location --sku B1 --is-linux
az webapp create --resource-group $resourceGroup --plan $planName --name $appName --runtime $pythonRuntime
az webapp update --resource-group $resourceGroup --name $appName --https-only true
```

If using the Azure portal to create the resources instead, choose **Web App →
Publish: Code → Runtime: Python → Operating System: Linux → Pricing plan: B1**.
Then set the PowerShell variables above to your actual resource names before
continuing. The CLI runtime list is the source of available versions.

### 3. Configure startup and logging

```powershell
az webapp config appsettings set --resource-group $resourceGroup --name $appName --settings WEBSITES_CONTAINER_START_TIME_LIMIT=1800 PROCESS_TIMEOUT_SECONDS=120 --output none
az webapp config set --resource-group $resourceGroup --name $appName --startup-file "bash startup-azure.sh" --always-on true --output none
az webapp log config --resource-group $resourceGroup --name $appName --docker-container-logging filesystem
```

Do not set `SCM_DO_BUILD_DURING_DEPLOYMENT` for the pre-built flow below: the
startup script itself creates the Python environment on first boot. If the app
was created with build automation enabled by default, turn it off:

```powershell
az webapp config appsettings set --resource-group $resourceGroup --name $appName --settings SCM_DO_BUILD_DURING_DEPLOYMENT=false --output none
```

The logging option is named `docker-container-logging` by Azure; it also captures
the managed Linux runtime's console output and does not require you to create Docker files.

- The startup command runs the supplied Bash file. It installs font/rendering and
  .NET OS dependencies, then prepares Python. A server-side build already has an
  `antenv`, and the script uses that. With server-side build skipped, it creates
  a virtual environment with `python -m venv --copies`. A normal venv on `/home`
  fails because Azure Files cannot host the `bin/python3` symlink, and the
  container exits before the app listens. If `--copies` still cannot run, the
  script creates the environment on local disk instead. It installs the .NET 10
  runtime under `/home/document-poc-dotnet` if absent and starts Uvicorn on
  `0.0.0.0:$PORT` (8000 on this image).
- The longer startup allowance (`WEBSITES_CONTAINER_START_TIME_LIMIT`) accommodates
  first-boot installs. It does not change the document-processing timeout.
- **Do not set `WEBSITE_RUN_FROM_PACKAGE`.** If reusing an app where this setting
  exists, remove it in **Settings → Environment variables**, save, and restart.
- If the portal's deployment UI offers **Skip Server-Side Build (Pre Built App)**,
  either setting works with this package. Leaving it off runs Oryx, which first
  replaces `/home/site/wwwroot` with `output.tar.zst`, `oryx-manifest.toml`, and
  `requirements.txt`. On startup the script copies the extracted application back
  into `/home/site/wwwroot`, deletes that manifest and archive, and starts Uvicorn
  from there. Refresh the Kudu file manager after the log line
  `startup: expected files are in /home/site/wwwroot`. The folder then contains:

```text
/home/site/wwwroot/app.py
/home/site/wwwroot/admission.py
/home/site/wwwroot/document_sdk.py
/home/site/wwwroot/requirements.txt
/home/site/wwwroot/startup-azure.sh
/home/site/wwwroot/static/
/home/site/wwwroot/artifacts/DocumentBridge.dll
/home/site/wwwroot/artifacts/libSkiaSharp.so
/home/site/wwwroot/artifacts/libHarfBuzzSharp.so
/home/site/wwwroot/fonts/LiberationSans-Regular.ttf
```

The next restart stays in that folder because the Oryx manifest is gone.
Skipping the server-side build leaves this layout in place from the ZIP itself.

See Microsoft's [ZIP deployment](https://learn.microsoft.com/en-us/azure/app-service/deploy-zip),
and [Python startup configuration](https://learn.microsoft.com/en-us/azure/developer/python/configure-python-web-app-on-app-service).

In the Azure portal, the same settings are under **Settings → Environment variables**
and **Settings → Configuration → General settings → Startup Command**.

### 4. Add the license and the process origin in Azure

For evaluation, no license setting is required. On Azure, `POST /api/process` stays closed until the origin allow list is set. In the Azure portal:

1. Open the web app and select **Settings → Environment variables**.
2. Add an app setting named **SYNCFUSION_LICENSE_KEY** with your valid key, if you have one.
3. Add an app setting named **ALLOWED_PROCESS_ORIGINS** with the value of your app URL.
4. Save/apply the settings and allow the app to restart.

A key in your Windows PowerShell session is **not** automatically sent to Azure. If `ALLOWED_PROCESS_ORIGINS` is missing on Azure, `POST /api/process` returns 503 and does not convert the file. The **Process document** button sends the page origin, so it matches this setting. Restart after saving the setting. The running site uses it only after this package is deployed.

### 5. Build a separate Linux deployment package on Windows

Return to the project folder in PowerShell. This creates a fresh staging folder
under your Windows temporary directory, leaving your local Windows `artifacts`
untouched. Ordinary .NET managed code can be published for `linux-x64` from Windows.

```powershell
$projectRoot = (Get-Location).Path
$stage = Join-Path ([System.IO.Path]::GetTempPath()) ("document-poc-azure-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $stage | Out-Null

Copy-Item -Path .\app.py, .\admission.py, .\document_sdk.py, .\requirements.txt, .\startup-azure.sh -Destination $stage
Copy-Item -Path .\static, .\fonts -Destination $stage -Recurse

dotnet publish .\DocumentBridge\DocumentBridge.csproj -c Release -r linux-x64 --self-contained false -o (Join-Path $stage "artifacts")
if ($LASTEXITCODE -ne 0) { throw "Linux worker publish failed. Do not deploy." }

# Ensure Bash receives LF line endings and UTF-8 without a BOM, even on Windows.
$startupPath = Join-Path $stage "startup-azure.sh"
$startupText = [System.IO.File]::ReadAllText($startupPath).Replace("`r`n", "`n").Replace("`r", "`n")
[System.IO.File]::WriteAllText($startupPath, $startupText, (New-Object System.Text.UTF8Encoding($false)))

# Compress-Archive stores entry names with backslashes. Linux unzip then creates
# files named "artifacts\DocumentBridge.dll" instead of an artifacts directory,
# and document operations cannot find the worker. Write forward-slash names.
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
$deploymentZip = Join-Path $projectRoot "document-web-poc.zip"
if (Test-Path $deploymentZip) { throw "Refusing to replace $deploymentZip. Choose the next version." }
$zip = [System.IO.Compression.ZipFile]::Open($deploymentZip, 'Create')
$stageRoot = (Resolve-Path $stage).Path.TrimEnd('\')
Get-ChildItem -Path $stage -Recurse -File | ForEach-Object {
  $entryName = $_.FullName.Substring($stageRoot.Length + 1).Replace('\', '/')
  [void][System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
    $zip, $_.FullName, $entryName, [System.IO.Compression.CompressionLevel]::Optimal)
}
$zip.Dispose()
Get-Item $deploymentZip
```

Do not use `Compress-Archive` for this package. Entry names must use `/`.

Open the ZIP and confirm its **top level** contains:

```text
app.py
admission.py
document_sdk.py
requirements.txt
startup-azure.sh
static/
fonts/
artifacts/
    DocumentBridge.dll
    DocumentBridge.deps.json
    DocumentBridge.runtimeconfig.json
    ...all other published dependencies...
```

Do not add an enclosing `document-web-poc/` folder. The original source ZIP is
**not** the deployment ZIP: it contains a parent folder and no published worker.
This staging approach also excludes private documents, local secrets, tests,
Git files and the Windows virtual environment. [Azure ZIP layout requirements](https://learn.microsoft.com/en-us/azure/app-service/deploy-zip#create-a-project-zip-package)

### 6. Deploy and open the hosted application

```powershell
az webapp deploy --resource-group $resourceGroup --name $appName --src-path $deploymentZip --type zip --async true --timeout 1800000
$siteHostname = az webapp show --resource-group $resourceGroup --name $appName --query defaultHostName --output tsv
Start-Process "https://$siteHostname"
```

Use the actual `defaultHostName` returned by Azure; do not guess it from the app
name. The first startup can take several minutes. Azure exposes the HTTPS URL;
users do not append `:8000` or open a separate public port.

Check that the page loads, then upload a small document and download the processed
result. Test Word, Excel and PowerPoint conversion, plus PDF watermarking, before
sharing **https://YOUR-AZURE-HOSTNAME** with testers. The app has no sign-in page;
anyone able to reach it can use it. For restricted testers, App Service's built-in
Authentication or Access restrictions can be configured separately.

Temporary document folders still get deleted before the download response is
returned. `/home/document-poc-dotnet` holds the installed runtime, not uploaded
documents, and should remain in place.

### 7. View logs and troubleshoot

```powershell
az webapp log tail --resource-group $resourceGroup --name $appName
```

Press **Ctrl+C** to stop watching logs; this does not stop the hosted app.
You can also use the Azure portal's **Monitoring → Log stream**. Deployment build
logs are available from **Deployment Center → Logs**.

| Symptom | What to check |
|---|---|
| `py` or `dotnet` is not recognized on Windows | Install the prerequisite and reopen PowerShell. Check Python's launcher and .NET SDK installation. |
| Windows reports a missing .NET framework | Install the .NET 10 x64 runtime/SDK; a newer major runtime alone does not satisfy this `net10.0` worker. |
| Windows port 8000 is already in use | Start with `run.py --port 8001`, then browse to port 8001. |
| Default Azure page or application error | Confirm Linux/Python, `bash startup-azure.sh`, successful build logs, and `app.py` at the ZIP root. |
| `bash: ...\r` or `$'\r': command not found` | Repeat the LF/no-BOM normalization in step 5 and redeploy. |
| Python module not found | Confirm the build flag was set before deployment and `requirements.txt` is at the ZIP root; redeploy. |
| Container exits in about 18s with `No such file or directory: '/home/document-poc-antenv/bin/python3'` | `/home` cannot host a symlink-based virtual environment. Redeploy the package whose startup script creates the environment with `--copies` and falls back to local disk. |
| `wwwroot` contains only `output.tar.zst` | Redeploy this package, restart, and wait for `startup: expected files are in /home/site/wwwroot`. Then refresh the file manager. That startup copies `app.py`, `static/`, and `artifacts/` into wwwroot and removes the Oryx archive. |
| Document worker unavailable (503) | Check the log for `startup: document worker ready at /home/site/wwwroot/artifacts`, that `artifacts/DocumentBridge.dll` is beside `app.py`, and that `dotnet --list-runtimes` lists `Microsoft.NETCore.App 10.0.x`. |
| Native library / `libSkiaSharp` / `libHarfBuzzSharp` error | Confirm `linux-x64` publish and successful OS-package installation. Inspect the actual worker error in Log stream. |
| PDF conversion returns 422 with `GetFont` or `NullReferenceException` | Deploy `document-web-poc.zip`. Syncfusion asks Skia for Tahoma before the substitute-font event, and Skia returns nothing unless that family is installed. The startup log must show `LiberationSans-Regular.ttf present` and `fc-match Tahoma:` pointing at a Liberation Sans file. `fonts/LiberationSans-Regular.ttf` must be in wwwroot. |
| PDF fonts or layout differ | Liberation Sans is the Linux substitute for fonts the image does not have. Install the document's original fonts when the layout must match them. |
| Startup fails during `apt-get` or runtime download | Check outbound access to the distro package mirrors and Microsoft's .NET download hosts. The script requires the built-in Linux stack's package-install permissions. |
| Processing timeout (504) | Try a smaller document; increase `PROCESS_TIMEOUT_SECONDS` if needed, subject to Azure's HTTP request timeout. |
| Too many requests (429) | The caller exceeded `RATE_LIMIT_REQUESTS` per window, or this process already has `MAX_CONCURRENT_JOBS` document jobs in flight. Wait for `Retry-After`, then try again. |

The POC installs OS packages at startup because it does not use a custom image.
Those packages can disappear when Azure replaces the instance, so the script
reapplies them; runtime files under `/home` are reused. Startup consequently depends
on network availability and may be slower. Microsoft describes this route for
[system packages in Python App Service](https://azureossd.github.io/2023/06/09/Python-on-App-Service-Linux-and-why-to-avoid-installing-packages-on-startup/).
Python packages are installed at deployment time, not each startup.
The .NET bootstrap uses the documented [runtime installation script](https://learn.microsoft.com/en-us/dotnet/core/tools/dotnet-install-script).

### 8. Redeploy changes or finish the POC

After changing Python, C#, frontend files or requirements, repeat **steps 5–6**.
This regenerates the Linux worker and deployment ZIP. A restart alone does not
upload local changes. Keep the app at one App Service instance for this simple
setup. That process runs at most `MAX_CONCURRENT_JOBS` document jobs at once (default 2). A second instance has its own cap.

When the POC is finished, delete its dedicated App Service plan and web app in the
Azure portal, or delete the dedicated resource group after checking its contents.
Stopping the web app alone does not stop App Service plan charges.

## Supported operations

| Input | Operation | Download |
|---|---|---|
| DOCX | Classification in headers/footers | classified.docx |
| XLSX | Classification in print headers/footers | classified.xlsx |
| PPTX | Classification at the top/bottom of slides | classified.pptx |
| DOCX, XLSX or PPTX | Convert to PDF | converted.pdf |
| PDF | Diagonal text watermark on every page | watermarked.pdf |

Choose one operation per request. To classify and then convert, download the
classified document and upload it for conversion. Labels accept 1–80 printable
ASCII characters. Excel markings appear in Print Preview, not worksheet cells.

## Temporary-file cleanup

Every request gets a new OS temporary folder with server-generated filenames.
After processing, the app reads the completed result into memory and deletes the
folder **before returning the download response**. It also deletes the folder
on validation failure, worker error, timeout or request cancellation. An interrupted
download therefore cannot retain the processing files. Uploaded multipart files
are closed as well.

The POC buffers the result in server/browser memory, accepts uploads up to 25 MB,
and defaults to a 120-second processing timeout. Set `PROCESS_TIMEOUT_SECONDS`
to change the timeout. `POST /api/process` is also limited per server process:
`MAX_CONCURRENT_JOBS` (default 2) in-flight jobs, and `RATE_LIMIT_REQUESTS`
per caller per `RATE_LIMIT_WINDOW_SECONDS` (default 10 per 60 seconds). A request
over either limit returns 429 before the upload is stored. A busy rejection still
counts against that caller's rate window. On Azure, `startup-azure.sh` sets
`TRUST_PROXY_HEADERS=1` so the caller is the last IP in `X-Forwarded-For`.
Local `run.py` ignores that header. A missing value uses the default. A non-integer,
zero, or negative value stops startup. These four names can also be Azure app
settings. A forced shutdown, OS crash or power failure can interrupt cleanup and
leave an OS temp folder behind.

## License

`SYNCFUSION_LICENSE_KEY` is an environment variable and is not stored in source. Leave it unset for evaluation.

Without a key, the app runs in evaluation mode; output may include trial watermarks.
To use a valid key, set it on the server before starting (do not put it in source):

```sh
export SYNCFUSION_LICENSE_KEY='your-valid-key'
python run.py
```

PowerShell: `$env:SYNCFUSION_LICENSE_KEY = 'your-valid-key'`.

## Tests

```sh
python -m pip install -r requirements-dev.txt
python -m pytest tests/test_app.py tests/test_worker.py -q
```

To verify all seven operations using generated (non-private) documents:

```sh
dotnet run --project tools/FixtureGenerator -c Release -- /tmp/document-poc-samples
TEST_FIXTURES=/tmp/document-poc-samples python -m pytest tests/test_real_operations.py -q
```

Windows: pass a Windows folder to FixtureGenerator and set `$env:TEST_FIXTURES`
to that folder before invoking pytest. These explicitly generated test samples
are retained for inspection; the web request folders are still automatically deleted.

`requirements-lock.txt` records the exact full environment used for verification.
The normal runtime installation needs only `requirements.txt`.

## Files

- `app.py`: upload validation, operation routing, download, cleanup, and request limits.
- `admission.py`: per-caller rate limit and in-process job slots for `POST /api/process`.
- `document_sdk.py`: asynchronous JSON subprocess adapter. One process per accepted call.
- `DocumentBridge/`: inherited C# document operations and updated license setup.
- `static/`: HTML, CSS, and ES5 JavaScript. Essential JS 2 34.1.29 is loaded from the Syncfusion CDN. No frontend build step.
- `run.py`: local / network server launcher.
- `startup-azure.sh`: .NET/rendering setup and web startup for Azure Python/Linux.
- `tests/`, `tools/FixtureGenerator/`: cleanup, concurrency and real-operation checks.

API: `POST /api/process` with multipart `file`, `operation`, and optional `label`.
Interactive API documentation is available at `/docs`.
