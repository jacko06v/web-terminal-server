import pty
import os
import subprocess
import select
import termios
import struct
import fcntl
import logging
import json

import paho.mqtt.client as mqtt
import threading


FORMAT = '%(asctime)s %(message)s'
logging.basicConfig(format=FORMAT, level=logging.DEBUG)

DEVICE_ID = "raspberrypi"
# DEVICE_SHELL = "bash"
DEVICE_SHELL = "sh"
MQTT_HOST = "localhost"
MQTT_PORT = 8883
MQTT_USER = "mqtt"
MQTT_PASSWD = ""
MQTT_USE_TLS = True


class AttrDict(dict):
    def __init__(self, *args, **kwargs):
        super(AttrDict, self).__init__(*args, **kwargs)
        self.__dict__ = self


config = AttrDict(fd=None, cmd=DEVICE_SHELL, child_pid=None)


def set_winsize(fd, row, col, xpix=0, ypix=0):
    logging.debug(f"Setting window size with termios: {row}x{col}")
    winsize = struct.pack("HHHH", row, col, xpix, ypix)
    fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)


def resize(data):
    if config.fd:
        logging.debug(f"Resizing window to {data['rows']}x{data['cols']}")
        set_winsize(config.fd, data["rows"], data["cols"])


def read_and_forward_pty_output(mqttc):
    max_read_bytes = 1024 * 20
    while True:
        if config.fd:
            try:
                timeout_sec = None
                (data_ready, _, _) = select.select(
                    [config.fd], [], [], timeout_sec)
                logging.debug("Data ready: " +
                              ",".join(map(lambda x: str(x), data_ready)))
            except select.error:
                logging.info("select error")
                pass
            if data_ready:
                output = os.read(config.fd, max_read_bytes).decode(
                    errors="ignore"
                )
                mqttc.publish(
                    f"/device/{DEVICE_ID}/terminal/output", json.dumps({"output": output}))


def pty_input(data):
    """write to the child pty. The pty sees this as if you are typing in a real
    terminal.
    """
    if config.fd:
        logging.debug("Received input from browser: %s" % data["input"])
        os.write(config.fd, data["input"].encode())


def mqtt_on_connect(client, userdata, flags, rc):
    logging.debug(f"Connected with result code {rc}")
    if rc == 0:
        client.subscribe(f"/device/{DEVICE_ID}/terminal/input")
        client.subscribe(f"/device/{DEVICE_ID}/terminal/resize")
    else:
        logging.error("Connection failed")
    t1 = threading.Thread(target=read_and_forward_pty_output,
                          args=(client,), daemon=True)
    t1.start()


# The callback for when a PUBLISH message is received from the server.
def mqtt_on_message(client, userdata, msg):
    topic = msg.topic
    payload = msg.payload.decode('utf8')
    data = json.loads(payload)
    logging.debug(f"Topic: {msg.topic}, pyload: {payload}")
    if topic == f"/device/{DEVICE_ID}/terminal/input":
        pty_input(data)
    elif topic == f"/device/{DEVICE_ID}/terminal/resize":
        resize(data)


if __name__ == "__main__":
    # create child process attached to a pty we can read from and write to
    (child_pid, fd) = pty.fork()
    if child_pid == 0:
        # this is the child process fork.
        # anything printed here will show up in the pty, including the output
        # of this subprocess
        while True:
            subprocess.run(config.cmd)
    else:
        # this is the parent process fork.
        # store child fd and pid
        config.fd = fd
        config.child_pid = child_pid
        set_winsize(fd, 50, 50)

        client = mqtt.Client()

        if MQTT_USE_TLS:
            client.tls_set("emqxsl-ca.crt")
            client.tls_insecure_set(True)
        client.username_pw_set(
            username=MQTT_USER, password=MQTT_PASSWD)
        client.on_connect = mqtt_on_connect
        client.on_message = mqtt_on_message

        client.connect(MQTT_HOST, MQTT_PORT, 60)

        # Blocking call that processes network traffic, dispatches callbacks and
        # handles reconnecting.
        # Other loop*() functions are available that give a threaded interface and a
        # manual interface.
        with mqtt.Client() as client:
            # setup and connect the client
            client.loop_forever()
