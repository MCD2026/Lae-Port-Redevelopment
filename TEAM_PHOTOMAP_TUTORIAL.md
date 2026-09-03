# Team tutorial: build and host a PhotoMap on GitHub

This guide explains how to turn a package of location-tagged photographs into the same type of stakeholder website used for the Lae Port Redevelopment PhotoMap. The finished website contains:

- a 2D satellite map with coloured photo markers, a legend and north arrow;
- a Cesium 3D view and location-guided tour;
- optimised web copies of the photographs; and
- one public link that viewers can open without ACC or GitHub login.

The current example is:

- Repository: <https://github.com/MCD2026/Lae-Port-Redevelopment>
- Stakeholder page: <https://mcd2026.github.io/Lae-Port-Redevelopment/>

## 1. Choose the correct workflow

| Situation | Recommended method |
|---|---|
| Add new photographs to the existing Lae Port map | Upload them to `incoming-photos` on GitHub. The build and publication are automatic. |
| Replace the existing Lae Port collection with a complete new package | Clone the repository and run `tools/Rebuild-LaePort.ps1` with `-Replace -Publish`. |
| Create a PhotoMap for another project at a new URL | Copy this repository as a starter, change the visible project information, rebuild with `-Replace`, and enable GitHub Pages. |

For routine updates, use the first method. It needs no QGIS, ACC or local development environment.

## 2. Prepare and check the photo package

### Supported input

The rebuild accepts either of these inputs:

1. **Original geotagged JPG/JPEG photographs.** GPS latitude and longitude must still be present in the photo metadata.
2. **A QGIS/qgis2web-style export.** The package must contain an `images` folder and a `data` or `layers` folder containing the JavaScript feature files that point to those images.

The input may be a folder or a ZIP file when using the Windows rebuild command.

### Requirements

- Use the original camera or phone files whenever possible.
- Acceptable extensions are `.jpg` and `.jpeg`, including uppercase forms.
- Each photo name should be unique within its location group.
- Keep the GPS/location metadata. Screenshots, email previews, social-media downloads and some image editors often remove it.
- A capture date, altitude and compass direction are helpful but not required. GPS coordinates are required.
- Do not upload confidential or personally sensitive images to a public repository.

### Optional location groups

For original photos, place photographs in first-level folders to create location groups. For example:

```text
New-Photo-Package/
├── Lae Port Existing Wharf/
│   ├── IMG_1001.jpg
│   └── IMG_1002.jpg
├── Lae Port Landside/
│   └── IMG_1101.jpg
└── HBS Services/
    └── IMG_1201.jpg
```

The first folder name becomes the marker group. For the Lae project, reuse these existing group names if possible:

- `HBS Camp Accommodation`
- `HBS Services`
- `Lae Port Existing Wharf`
- `Lae Port Landside`
- `Pacific Marine Group - Kimbe Port`
- `Ready Mixed Concrete PNG`
- `Trans Pacific Piling`

Photos uploaded without a subfolder are placed in `New Photos`.

## 3. Fastest method: update the existing map in a browser

This is the normal process for new site-visit photographs.

