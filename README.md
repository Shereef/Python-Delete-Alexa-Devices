# Alexa-Device-Management

This repository contains a Python script for managing devices connected to the Amazon Alexa API. The script provides functionality to retrieve and delete entities and endpoints related to an Amazon Alexa skill.

⚠️⚠️ **Warning:** This script is not intended to be used for malicious purposes. I am not responsible for any damage caused by the use of this script. Use at your own risk. Also note that this script is not officially supported by Amazon and may break at any time. It is also not recommended to use this script for a small number of devices, as it takes a while to set up. If you only want to delete a few devices, it is probably faster to do it manually. ⚠️⚠️

## Heads up

I do not know **anything** about how the Alexa API works. I just reverse engineered the API calls the Alexa app makes and wrote a script to automate them. I do not know if this script will work for you. I left as many comments as possible here and in the script itself, so you can try and debug and use it yourself. If you have any questions, feel free to open an issue or write a comment in the [r/AmazonEcho](https://www.reddit.com/r/amazonecho/comments/18phvps/manage_amazon_alexa_devices_with_python/?utm_source=share&utm_medium=web2x&context=3) or [r/HomeAssistant](https://www.reddit.com/r/homeassistant/comments/18phwta/manage_amazon_alexa_devices_with_python/?utm_source=share&utm_medium=web2x&context=3) subreddit posts or alternatively create an issue in the Git repo. I will try and answer all of them as soon as possible.

## Alternative Browser Method

If you are having trouble setting up the Python script or extracting cookies, there is a much simpler, sniffer-free approach that uses your browser's Developer Console. See [ALTERNATIVE_BROWSER_METHOD.md](ALTERNATIVE_BROWSER_METHOD.md) for instructions.

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

## Contributing

Contributions are welcome! Please see our [Contributing Guidelines](CONTRIBUTING.md) and [Code of Conduct](CODE_OF_CONDUCT.md).

## Security

To report a security vulnerability, please follow our [Security Policy](SECURITY.md).

## Inspiration

An Amazon employee told me "have fun with that" when I asked him how to delete devices connected to an Alexa skill. So I did.

## Inscription

Thanks to the original author @[Pytonballoon810](https://github.com/Pytonballoon810).

Thanks to @[HennieLP](https://github.com/hennielp) for helping me with the script and the README (also thanks to him I didn't have to root my phone to get an HTTP Sniffer running <3).


