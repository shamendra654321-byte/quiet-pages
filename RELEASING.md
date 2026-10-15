# Announcing updates

Before publishing an app update, replace RELEASE_NOTES.md with a short explanation of the final change: new features, fixes, any setup steps and known limitations. Do not reuse old feature announcements for a different release.

Push the finished change to main. The Windows workflow runs tests, builds the app and publishes a preview release using RELEASE_NOTES.md as its announcement. The download website reads GitHub releases when visitors open it, so the new download and announcement appear without a website redeployment.

Visitors can follow GitHub release notifications (Watch → Custom → Releases) or the Atom feed at https://github.com/shamendra654321-byte/quiet-pages/releases.atom. The website does not collect emails or send messages itself.

The website is at https://quiet-pages.abuzzlion9.chatgpt.site. Its source is maintained in the connected Sites project. Review automated build results and test listening on Windows before calling any release stable.

The build stamps app_version.py with preview-RUN_NUMBER-RUN_ATTEMPT. Keep this tag format and the QuietPages-Windows-x64.zip asset name: the in-app updater compares these numeric versions, including prereleases, and requires GitHub's asset SHA-256 digest. Never replace an existing release asset in place; publish a new numbered release. Checks occur at app startup or through Help, and announcements are shown before downloading. This is not a background service or email notification system.
