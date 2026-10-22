# Fast Contacts — Phone + Contacts

Modern Android dialer and contacts app based on the original Fast Contacts project.

## Features (all preserved)

- **Phone tab:** recent call history (with type indicators), custom dialpad, instant matching contacts while dialing, direct call, create-contact from number, hide/show keypad.
- **Contacts tab:** searchable alphabetical list, alphabet index, label/group chips, favorites, detail/edit screens, organize, settings, share, SMS, WhatsApp and other installed apps.
- **Permissions:** READ/WRITE_CONTACTS, CALL_PHONE, READ_CALL_LOG — requested only when needed; denied states handled without crashing.
- **Dark mode:** Material 3 DayNight theme with light and night color sets.

## Performance upgrades (this revision)

- **Pre-indexed search:** `SearchEngine` builds a normalized index (lowercased names, digit-only phones, emails) once when contacts load. Each keystroke reuses that index instead of re-lowercasing and re-filtering every contact.
- **Cached engines:** MainActivity and Dialpad keep a shared `SearchEngine` instance across typing; label-filtered searches still build a scoped engine only when needed.
- **Debounce:** Contacts search ~50 ms, dialpad matching ~40 ms — responsive without flooding background work.
- **Stale-result guards:** Generation counters prevent older background searches from overwriting newer results.
- **RecyclerView:** Contact list uses `ListAdapter` + `DiffUtil`; call log now uses the same pattern.
- **Dialpad layout:** Flexible space above the keypad keeps the keypad from jumping when the first digit is typed; recent calls stay visible when the number field is empty.

## Phone tab polish

- Call history rows show avatar initials, call-type arrow/color (incoming / outgoing / missed / rejected), relative time, and a one-tap call button.
- Empty and permission-denied states remain informative.

## Build without Android Studio (GitHub Actions)

1. Create a new GitHub repository and upload **the contents of this folder** (so that `app/`, `build.gradle.kts`, `settings.gradle.kts`, `gradle/`, and `.github/` sit at the repo root).
2. Open **Actions** → **Build FastContacts APK** → **Run workflow**, or push a commit to `main`.
3. When the workflow finishes, download the **FastContacts-APK** artifact (`app-debug.apk`).

The workflow uses **Java 17** and **Gradle 8.9**. It generates the Gradle wrapper at build time, so wrapper files do not need to be committed.

### Workflow file

`.github/workflows/build.yml` runs:

```text
gradle wrapper --gradle-version 8.9
./gradlew --no-daemon assembleDebug
```

and uploads `app/build/outputs/apk/debug/app-debug.apk`.

## Package / identity

- Application ID: `com.example.fastcontacts`
- Min SDK 24, target/compile SDK 35
- Kotlin 2.0.21, AGP 8.7.3

## Verification note

Source was inspected and upgraded in place. A full Android Gradle build was **not** executed in this environment (no Android SDK/Gradle cache available here). Treat the first GitHub Actions run as the compile verification before installing the APK.
