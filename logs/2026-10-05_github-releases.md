# 2026-10-05 — GitHub Releases for the AppImage and Flatpak

Phase 16 of `TASKS.md` ("publish AppImage and Flatpak as GitHub Releases from
CI"). The two packages already existed and built locally; what was missing was a
way to hand them to someone who does not want to run a build script.

---

## 14:43 — Publishing both packages from a tag

**Objective.** The AppImage and the Flatpak could only be produced on the
maintainer's machine, so "installing" Fallow meant cloning the repository and
running a build. The goal was a downloadable artifact per release, plus the
automation that produces it, so a release is something a reader can install and
not something an author has to assemble by hand.

**Solution.**

- `.github/workflows/release.yml` — a three-stage pipeline. `prepare` normalises
  the requested version; `appimage` and `flatpak` build in parallel; `release`
  creates or updates the GitHub Release and attaches both files.
  - triggered by `push` of a `v*` tag, or by `workflow_dispatch` with a version
    input (which also lets it create the tag);
  - `appimage` runs on `ubuntu-22.04` so the image keeps a low glibc floor; the
    `flatpak` job runs on `ubuntu-24.04` because it works against the KDE
    runtime rather than the host, and the newer `flatpak-builder` there is not
    exposed to flatpak#6818;
  - each job smoke-tests its own package before anything is published, and the
    `prepare` job rejects a version that is not `vMAJOR.MINOR.PATCH`.
- `appimage/build-appimage.sh` — `VERSION` now reads
  `FALLOW_VERSION` when set, so the workflow names the image after the tag while
  a local build keeps the pinned default.
- `.gitignore` — dropped the `.github/` entry that would have kept the workflow
  out of the repository.
- `README.md` — an "Install" section that leads with downloading a release
  asset, and keeps the build-from-source commands below it.
- `flatpak_appimage_build.md` — a "Cutting a release" section (section 8), plus
  the version table now points at the tag.

**Actions Performed.**

1. Read the existing packaging scripts, manifest, launcher and metadata to see
   how the two builds are wired, and confirmed the local artifacts still run:
   `build/appimage/Fallow.AppDir/usr/python/bin/python3 -P -c "import PySide6,
   pymupdf, numpy"` reported PySide6 6.11.2 / PyMuPDF 1.28.2 / numpy 2.2.6, and
   the installed Flatpak reported the same through
   `flatpak run --command=python3`.
2. Removed `.github/` from `.gitignore` so the workflow is tracked.
3. Made `VERSION` in `appimage/build-appimage.sh` overridable by
   `FALLOW_VERSION` (default unchanged at `0.14.0`).
4. Wrote `.github/workflows/release.yml`.
5. Added a versioned copy of the Flatpak bundle
   (`dist/Fallow-<version>-x86_64.flatpak`) because the build script's bundle
   name is fixed, so two downloads could otherwise be confused for one another.
6. Updated the README install section, the build doc, and `TASKS.md`.

**Verification Output.**

```
$ FALLOW_VERSION=9.9.9 bash appimage/build-appimage.sh
...
Built: /home/redram/python/Fallow/dist/Fallow-9.9.9-x86_64.AppImage (135M)

$ Fallow-9.9.9-x86_64.AppImage --appimage-extract
$ squashfs-root/usr/python/bin/python3 -P -c "import PySide6, pymupdf, numpy; ..."
bundled interpreters ok

$ flatpak run --command=python3 --env=PYTHONPATH=/app/lib/fallow \
      --env=QT_QPA_PLATFORM=offscreen org.fallow.PdfReader -P -c "..."
bundled interpreters ok

$ FLATPAK_USER_DIR=/tmp/fp-test flatpak install --user -y --noninteractive \
      --no-deps build/flatpak/org.fallow.PdfReader.flatpak
Installing app/org.fallow.PdfReader/x86_64/stable
exit=0

$ actionlint .github/workflows/release.yml
actionlint: clean

$ <tag-normalisation step, exercised standalone>
v0.14.0        -> OK version=0.14.0 tag=v0.14.0
0.15.0         -> OK version=0.15.0 tag=v0.15.0
development    -> REJECT vdevelopment
v1.2.3-rc4     -> REJECT v1.2.3-rc4
```

The two smoke tests are the same commands the workflow runs, so a packaged build
that cannot import its own Qt fails the release instead of shipping. The Flatpak
bundle was installed into a throwaway `FLATPAK_USER_DIR` so the working user
installation was left alone. The version-override build and the throwaway
Flatpak installation were both deleted afterwards; `dist/` holds only
`Fallow-0.14.0-x86_64.AppImage` again.

**References Used.**

1. https://github.com/softprops/action-gh-release — creating or updating a
   release and attaching assets with the default `GITHUB_TOKEN`.
2. https://docs.github.com/en/actions/using-workflows/events-that-trigger-workflows#push
   — the `push` `tags` filter, and why `github.ref_name` is the tag there.
3. https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions#permissions
   — the `contents: write` permission the release job needs.

**Optional steps.**

- Add a `pull_request` job that builds both packages without publishing, so a
  packaging change is validated before it is tagged.
- Have the workflow refresh the `<release>` entry in
  `packaging/org.fallow.PdfReader.metainfo.xml` from the tag, so the AppStream
  version never lags the release.
- Publish a `.zsync` alongside the AppImage so it can update itself.
- Cache the KDE runtime and the python-build-standalone tarball in the workflow,
  which is most of both jobs' runtime.

**Possible problems.**

- The workflow has not been run on GitHub yet — it is validated with
  `actionlint` and every build command was exercised locally, but the runner
  images themselves are unproven until the first tag is pushed.
- The Flatpak job downloads the KDE runtime, SDK and PySide6 BaseApp on every
  run (a few GB), so a release takes several minutes and there is no cache.
- The metainfo `<release>` is still hand-written, so a release tagged without
  bumping it will ship metadata naming the previous version.
- `softprops/action-gh-release` is pinned by major tag (`@v2`), so it is not
  reproducible bit-for-bit.
- Releases are unsigned: there is no GPG signature on the AppImage or the tag,
  so a download cannot be verified beyond the transport.

---

## 19:48 — Tagged v0.14.0 (release run blocked by a GitHub outage)

**Objective.** Turn the merged pipeline into an actual published release.

**Solution.** `development` and `main` had diverged (main carried the PR merge
commits), so `main` was updated by merging PR #5 (`e80572e`); that put
`.github/workflows/release.yml` on the default branch, which is also what makes
the "Run workflow" button appear. An annotated `v0.14.0` tag was then created on
that commit and pushed, which is the trigger the workflow waits for.

**Actions Performed.**
1. Confirmed the merge landed the workflow on `main`
   (`git ls-tree -r --name-only origin/main | grep .github`).
2. Tagged the merge commit: `git tag -a v0.14.0 e80572e -m "Fallow 0.14.0"`.
3. Pushed the tag: `git push origin v0.14.0`.
4. Checked the run with the GitHub API: the `Release` workflow is registered and
   `active`, and run #1 was created for the tag.
5. Found the job stuck in `queued` for ~15 minutes and traced it to a GitHub
   incident rather than the workflow.

**Verification Output.**

```
$ git push origin v0.14.0
 * [new tag]         v0.14.0 -> v0.14.0

run #1  id=37365807185  event=push  head_branch=v0.14.0  status=queued
job     id=111950543003 name="Resolve the version" labels=[ubuntu-latest]

$ curl https://www.githubstatus.com/api/v2/components.json
Actions status: degraded_performance      # "Partially Degraded Service"
```

**References Used.**

1. https://www.githubstatus.com/api/v2/components.json — the component feed that
   showed `Actions` as degraded while the job stayed queued.
2. https://docs.github.com/en/actions/writing-workflows/choosing-when-your-workflow-runs/events-that-trigger-workflows#push
   — the tag trigger, and why a tag push runs even though it is not on a branch.
3. https://docs.github.com/en/actions/how-tos/manage-workflow-runs/re-run-workflows-and-jobs
   — re-running a queued or failed run once capacity returns.

**Optional steps.** Re-run the job from the run page once Actions reports
operational. Add a `workflow_dispatch` dry-run input that builds and uploads the
artifacts without creating a release, so a runner breakage is found without
consuming a version number.

**Possible problems.** The first run is still unproven: the Flatpak job downloads
the KDE runtime, SDK and BaseApp (several GB) with no cache, and the AppImage job
is the first use of `appimage/build-appimage.sh` on `ubuntu-22.04`. Either may
need a follow-up commit. Until run #1 completes, the `v0.14.0` tag exists with no
release and no assets behind it.
