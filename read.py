#!/usr/bin/env python
from argparse import ArgumentParser
from collections.abc import Iterable
from typing import Callable, NamedTuple, Any
import logging
import sys
from datetime import datetime
from dataclasses import dataclass
from decimal import Decimal
import gatt
from time import sleep


@dataclass
class Measurement():
    mantissa: Decimal
    order: int
    prefix: str
    unit: str
    function: str

    @property
    def value(self) -> float:
        return float(self.mantissa) * 10**self.order


MacAddress = str

Formatter = Callable[[MacAddress, datetime, Measurement], str]


class AnyDeviceManager(gatt.DeviceManager):
    def device_discovered(self, device):
        if device.alias() == "BDM":
            logger.info("Discovered multimeter [%s] %s" % (
                device.mac_address, device.alias()))
            self.owon_mac = device.mac_address
            self.stop()


class OwonDMM(gatt.Device):
    def __init__(self, mac_address, manager, on_measurement: Callable[[MacAddress, datetime, Measurement], Any], auto_reconnect=True):
        super().__init__(mac_address, manager)
        self.on_measurement = on_measurement
        self.auto_reconnect = auto_reconnect

    def connect_succeeded(self):
        super().connect_succeeded()
        logger.info("[%s] Connected to multimeter" % (self.mac_address))

    def connect_failed(self, error):
        super().connect_failed(error)
        logger.critical("[%s] Connection to multimeter failed: %s" %
                        (self.mac_address, str(error)))
        if self.auto_reconnect:
            logger.info("[%s] Attempting to reconnect" % self.mac_address)
            while True:
                sleep(1)
                self.connect()

    def disconnect_succeeded(self):
        super().disconnect_succeeded()
        logger.info("[%s] Disconnected from multimeter" % (self.mac_address))

        if self.auto_reconnect == True:
            self.connect()

    def services_resolved(self):
        super().services_resolved()
        logger.debug("[%s] Services resolved" % (self.mac_address))

        # Find measurement service
        measurement_service = next(
            s for s in self.services if s.uuid == "0000fff0-0000-1000-8000-00805f9b34fb"
        )

        # Find measurement characteristic
        measurement_characteristic = next(
            s
            for s in measurement_service.characteristics
            if s.uuid == "0000fff4-0000-1000-8000-00805f9b34fb"
        )

        measurement_characteristic.enable_notifications()

    def descriptor_read_value_failed(self, descriptor, error):
        logger.critical(
            f"Could not read value from descriptor: {descriptor}; received error: {error}")

    def characteristic_enable_notification_succeeded(self, characteristic):
        logger.debug(
            f"Successfully subscribed to characteristic notifications: {characteristic}")

    def characteristic_enable_notification_failed(self, characteristic):
        logger.warn("Could not subscribe to characteristic notifications")
        logger.debug(
            f"Failed to subscribe to characteristic notifications: {characteristic}")

    def characteristic_value_updated(self, characteristic, value):
        self.on_measurement(self.mac_address, datetime.now(), Measurement(
            get_mantissa(value),
            get_order(value),
            get_prefix(value),
            get_unit(value),
            get_function(value)
        ))

        unit = get_unit(value)
        # if unit:
        #     print(
        #         "{value} {prefix}{unit} ({function})".format(
        #             value=get_mantissa(value), prefix=get_prefix(value), unit=get_unit(value), function=get_function(value)
        #         )
        #     )
        # else:
        #     print(
        #         "{value} * 10^{order}".format(
        #             value=get_mantissa(value), order=get_order(value)
        #         )
        #     )


def get_function_index(data):
    return (data[1] & 0b11) << 2 | data[0] >> 6


def get_function(data):
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
    ][get_function_index(data)]


def get_unit(data):
    return [
        "V",
        "V",
        "A",
        "A",
        "Ohm",
        "F",
        "Hz",
        "%",
        "°C",
        "°F",
        "V",
        "Ohm",
        None,
        None,
        None,
        None,
    ][get_function_index(data)]


def get_order_index(data):
    return ((data[0] >> 3) & 0b0111) - 4


def get_order(data):
    return 3 * get_order_index(data)


def get_prefix(data):
    return [
        "",  # 0
        "k",  # 1
        "M",  # 2
        "n",  # -3
        "u",  # -2
        "m",  # -1
    ][get_order_index(data)]


def get_mantissa(data):
    sign = -1 if data[5] >> 7 == 1 else 1
    number = (data[5] & 0b0111_1111) << 8 | data[4]
    decimal = data[0] & 0b0111
    return Decimal(sign * number) / Decimal(10**decimal)


def csv_formatter(mac_address: str, time: datetime, measurement: Measurement) -> str:
    return "{mac_address};{time};{function};{value};{unit}".format(
        mac_address=mac_address,
        time=time.timestamp(),
        function=measurement.function,
        value=measurement.value,
        unit=measurement.unit
    )


def json_formatter(mac_address: str, time: datetime, measurement: Measurement) -> str:
    pass


def default_formatter(mac_address: str, time: datetime, measurement: Measurement) -> str:
    return "{mac_address} {time} {function} {value} {unit}".format(
        mac_address=mac_address,
        time=time,
        function=measurement.function,
        value=measurement.value,
        unit=measurement.unit
    )


arg_parser = ArgumentParser(
    description="A tool for reading bluetooth values from owon multimeters")
arg_parser.add_argument(
    "--format",
    help="Set custom format type. One can choose from JSON, CSV, or omit to get a legible tabular output",
    type=str,
    choices=["json", "csv"]
)
arg_parser.add_argument(
    "-v", "--verbose",
    action="store_true"
)

args = arg_parser.parse_args()

logging.basicConfig(format='%(levelname)s: %(message)s')

logger = logging.getLogger(__name__)

if args.verbose:
    logger.setLevel(logging.DEBUG)
else:
    logger.setLevel(logging.INFO)


FORMATTERS = {
    "csv": csv_formatter,
    "json": json_formatter,
}

discovery_manager = AnyDeviceManager(adapter_name='hci0')
discovery_manager.start_discovery()
logger.info("Looking for multimeters...")

discovery_manager.run()

manager = gatt.DeviceManager(adapter_name="hci0")

measurement_formatter = default_formatter
if args.format:
    measurement_formatter = FORMATTERS[args.format]

device = OwonDMM(on_measurement=lambda *args, **kwargs: print(measurement_formatter(*
                 args, **kwargs), flush=True), manager=manager, mac_address=discovery_manager.owon_mac)
device.connect()

manager.run()
