# Google setup (Gmail and Calendar)

Jarvis talks to Gmail and Google Calendar through your own Google Cloud project. You do this once.

## 1. Create the project and enable the APIs
1. Open <https://console.cloud.google.com/> and sign in with the Google account Jarvis should use.
2. Project picker (top bar) > **New project** > name it `Jarvis` > **Create**, then select it.
3. **APIs & Services > Library**: search for and **Enable** both **Gmail API** and **Google Calendar API**.

## 2. Configure the consent screen
1. **APIs & Services > OAuth consent screen** (or **Google Auth Platform**) > **Get started**.
2. App name `Jarvis`, support email = your address, audience **External**, contact email = your address.
3. **Audience / Test users**: add your own Google address. Leave the app in *Testing* mode.
   Note: in Testing mode the login token expires after 7 days, so you will sign in again weekly. This is normal.
4. **Data access / Scopes** (optional here, Jarvis requests them at login):
   - `https://www.googleapis.com/auth/calendar.events` (view, create, edit events)
   - `https://www.googleapis.com/auth/gmail.readonly` (read and summarize mail)
   - `https://www.googleapis.com/auth/gmail.compose` (save drafts and send)

## 3. Create the OAuth client
1. **APIs & Services > Credentials > Create credentials > OAuth client ID**.
2. Application type **Desktop app**, name `Jarvis desktop` > **Create**.
3. **Download JSON** and save it as `credentials.json` in the Jarvis data folder:
   `%APPDATA%\Jarvis\credentials.json` (override with `JARVIS_GOOGLE_CREDENTIALS`).

`credentials.json` and `token.json` are secrets. They are gitignored; never commit or share them.
