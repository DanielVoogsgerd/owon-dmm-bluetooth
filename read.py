from argparse import ArgumentParser
from collections.abc import Iterable

import gatt


class AnyDevice(gatt.Device):
    def connect_succeeded(self):
        super().connect_succeeded()
        print("[%s] Connected" % (self.mac_address))

    def connect_failed(self, error):
        super().connect_failed(error)
        print("[%s] Connection failed: %s" % (self.mac_address, str(error)))

    def disconnect_succeeded(self):
        super().disconnect_succeeded()
        print("[%s] Disconnected" % (self.mac_address))

    def services_resolved(self):
        super().services_resolved()

        measurement_service = next(
            s for s in self.services if s.uuid == "0000fff0-0000-1000-8000-00805f9b34fb"
        )

        measurement_characteristic = next(
            s
            for s in measurement_service.characteristics
            if s.uuid == "0000fff4-0000-1000-8000-00805f9b34fb"
        )

        measurement_characteristic.enable_notifications()

        # print("[%s] Resolved services" % (self.mac_address))
        # for service in self.services:
        #     print("[%s]\tService [%s]" % (self.mac_address, service.uuid))
        #     for characteristic in service.characteristics:
        #         print("[%s]\t\tCharacteristic [%s]" % (self.mac_address, characteristic.uuid))
        #         print(characteristic)
        #         if isinstance(characteristic, Iterable):
        #             for descriptor in characteristic.descriptors:
        #                 print("[%s]\t\t\tDescriptor [%s] (%s)" % (self.mac_address, descriptor.uuid, descriptor.read_value()))
        #         else:
        #             print("No descriptors")

    def descriptor_read_value_failed(self, descriptor, error):
        print("descriptor_value_failed")

    def characteristic_enable_notification_succeeded(self, characteristic):
        print("Notification subscription succesful")

    def characteristic_enable_notification_failed(self, characteristic):
        print("Notification subscription failed")

    def characteristic_value_updated(self, characteristic, value):
        print("Value updated")
        print(get_function(value))
        print(
            "{value} * 10^{order}".format(
                value=get_value(value), order=get_order(value)
            )
        )


def get_function(data):
    number = (data[1] & 0b11) << 2 | data[0] >> 6
    return [
        "Voltage DC",
        "Voltage AC",
        "Current DC",
        "Current AC",
        "Resistance",
        "Capacitance",
        "Frequency",
        "Duty Cycle",
        "Temperature Celsius",
        "Temperature Fahrenheit",
        "Diode",
        "Continuity",
        "Unknown #12",
        "NCV",
        "Unknown #14",
        "Unknown #15",
    ][number]


def get_value(data):
    sign = -1 if data[5] >> 7 == 1 else 1
    number = (data[5] & 0b0111_1111) << 8 | data[4]
    decimal = data[0] & 0b0111
    return sign * number / 10**decimal


def get_order(data):
    return (((data[0] >> 3) & 0b0111) - 4) * 3


arg_parser = ArgumentParser(description="GATT Connect Demo")
arg_parser.add_argument("mac_address", help="MAC address of device to connect")
args = arg_parser.parse_args()

print("Connecting...")

manager = gatt.DeviceManager(adapter_name="hci0")

device = AnyDevice(manager=manager, mac_address=args.mac_address)
device.connect()

manager.run()
