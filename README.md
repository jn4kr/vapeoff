# VapeOff
VapeOff is a tool wich uses the lack of authentication in the communication protocoll, to controll vaporizers (at the moment only the Crafty) from Storz&Bickel. The issue was reported to Storz&Bickel on 15 August 2019. The 90 days deadline expired on 13.11.2019 without reaction, and therefore this script will be published without fix for the devices.

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
## Workarounds

a) Sometimes disconnecting fails. In this case the connection must be disconnected manually. This is possible via Bluetooth Manager or resetting the Bluetooth interface. 

## Dependencies
* python3
* bitstring
* gatt>=0.2.7
