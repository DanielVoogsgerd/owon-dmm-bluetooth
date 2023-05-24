#!/usr/bin/env python
import sys
from collections import defaultdict
from time import sleep
from matplotlib import pyplot as plt
from datetime import datetime

if __name__ == "__main__":
    graphs = {}
    fig = plt.figure()
    ax = fig.add_subplot(111)
    fig.show()

    while True:
        line = sys.stdin.readline()

        if not line:
            break

        mac, time, function, value, unit = line.split(";")

        if (mac, unit) not in graphs:
            graphs[(mac, unit)] = {
                "data": []
            }

        graphs[(mac, unit)]["data"].append(
            (datetime.fromtimestamp(float(time)), float(value)))

        ax.clear()
        ax.set_xlabel("Time")
        for (mac, unit), graph in graphs.items():
            x, y = zip(*graph['data'])
            ax.plot(x, y)
            ax.set_ylabel(unit)

        plt.draw()
        fig.canvas.flush_events()

    # plt.show()
    while True:
        sleep(0.5)
        plt.draw()
        ax.autoscale()
        fig.canvas.flush_events()
