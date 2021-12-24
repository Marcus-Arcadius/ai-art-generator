import threading
import time
import shlex
import subprocess
import sys
import keyboard
import unicodedata
import re
import random
from pathlib import Path
from collections import deque

ITERATIONS = 500        # number of times to run, default is 500
LEARNING_RATE = 0.1     # default = 0.1
INPUT_IMAGE = ""        # path and filename of starting image, eg: samples/vectors/face_07.png
TRANSFORMER = ""        # needs to be a .yaml and .ckpt file in /checkpoints directory for whatever is specified here

# Prevent threads from printing at same time.
print_lock = threading.Lock()

# worker thread executes specified shell command
class Worker(threading.Thread):
    def __init__(self, command, callback=lambda: None):
        threading.Thread.__init__(self)
        self.command = command
        self.callback = callback

    def run(self):
        with print_lock:
            print("\n\nWorker starting, command: " + self.command)

        # create output folder if it doesn't exist
        filepath = self.command.split(" -o ",1)[1]
        filepath = filepath.replace(filepath[filepath.rindex('/'):], "")
        Path(filepath).mkdir(parents=True, exist_ok=True)
        # invoke VQGAN+CLIP
        subprocess.call(shlex.split(self.command))

        with print_lock:
            print("Worker done.")
        self.callback()

# controller manages worker thread(s) and user input
# TODO change worker_idle to array of bools to manage multiple threads/gpus
class Controller:
    def __init__(self):

        self.iterations = ITERATIONS
        self.learning_rate = LEARNING_RATE
        self.input_image = INPUT_IMAGE
        self.transformer = TRANSFORMER

        self.prompt_file = TextFile('prompts.txt')
        self.style_file = TextFile('styles.txt')
        self.work_queue = deque()
        self.work_done = False
        self.worker_idle = True
        self.is_paused = False
        self.jobs_done = 0
        self.styles = []
        keyboard.on_press_key("f10", lambda _:self.pause_callback())
        keyboard.on_press_key("esc", lambda _:self.exit_callback())
        self.init_work_queue()

    # build a work queue with the specified prompt and style files
    def init_work_queue(self):

        # construct array of styles from given style text file
        while self.style_file.lines_remaining() > 0:
            self.styles.append(self.style_file.next_line())

        # construct work queue consisting of all prompt+style combos
        while self.prompt_file.lines_remaining() > 0:
            base = "python generate.py -i " + str(self.iterations) + " -lr " + str(self.learning_rate) + " -p \""
            subject = self.prompt_file.next_line()
            base += subject
            outdir="output/" + slugify(subject)

            for style in self.styles:
                work = base + " | " + style + "\""

                if self.input_image != "":
                    work += " -ii " + self.input_image
                if self.transformer != "":
                    work += " -conf checkpoints/" + self.transformer + ".yaml -ckpt checkpoints/" + self.transformer + ".ckpt"

                seed = random.randint(100000000000000,999999999999999)
                work += " -sd " + str(seed) + " -o " + outdir + "/" + slugify(style) + ".png"

                self.work_queue.append(work)

    # start a new worker thread
    def do_work(self, command):
        self.worker_idle = False
        thread = Worker(command, self.on_work_done)
        thread.start()

    # callback for worker threads when finished
    def on_work_done(self):
        self.worker_idle = True
        self.jobs_done += 1

    # pause execution at user request
    def pause_callback(self):
        self.is_paused = not self.is_paused
        if self.is_paused:
            with print_lock:
                print("\n\n*** Work will be paused when current operation finishes! ***")
                print("*** (press 'F10' again to unpause, or <ESC> to quit) ***\n")
        else:
            with print_lock:
                print("\n*** Work resuming! ***\n")

    # allow exit at user request if currently paused
    def exit_callback(self):
        if self.is_paused:
            print("Exiting...")
            self.work_done = True

# for easy reading of prompt/style files
class TextFile():
    def __init__(self, filename):
        self.lines = deque()

        with open(filename) as f:
            l = f.readlines()

        for x in l:
            x = x.strip();
            if x != "" and x[0] != '#':
                # these lines are actual prompts
                x = x.strip('\n')
                self.lines.append(x)

    def next_line(self):
        return self.lines.popleft()

    def lines_remaining(self):
        return len(self.lines)

# Taken from https://github.com/django/django/blob/master/django/utils/text.py
# Using here to make filesystem-safe directory names
def slugify(value, allow_unicode=False):
    value = str(value)
    if allow_unicode:
        value = unicodedata.normalize('NFKC', value)
    else:
        value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
    value = re.sub(r'[^\w\s-]', '', value.lower())
    return re.sub(r'[-\s]+', '-', value).strip('-_')

# entry point
if __name__ == '__main__':

    control = Controller()
    while not control.work_done:

        # worker is idle, start some work
        if (control.worker_idle and not control.is_paused):
            if len(control.work_queue) > 0:
                control.do_work(control.work_queue.popleft())

            else:
                # no more prompts to work on
                print('\nAll work done!')
                control.work_done = True

        else:
            time.sleep(.01)

    exit()