1. Sign in to GitHub with an account that has write access to `MCD2026/Lae-Port-Redevelopment`.
2. Open [`incoming-photos`](https://github.com/MCD2026/Lae-Port-Redevelopment/tree/main/incoming-photos).
3. Select **Add file**, then **Upload files**.
4. Drag in the new original JPG/JPEG photographs.
5. Add a short commit message, for example `Add Lae Port photos 2026-09-03`.
6. Choose **Commit directly to the main branch**, then select **Commit changes**.
7. Open the repository's [Actions](https://github.com/MCD2026/Lae-Port-Redevelopment/actions) tab.
8. Watch **Process New Lae Port Photos**. Do not upload another batch until this run is green.
9. Open the stakeholder page and refresh it: <https://mcd2026.github.io/Lae-Port-Redevelopment/>.
10. Check both **2D Map** and **3D Tour**, open two or three markers, and confirm the newest images are present.

GitHub's browser uploader currently permits up to 100 files at a time and 25 MiB per file. Upload a large package in batches and wait for each batch to finish before starting the next one. See [Adding a file to a repository](https://docs.github.com/en/repositories/working-with-files/managing-files/adding-a-file-to-a-repository).

### What the automation does

The workflow:

1. reads the GPS coordinates and optional direction from each photo;
2. rejects the batch if required GPS metadata is missing;
3. resizes and compresses each photograph for reliable web viewing;
4. adds the new locations to the shared dataset;
5. updates the photo counts on the 2D/3D website;
6. extends the local terrain cache when new locations require it;
7. removes processed originals from `incoming-photos`;
8. commits the generated website files; and
9. republishes the same stakeholder URL.

The existing live website remains available while a new version is being processed. Removing the uploaded originals from the latest branch does not erase them from Git history, so the public-repository warning still applies.

## 4. Full local rebuild on Windows

Use this method for a large package, a full replacement, or when the browser uploader is inconvenient.

### One-time setup

Install:

- [GitHub Desktop](https://desktop.github.com/) and sign in;
- [Python 3](https://www.python.org/downloads/windows/) with **Add Python to PATH** selected during installation; and
- Git for Windows, which is normally installed with GitHub Desktop.

Clone the repository:

1. On GitHub, open <https://github.com/MCD2026/Lae-Port-Redevelopment>.
2. Select **Code**, then **Open with GitHub Desktop**.
3. Choose a local folder and select **Clone**.

GitHub also documents this process in [Cloning a repository from GitHub to GitHub Desktop](https://docs.github.com/en/desktop/adding-and-cloning-repositories/cloning-a-repository-from-github-to-github-desktop).

### Check the package without changing anything

Open PowerShell in the cloned repository folder and run:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\Rebuild-LaePort.ps1 `
  -Source "C:\SiteVisit\Lae-Photos.zip" `
  -DryRun
```

Replace the example path with the real folder or ZIP path. A successful result reports the number of input, existing and new photos. The wrapper automatically installs its required Python image library if it is missing.

### Append new photographs and publish

Use this when the current photos must stay on the map:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\Rebuild-LaePort.ps1 `
  -Source "C:\SiteVisit\New-Lae-Photos" `
  -Publish
```

The script asks you to type `PUBLISH`. It then commits and pushes the rebuilt site. Omit `-Replace` for an append update.

### Replace the whole collection and publish

Use this only when the package is the new complete source of truth:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\Rebuild-LaePort.ps1 `
  -Source "C:\SiteVisit\Complete-Lae-Package.zip" `
  -Replace `
  -Publish
```

`-Replace` removes generated photos that are not in the new package. Always run `-DryRun` first and retain an independent copy of the source package.

### Preview before publishing

Run the rebuild without `-Publish`, then start a local web server:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\Rebuild-LaePort.ps1 `
  -Source "C:\SiteVisit\Complete-Lae-Package.zip" `
  -Replace

python -m http.server 8000 --directory github-pages
```

Open <http://localhost:8000/>. Stop the preview with `Ctrl+C`.

After a preview rebuild, the repository contains uncommitted changes. Review them in GitHub Desktop, enter a commit message, select **Commit to main**, then **Push origin**. Do not rerun the wrapper with `-Publish` while those uncommitted changes are present; its safety check will stop.

### Useful options

| Option | Meaning |
|---|---|
| `-DryRun` | Validate and count the input without changing the website. |
| `-Replace` | Replace the entire photo collection. Without it, the script appends only new photos. |
| `-Publish` | Commit and push the generated website after a successful rebuild. |
| `-Yes` | Publish without asking for the typed `PUBLISH` confirmation. Use only in a trusted scripted process. |
| `-MaxSize 1600` | Set the longest web-image edge in pixels. Allowed range: 800–4000. |
| `-Quality 70` | Set JPEG quality. Allowed range: 50–95. |
| `-SkipTerrain` | Skip downloading new 3D terrain. Use only for testing or when all locations are already covered. |

## 5. Create a PhotoMap in a new GitHub repository

The current repository is a working starter, but some names are Lae-specific. A new project therefore needs a one-time configuration.

### A. Create the empty repository

1. In the `MCD2026` GitHub organisation, create a repository with the required URL-safe name, for example `New-Project-PhotoMap`.
2. Choose **Public** if stakeholders must open it without signing in.
3. Leave **Add a README**, `.gitignore` and licence unchecked because the starter already contains these files.

The final URL will normally be:

```text
https://mcd2026.github.io/New-Project-PhotoMap/
```

Repository names and public URLs should be treated as permanent once shared.

### B. Copy the working starter without its history

1. Open <https://github.com/MCD2026/Lae-Port-Redevelopment>.
2. Select **Code → Download ZIP**.
3. Extract the ZIP and rename the extracted folder to `New-Project-PhotoMap`.
4. Open PowerShell in that folder.

Do not push this starter yet. It still contains the example Lae photographs. The `-Replace` rebuild in step D removes those generated files before the new repository is created.

Downloading a ZIP instead of cloning avoids copying the Lae project's full Git history into the new project.

### C. Change the visible project information

Use a text editor such as Visual Studio Code. Update these visible items before publishing:

- `github-pages/index.html`: page title, description, heading, subtitle and all old `og:url`/`og:image` URLs;
- `github-pages/map/index.html`: 2D page title, accessibility label and `siteColours` names/colours;
- `github-pages/3d/index.html`: 3D page title, description, heading and accessibility label;
- `github-pages/social-preview.png`: optional project-specific sharing image;
- `README.md`: repository description and stakeholder URL;
- `tools/Rebuild-LaePort.ps1`: displayed project name and stakeholder URL;
- `.github/workflows/rebuild-from-photos.yml`: displayed workflow and commit names.

For the safest first copy, keep the internal filename and JavaScript variable `Lae_Port_Photos` unchanged. The Python script, 2D map, 3D map and Actions workflow all refer to it. Renaming it is possible, but every reference must be changed together.

For new marker groups, add each exact group name and colour to the `siteColours` object in `github-pages/map/index.html`. Folder/layer names and legend names must match exactly.

### D. Build the new package

From the clean local copy, validate first:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\Rebuild-LaePort.ps1 `
  -Source "C:\SiteVisit\New-Project-Package.zip" `
  -DryRun
```

Then replace the starter's Lae collection:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\Rebuild-LaePort.ps1 `
  -Source "C:\SiteVisit\New-Project-Package.zip" `
  -Replace
```

Preview with the local server described above. Check the title, logo, photo count, legend, markers, popups, close zoom and 3D tour.

### E. Push the first version

```powershell
git init -b main
git remote add origin https://github.com/MCD2026/New-Project-PhotoMap.git
git add .
git commit -m "Create New Project PhotoMap"
git push -u origin main
```

The destination repository must be empty for this simple first push. If it is not empty, stop and reconcile the histories rather than using a force push.

### F. Enable automatic processing and GitHub Pages

1. Open the new repository on GitHub.
2. Go to **Settings → Actions → General**.
3. Under **Workflow permissions**, select **Read and write permissions**, then save. This permits the photo-processing workflow to commit its generated output.
4. Go to **Settings → Pages**.
5. Under **Build and deployment**, choose **GitHub Actions** as the source.
6. Open **Actions** and confirm **Deploy GitHub Pages** completes successfully.
7. Open the Pages URL shown by the successful deployment.

The included workflow follows GitHub's custom Pages process: configure Pages, upload the `github-pages` directory as an artifact, and deploy it. See [Using custom workflows with GitHub Pages](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages) and [Configuring a publishing source](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site).

After the first deployment, the team can use the browser-only `incoming-photos` process for normal updates.

## 6. Final quality-assurance checklist

Before sharing the link, test it in an incognito/private browser window so the test does not rely on a staff login.

- The page opens without GitHub or ACC authentication.
- The correct project title, subtitle and logo appear.
- The displayed photo count matches the expected total.
- Satellite imagery appears in the 2D view.
- **Fit all** shows every project area.
- Marker colours match the legend.
- The north arrow remains visible.
- Several marker popups show the correct photos.
- Close zoom continues to show imagery rather than `Data not available`.
- The 3D view loads terrain and markers.
- **Play tour** follows a comfortable location-based route.
- The layout works on both a desktop screen and a phone.

## 7. Troubleshooting

| Symptom | Likely cause | What to do |
|---|---|---|
| `Process New ... Photos` is red | One or more files lack GPS metadata, contain duplicate names, or are unsupported | Open the failed Action, expand the red step, identify the named file, and replace it with the original geotagged JPG/JPEG. |
| No workflow starts | Files were uploaded outside `incoming-photos`, use a different extension, or Actions are disabled | Confirm the path and extension, then check **Settings → Actions**. |
| Workflow cannot push its result | Repository workflow token is read-only | Select **Read and write permissions** under **Settings → Actions → General**. |
| Pages URL shows 404 | Pages is not enabled or deployment has not completed | Set Pages source to **GitHub Actions** and wait for **Deploy GitHub Pages** to turn green. |
| Old version still appears | Browser or CDN cache | Wait a minute, then use `Ctrl+F5` or test in a private window. |
| A new photo does not appear | Same group and filename already exist | Rename the original file uniquely and upload it again. |
| New markers have the wrong colour or no legend entry | The folder/layer name is not in `siteColours` | Add the exact group name and colour to `github-pages/map/index.html`, then commit and push. |
| 2D basemap disappears at close zoom | The copied template lost the Esri native-zoom limit | Preserve `maxNativeZoom: 17` and the higher display `maxZoom` setting in the Leaflet tile layer. |
| 3D terrain is flat at a new remote location | Terrain generation was skipped or does not cover the new coordinates | Rebuild without `-SkipTerrain`, commit the new `github-pages/terrain` files and republish. |
| Repository becomes very large | Too many originals or unnecessarily large generated images | Keep only optimised web copies in the live site, add photos in sensible batches, and consider starting a fresh annual/project repository if history becomes excessive. |

Do not move the website images to Git LFS: GitHub states that Git LFS cannot be used with GitHub Pages sites. See [About Git Large File Storage](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-git-large-file-storage).

## 8. Recommended team operating procedure

Assign three simple roles:

1. **Photo owner:** retains the original photo package and checks that location services were enabled during capture.
2. **Publisher:** uploads a batch, watches the Action, and records the publication date.
3. **Checker:** opens the public link without signing in and completes the quality-assurance checklist.

For every update, record the project, source package, photo count, GitHub commit, Action result and final public URL. The public URL should remain unchanged throughout the project.
