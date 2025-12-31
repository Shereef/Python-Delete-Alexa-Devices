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

1. Download and install an HTTP Sniffer on your device.
2. Open the Alexa app and log in with the account you want to delete entities from.
3. Navigate to the `Devices` tab.
4. Open the HTTP Sniffer and start a new capture.
5. In the Alexa app, refresh the device list by pulling down.
6. Let the page load completely.
7. Delete a device using the Alexa app.
8. Stop the capture in the HTTP Sniffer.
9. Extract the following values from your HTTP Sniffer:
   - **HOST**: The host from the `GET /api/behaviors/entities` request (e.g., `na-api-alexa.amazon.com` or `eu-api-alexa.amazon.co.uk`)
   - **COOKIE**: The full `Cookie` header value from the `GET /api/behaviors/entities` request (will be very long)
   - **X_AMZN_ALEXA_APP**: The `x-amzn-alexa-app` header value from the `GET /api/behaviors/entities` request
   - **DELETE_SKILL**: From the `DELETE` request containing `/api/phoenix/appliance/`, copy the part after `api/phoenix/appliance/` but before `%3D%3D_` (e.g., `SKILL_abc123abc...`)

10. Run the script. You can provide values in three ways:

    **Interactive mode** (prompts for all values):
    ```bash
    python main.py
    ```
    The script will prompt you for each value. CSRF is automatically extracted from the cookie.

    **Command-line arguments** (skip prompts):
    ```bash
    python main.py --host na-api-alexa.amazon.com --cookie "..." --alexa-app "..." --delete-skill "..."
    ```

    **Environment variables** (skip prompts):
    ```bash
    export ALEXA_HOST="na-api-alexa.amazon.com"
    export ALEXA_COOKIE="..."
    export ALEXA_APP="..."
    export ALEXA_DELETE_SKILL="..."
    python main.py
    ```

    You can mix and match - provide some values via arguments/env vars and the script will only prompt for the missing ones.

If it works, you should see a list of all devices connected to the account you are logged in with. If you get an error, see the [Troubleshooting](#troubleshooting) section for more information.

## Troubleshooting

1. Try changing the `HOST` address to your local Amazon address. You can find it in the HTTP Sniffer in both the requests you copied the headers from. Provide it via `--host` argument or `ALEXA_HOST` environment variable.
2. If you used the script some time ago, try updating the `COOKIE` value - cookies expire. Provide it via `--cookie` argument or `ALEXA_COOKIE` environment variable.
3. Make sure you copied the complete cookie string - it should be very long. The CSRF token is automatically extracted from the cookie, so you don't need to provide it separately.

## Inspiration

An Amazon employee told me "have fun with that" when I asked him how to delete devices connected to an Alexa skill. So I did.

## Inscription

Thanks to the original author @[Pytonballoon810](https://github.com/Pytonballoon810).

Thanks to @[HennieLP](https://github.com/hennielp) for helping me with the script and the README (also thanks to him I didn't have to root my phone to get an HTTP Sniffer running <3).
