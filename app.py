from flask import Flask, render_template
from flask_socketio import SocketIO
import os
import subprocess
import select
import termios
import struct
import fcntl
import pty

# Soket programlama için ilgili kütüphaneleri ekliyoruz
app = Flask(__name__)
socketio = SocketIO(app)
app.config["fd"] = False
app.config["child_pid"] = None
app.config["cmd"] = ["bash"]


# Socket SSH Bağlantısı için
def set_winsize(fd, row, col, xpix=0, ypix=0):
    winsize = struct.pack("HHHH", row, col, xpix, ypix)
    fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)

def read_and_forward_pty_output():
    max_read_bytes = 1024 * 20
    while True:
        socketio.sleep(0.01)
        if app.config["fd"]:
            (data_ready, _, _) = select.select([app.config["fd"]], [], [], 0)
            if data_ready:
                output = os.read(app.config["fd"], max_read_bytes).decode(errors="ignore")
                socketio.emit("pty-output", {"output": output}, namespace="/pty")

@socketio.on("pty-input", namespace="/pty")
def pty_input(data):
    if app.config["fd"]:
        os.write(app.config["fd"], data["input"].encode())


@socketio.on("resize", namespace="/pty")
def resize(data):
    if app.config["fd"]:
        set_winsize(app.config["fd"], data["rows"], data["cols"])


@socketio.on("connect", namespace="/pty")
def connect():
    if app.config["child_pid"]:
        return
    
    (child_pid, fd) = pty.fork()
    if child_pid == 0:
        subprocess.run(app.config["cmd"])
    else:
        app.config["fd"] = fd
        app.config["child_pid"] = child_pid
        set_winsize(fd, 50, 50)
        socketio.start_background_task(target=read_and_forward_pty_output)

@app.route("/", methods=["GET"])
def login_screen():
    return render_template("index.html")

if __name__ == '__main__':
    socketio.run(app, port=8080, host="0.0.0.0", allow_unsafe_werkzeug=True)