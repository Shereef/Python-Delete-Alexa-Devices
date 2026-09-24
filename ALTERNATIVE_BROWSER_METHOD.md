# Alternative Browser JavaScript Method (Issue #9)

> **⚠️ Security Warning:** This method requires pasting code into your browser's Developer Console. You should never paste code into your console unless you understand exactly what it does, as it can allow attackers to steal your session cookies or take over your account.

If you prefer a simpler, sniffer-free approach, there is a browser-based JavaScript method reported in issue #9 that uses your logged-in Alexa session to call the same APIs directly from the browser console. This method was contributed and documented by `rPraml` (with additional helpful steps from `Fade2Gray2`), building on the reverse-engineering work by `Shereef` and the `alexa-remote` project by `Apollon77`.

- **Credit:** rPraml, Fade2Gray2, Apollon77 (see the original discussion: https://github.com/Shereef/Python-Delete-Alexa-Devices/issues/9).
- **What it does:** Uses the browser's existing Amazon cookies/session and the Alexa web endpoints to list smart-home devices and call the delete endpoint for each device.

- **Quick one-liner (paste into the browser Console on the Alexa region domain that returns your device JSON):**

```javascript
devices = await (await fetch('/nexus/v1/graphql', { method: 'POST', headers: {"Content-Type": "application/json","Accept": "application/json"}, body: JSON.stringify({query: `query { endpoints { items { friendlyName legacyAppliance { applianceId }}} } `})})).json();for (const device of devices.data.endpoints.items) console.log(await fetch(`/api/phoenix/appliance/${encodeURIComponent(device.legacyAppliance.applianceId)}`, { method: "DELETE", headers: { "Accept": "application/json", "Content-Type": "application/json"}}))
```

- **Safari Console:** Safari does not support top-level `await`. Wrap the code in an async function:

```javascript
(async () => {
  const devices = await (await fetch('/nexus/v1/graphql', { method: 'POST', headers: {"Content-Type": "application/json","Accept": "application/json"}, body: JSON.stringify({query: `query { endpoints { items { friendlyName legacyAppliance { applianceId }}} } `})})).json();
  for (const device of devices.data.endpoints.items) {
    console.log(await fetch(`/api/phoenix/appliance/${encodeURIComponent(device.legacyAppliance.applianceId)}`, { method: "DELETE", headers: { "Accept": "application/json", "Content-Type": "application/json"}}));
  }
})();
```

- **If the one-liner fails, CSRF fallback:** some accounts require a CSRF token. You can obtain a CSRF token from an Amazon page (for example by inspecting a cart update request on www.amazon.com/.de) and then run:

```javascript
csrf = '<your-csrf-value-here>'
devices = await (await fetch('/nexus/v1/graphql', { method: 'POST', headers: {"Content-Type": "application/json","Accept": "application/json"}, body: JSON.stringify({query: `query { endpoints { items { friendlyName legacyAppliance { applianceId }}} } `})})).json()
for (const device of devices.data.endpoints.items) console.log(await fetch(`/api/phoenix/appliance/${encodeURIComponent(device.legacyAppliance.applianceId)}`, { method: "DELETE", headers: { "Accept": "application/json", "Content-Type": "application/json", "csrf": csrf }}))
```

> **Note:** The deletion methods (both Python and JS) rely on the `legacyAppliance` API. This works for many devices (e.g., TP-Link, Kasa, Gree) but may fail for "non-legacy" devices like Home Assistant integrations (Issue #3). These devices might return a 200 OK status but remain undeleted.

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
