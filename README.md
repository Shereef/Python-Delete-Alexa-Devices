# Alexa-Device-Management

This repository contains a Python script for managing devices connected to the Amazon Alexa API. The script provides functionality to retrieve and delete entities and endpoints related to an Amazon Alexa skill.

⚠️⚠️ **Warning:** This script is not intended to be used for malicious purposes. I am not responsible for any damage caused by the use of this script. Use at your own risk. Also note that this script is not officially supported by Amazon and may break at any time. It is also not recommended to use this script for a small number of devices, as it takes a while to set up. If you only want to delete a few devices, it is probably faster to do it manually. ⚠️⚠️

## Heads up

I do not know **anything** about how the Alexa API works. I just reverse engineered the API calls the Alexa app makes and wrote a script to automate them. I do not know if this script will work for you. I left as many comments as possible here and in the script itself, so you can try and debug and use it yourself. If you have any questions, feel free to open an issue or write a comment in the [r/AmazonEcho](https://www.reddit.com/r/amazonecho/comments/18phvps/manage_amazon_alexa_devices_with_python/?utm_source=share&utm_medium=web2x&context=3) or [r/HomeAssistant](https://www.reddit.com/r/homeassistant/comments/18phwta/manage_amazon_alexa_devices_with_python/?utm_source=share&utm_medium=web2x&context=3) subreddit posts or alternatively create an issue in the Git repo. I will try and answer all of them as soon as possible.

## Prerequisites

The script is written in Python 3.11 and requires the following packages:
- requests  
_see requirements.txt for more details_   
Run `pip install -r requirements.txt` to install required packages

To get the needed HTTP headers and cookie information, you will need to download some kind of HTTP traffic sniffer.  

### iOS
I used [HTTP Catcher](https://apps.apple.com/de/app/http-catcher/id1445874902), which is only available for iOS.  
Alternatively [Proxyman](https://apps.apple.com/us/app/proxyman-network-debug-tool/id1551292695), also works on iOS.

### Android
Tools like [HTTP Toolkit](https://httptoolkit.tech/) should work for Android-based devices, but this app requires a rooted device.  
(For this, there is a workaround, somewhat at least. If you install `Windows Subsystem for Android` on your device with Google apps and `Magisk` following [this](https://ahaan.co.uk/article/top_stories/google-play-store-windows-11-install) guide, you can simulate a rooted Android device and don't have to backup (or delete) any data. Make sure you install a version with the `Nightly-with-Magisk-canary-MindTheGapps-RemovedAmazon` tag for the same setup as I used in my testing. This is probably the version you want to install anyways).  
_Note: For using an HTTP Sniffer on Android, you will need to install the certificate of the sniffer app on your device. Proxy-based sniffers will not work, as the Alexa app (and most other ones like Google and PayPal) uses certificate pinning._

You also need to have a valid Amazon account and access to the account you want to delete entities from.

## Usage

The script reads credentials from environment variables or from a local `config.json` file. Do not commit your real config.

1. Download and install an HTTP sniffer on your device.
2. Open the Alexa app and log in with the account you want to clean up.
3. Navigate to the `Devices` tab.
4. Start a capture, refresh the device list, and delete one cloud-connected device manually.
5. Capture these request values:
   - `Host`, for example `eu-api-alexa.amazon.in`
   - `Cookie`
   - `csrf`
   - `x-amzn-alexa-app`
   - optionally `User-Agent` and `Accept-Language`
6. Copy `config.example.json` to `config.json` and fill in the captured values.
7. Start with a dry run:

```sh
python main.py --dry-run
```

8. If the dry run lists the devices you expect, set `"dry_run": false` in `config.json` or run:

```sh
python main.py
```

You can also use environment variables instead of `config.json`:

```sh
export ALEXA_HOST="eu-api-alexa.amazon.in"
export ALEXA_COOKIE="paste-cookie-header-here"
export ALEXA_CSRF="paste-csrf-token-here"
export ALEXA_X_AMZN_ALEXA_APP="paste-x-amzn-alexa-app-header-here"
python main.py --dry-run
```

The script fetches devices with GraphQL and deletes matching devices with:

```text
DELETE /api/phoenix/appliance/<legacyAppliance.applianceId>
```

By default it filters for manufacturer names containing `SmartLife`. Override that with `--manufacturer` or `ALEXA_MANUFACTURER_FILTER`.

## Troubleshooting

1. Confirm `ALEXA_HOST` or `host` matches the host captured from your Alexa app.
2. Refresh `Cookie`, `csrf`, and `x-amzn-alexa-app` if the script previously worked but now fails.
3. Try the captured `User-Agent` and `Accept-Language` values if Amazon rejects requests.
4. Run `python main.py --dry-run --save-graphql graphql.json` to inspect the returned `legacyAppliance.applianceId` values before deleting.

## Inspiration

An Amazon employee told me "have fun with that" when I asked him how to delete devices connected to an Alexa skill. So I did.

## Inscription

Thanks to the original author @[Pytonballoon810](https://github.com/Pytonballoon810).

Thanks to @[HennieLP](https://github.com/hennielp) for helping me with the script and the README (also thanks to him I didn't have to root my phone to get an HTTP Sniffer running <3).

## Browser JavaScript Method (Issue #9)

If you prefer a simpler, sniffer-free approach, there is a browser-based JavaScript method reported in issue #9 that uses your logged-in Alexa session to call the same APIs directly from the browser console. This method was contributed and documented by `rPraml` (with additional helpful steps from `Fade2Gray2`), building on the reverse-engineering work by `Shereef` and the `alexa-remote` project by `Apollon77`.

- **Credit:** rPraml, Fade2Gray2, Apollon77 (see the original discussion: https://github.com/Shereef/Python-Delete-Alexa-Devices/issues/9).
- **What it does:** Uses the browser's existing Amazon cookies/session and the Alexa web endpoints to list smart-home devices and call the delete endpoint for each device.

- **Quick one-liner (paste into the browser Console on the Alexa region domain that returns your device JSON):**

```
devices = await (await fetch('/nexus/v1/graphql', { method: 'POST', headers: {"Content-Type": "application/json","Accept": "application/json"}, body: JSON.stringify({query: `query { endpoints { items { friendlyName legacyAppliance { applianceId }}} } `})})).json();for (const device of devices.data.endpoints.items) console.log(await fetch(`/api/phoenix/appliance/${encodeURIComponent(device.legacyAppliance.applianceId)}`, { method: "DELETE", headers: { "Accept": "application/json", "Content-Type": "application/json"}}))
```

- **If the one-liner fails, CSRF fallback:** some accounts require a CSRF token. You can obtain a CSRF token from an Amazon page (for example by inspecting a cart update request on www.amazon.com/.de) and then run:

```
csrf = '<your-csrf-value-here>'
devices = await (await fetch('/nexus/v1/graphql', { method: 'POST', headers: {"Content-Type": "application/json","Accept": "application/json"}, body: JSON.stringify({query: `query { endpoints { items { friendlyName legacyAppliance { applianceId }}} } `})})).json()
for (const device of devices.data.endpoints.items) console.log(await fetch(`/api/phoenix/appliance/${encodeURIComponent(device.legacyAppliance.applianceId)}`, { method: "DELETE", headers: { "Accept": "application/json", "Content-Type": "application/json", "csrf": csrf }}))
```

- **Usage summary:**
    - Log in to your Amazon/Alexa account in a desktop browser.
    - Open each candidate region URL and find the one returning JSON (examples: https://alexa.amazon.com/api/behaviors/entities?skillId=amzn1.ask.1p.smarthome, https://pitangui.amazon.com/..., https://alexa.amazon.de/..., etc.).
    - With that page open, press F12 → Console, paste the script, and press Enter.
    - Refresh the device list page; if deletions succeeded it should be empty or much smaller. You may need to run the script twice.
    - Force‑close and re-open the Alexa mobile app and pull to refresh the device list if needed (the app caches heavily).

### Step-by-step browser method

1. **Use a desktop browser and sign in** — open Chrome, Edge, or Firefox and sign in to the same Amazon account used by your Alexa app.

2. **Find the Alexa region JSON endpoint** — open each of these URLs in separate tabs until one returns a JSON array/object containing your device list (one will show JSON or text containing devices):
    - https://alexa.amazon.com/api/behaviors/entities?skillId=amzn1.ask.1p.smarthome
    - https://pitangui.amazon.com/api/behaviors/entities?skillId=amzn1.ask.1p.smarthome
    - https://layla.amazon.com/api/behaviors/entities?skillId=amzn1.ask.1p.smarthome
    - https://alexa.amazon.de/api/behaviors/entities?skillId=amzn1.ask.1p.smarthome
    - https://alexa.amazon.co.jp/api/behaviors/entities?skillId=amzn1.ask.1p.smarthome

3. **Keep the JSON page/tab open** — this tab's host is important because the script uses relative `fetch()` paths and will use that domain's cookies.

4. **Open Developer Tools → Console** — press `F12` or `Ctrl+Shift+I` and switch to the `Console` tab. Make sure the console is cleared so output is easy to read.

5. **Verify you can see the devices from the Console (optional)** — run the GraphQL query only to inspect the returned device list before deleting anything:

```
devices = await (await fetch('/nexus/v1/graphql', { method: 'POST', headers: {"Content-Type":"application/json","Accept":"application/json"}, body: JSON.stringify({query: `query { endpoints { items { friendlyName legacyAppliance { applianceId }}} } `})})).json();
console.log(devices.data.endpoints.items)
```

6. **Run the deletion script (one-liner)** — paste the quick one-liner into the Console and press Enter. This will iterate over devices and call the delete endpoint for each one:

```
devices = await (await fetch('/nexus/v1/graphql', { method: 'POST', headers: {"Content-Type": "application/json","Accept": "application/json"}, body: JSON.stringify({query: `query { endpoints { items { friendlyName legacyAppliance { applianceId }}} } `})})).json();for (const device of devices.data.endpoints.items) console.log(await fetch(`/api/phoenix/appliance/${encodeURIComponent(device.legacyAppliance.applianceId)}`, { method: "DELETE", headers: { "Accept": "application/json", "Content-Type": "application/json"}}))
```

7. **If the API requires CSRF, use the fallback** — some browsers/accounts require a CSRF token in a header. To get one:
    - Open `www.amazon.com` or `www.amazon.de` in a new tab and add any item to the cart.
    - Open Developer Tools → Network and clear the network log.
    - Change the quantity of the cart item and watch for a request like `ref=ox_sc_update_quantity`.
    - Inspect that request's headers and look for either a `csrf` header value or a cookie value that looks like `csrf=`; some browsers use `anti-csrftoken-a2z` instead.
    - Copy the token string.

    Back on the Alexa JSON tab Console, run:

```
csrf = '<paste-csrf-here>'
devices = await (await fetch('/nexus/v1/graphql', { method: 'POST', headers: {"Content-Type":"application/json","Accept":"application/json"}, body: JSON.stringify({query: `query { endpoints { items { friendlyName legacyAppliance { applianceId }}} } `})})).json()
for (const device of devices.data.endpoints.items) console.log(await fetch(`/api/phoenix/appliance/${encodeURIComponent(device.legacyAppliance.applianceId)}`, { method: "DELETE", headers: { "Accept": "application/json", "Content-Type": "application/json", "csrf": csrf }}))
```

8. **Check results** — after the script finishes, reload the JSON URL tab. A successful wipe will show an empty array `[]` or a much smaller list (only devices provided by active skills).

9. **Force the Alexa app to sync** — the Alexa mobile app caches device lists. Force-close and reopen the Alexa app and pull-to-refresh Devices → All Devices.

10. **Troubleshooting tips**
     - If the Console shows `200 OK` but the device is still listed, try running the script again or wait and repeat the refresh steps.
     - If the JSON tab is rendered as formatted JSON by the browser and the relative `fetch()` calls fail, open the Alexa root page for that region (for example `https://alexa.amazon.de/`) and run the same script from that tab so relative paths resolve.
     - If you see CORS or mixed-content errors, ensure you're on the correct host and using the same protocol (https).
     - If you still need help, include console output and which host URL returned your devices when opening an issue.

- **Safety & notes:**
    - This uses your authenticated browser session and existing cookies. Run it at your own risk.
    - The API endpoints and required headers/CSRF behavior may change anytime and the script may stop working.
    - Deletion requests often return HTTP 200 even if the device was not removed; verify by refreshing the device list.
