# VapeOff
VapeOff is a tool wich uses the lack of authentication in the communication protocoll, to control vaporizers (at the moment only the Crafty) from Storz&Bickel. The issue was reported to Storz&Bickel on 15 August 2019. The 90 days deadline expired on 13.11.2019 without reaction, and therefore this script will be published without fix for the devices.

Currently it is possible to heat devices up (without led and vibration) and prevent shutdown by the owner, to prevent turning devices on and to let all craftys (with enabled bluetooth) in proximity vibrate and blink.

## Usage
```
usage: vapeoff.py [-h] [-i INTERFACE] [-m MAC] [-a] [-o] [-p] [-s] [-f]
                  [-t TARGET_TEMP] [-l] [-v]

optional arguments:
  -h, --help            show this help message and exit
  -i INTERFACE, --interface INTERFACE
                        specify interface (default: hci0)
  -m MAC, --mac MAC     specify target mac (default: None)
  -a, --all             attack all devices in area, overwrites '--mac'
                        (default: False)
  -o, --heat            start device(s) (default: False)
  -p, --perm            enable permanent bluetooth (default: False)
  -s, --silent          deactivate vibration and leds of devices (default:
                        False)
  -f, --vibrate         let devices vibrate (default: False)
  -t TARGET_TEMP, --target_temp TARGET_TEMP
                        sets the target temperature (default: None)
  -l, --list-devices    run discovery and print macs of supported devices in
                        the area. Can be combined with '--mac' and '--all'
                        (default: False)
  -v, --verbose
```

## Examples

Turning all Crafty's (with bluetooth enabled) on in proximity and activates permament bluetooth.
```
python3 vapeoff.py -o -a --perm
```
Turning on only a specified device without notification of the owener
```
python3 vapeoff.py -o -m [MAC] --silent
```

Preventing tuning on of all Crafty's in proximity
As soon as the device is turned on this script connects and stops the heating.
```
python3 vapeoff.py -a
```

Letting all Crafty's (with bluetooth enabled) in proximity vibrate and blink
```
python3 vapeoff.py -a -f
```

## Workarounds

a) Sometimes disconnecting fails. In this case the connection must be disconnected manually. This is possible via Bluetooth Manager or resetting the Bluetooth interface. 

## What can i do to protect my Crafty?
1. Turn off permament bluetooth.
2. Connect your smartphone to your Crafty as soons as you turn it on.
3. If you realize that your device is heating up without your interaction, leave the area as a bluetooth connection is needed. Make sure permanent bluetooth was not activated.

## Why do you release this tool?
Because wether i release it or not the attack is possible. I hope that the release puts pressure on Storz & Bickel to fix this issue.

## Dependencies
* python3
* bitstring
* gatt>=0.2.7
