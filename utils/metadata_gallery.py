# Copyright 2021 - 2022, Bill Kennedy (https://github.com/rbbrdckybk/ai-art-generator)
# SPDX-License-Identifier: MIT

# image metadata/gallery tool
# point this at a directory full of images created via AI Art Generator to generate:
# 1) an HTML gallery page that displays all images along with their prompt metadata
# 2) a prompt file that can be used to create similar images

import shlex
import subprocess
import sys
import unicodedata
import re
import random
import os
from os.path import exists
from pathlib import Path
from PIL import Image
from PIL.ExifTags import TAGS

# prompt file class
class PromptFile:
    def __init__(self, prompt_file):
        self.prompt_file_name = prompt_file
        self.f = None
        self.prompt_count = 0
        self.init_prompts()

    # create the prompt file, populate it
    def init_prompts(self):
        self.f = open(self.prompt_file_name, 'w')

        self.write("# *******************************************************************************")
        self.write("# Generated by utils/metadata_gallery.py")
        self.write("# Place this file in your prompts directory and run with:")
        self.write("# python make_art.py prompts/gallery_prompts.txt")
        self.write("# see docs for settings info: https://github.com/rbbrdckybk/ai-art-generator#usage")
        self.write("# *******************************************************************************\n")
        self.write("[subjects]")
        self.write("!PROCESS = stablediff")
        self.write("!SD_LOW_MEMORY = no            # change to yes if you need the low-memory version")
        self.write("!UPSCALE_KEEP_ORG = yes        # keep original when upscaling?")
        self.write("!SAMPLES = 3                   # default 3 images per prompt, change if desired")
        self.write("!REPEAT = yes")

    # add prompt block
    def add_prompt_section(self, prompt, width, height, steps, scale, initimg, initstr, upscale_use, upscale_amt, upscale_face):
        self.write("\n# *********************************************** [prompt " + str(self.prompt_count+1) + " ] ***********************************************\n")
        self.write("!WIDTH = " + str(width))
        self.write("!HEIGHT = " + str(height))
        self.write("!STEPS = " + str(steps))
        self.write("!SCALE = " + str(scale))
        if initimg != "":
            self.write("!INPUT_IMAGE = " + initimg)
            self.write("!STRENGTH = " + str(initstr))
        self.write("!USE_UPSCALE = " + upscale_use)
        if upscale_use == "yes":
            self.write("!UPSCALE_AMOUNT = " + str(upscale_amt))
            self.write("!UPSCALE_FACE_ENH = " + upscale_face)
        self.write('\n' + prompt)
        self.prompt_count += 1


    # cleanup and close prompt file
    def cleanup(self):
        self.f.close()

    # write specified text to prompt file
    def write(self, text):
        self.f.write(text + '\n')


# gallery html class
class Html:
    def __init__(self, html_file):
        self.html_file_name = html_file
        self.f = None
        self.init_html()

    # create the html file, populate it
    def init_html(self):
        self.f = open(self.html_file_name, 'w')
        self.write("<!DOCTYPE html>")
        self.write("<html>")
        self.write("<head>")
        self.write("  <title>AI Art Metadata Explorer</title>")
        self.write("  <link rel=\"stylesheet\" href=\"gallery.css\">")
        self.write("</head>")
        self.write("<body>")
        self.write("<div class=\"intro\">")
        self.write("Metadata gallery of images created with <a href=\"https://github.com/rbbrdckybk/ai-art-generator\" target=\"_blank\">AI Art Generator</a>.")
        self.write("</div>")
        self.write("<div class=\"flex-column\">")

    # add image data to html along with necessary formatting
    def add_image_section(self, dir, file, height, prompt, settings, initimg, initstr):
        ifn = initimg
        if '\\' in initimg:
            ifn = initimg.rsplit('\\', 1)[1]
        fullpath = dir + '\\' + file
        self.write("  <div class=\"flex-row\">")
        self.write("    <div>")
        self.write("      <a href=\"" + fullpath + "\">")
        self.write("        <img src=\"" + fullpath + "\" alt=\"" + file + "\" height=\"" + str(height) + "\">")
        self.write("      </a>")
        self.write("    </div>")
        self.write("    <div class=\"flex-info\">")
        self.write("      <div>")
        self.write("        " + prompt)
        self.write("      </div>")
        self.write("      <div class=\"bottom\">")
        self.write("        " + settings)
        if ifn != "":
            imgtxt = "<div><a href=\"" + initimg + "\">" + ifn + "</a> used as init image @ " + str(initstr) + " strength</div>"
            self.write("        " + imgtxt)
        self.write("      </div>")
        self.write("    </div>")
        self.write("  </div>")


    # cleanup and close html file
    def cleanup(self):
        self.write("</div>")
        self.write("</body>")
        self.write("</html>")
        self.f.close()

    # write specified text to html file
    def write(self, text):
        self.f.write(text + '\n')


# returns the text in string s
# that's between the first occurance of first and last search text
# returns an empty string if first or last don't appear in s
def find_between(s, first, last):
    text = s
    if first in text:
        text = s.split(first, 1)[1]
        if (last in text) or (" " not in text.strip()):
            if last in text:
                text = text.split(last, 1)[0]
                return text
            else:
                return text.strip()
        else:
            return ""
    else:
        return ""

# find the number closest
# to n and divisible by m
def closest_number(n, m) :
    q = int(n / m)

    # 1st possible
    n1 = m * q

    # 2nd possible
    if((n * m) > 0) :
        n2 = (m * (q + 1))
    else :
        n2 = (m * (q - 1))

    # n1 is the closest number
    if (abs(n - n1) < abs(n - n2)) :
        return n1

    # else n2
    return n2

# build the gallery .htm given a directory of images
def make_gallery(dir):
    print('\nStarting...')
    files = os.listdir(dir)
    file_count = 0
    file_metadata_count = 0
    html = Html('gallery.html')
    prompts = PromptFile('gallery_prompts.txt')

    for f in files:
        f = f.lower()
        file_ext = f[-4:]
        if (file_ext == ".jpg") or (file_ext == ".png"):
            file_count += 1
            full_path = dir + '\\' + f

            # read metadata from each image
            im = Image.open(full_path)
            exif = im.getexif()
            im_width, im_height = im.size
            im.close()

            # check for custom exif tags
            command = ""
            upscale_text = ""
            try:
                command = exif[0x9286]
            except KeyError as e:
                try:
                    command = exif[0x9c9c].decode('utf16')
                except KeyError as e:
                    print('   Couldn\'t find any metadata in ' + f + ', skipping...')


            if command != "":
                try:
                    upscale_text = exif[0x9c9d].decode('utf16')
                except KeyError as e:
                    pass

            # proceed if exif data found
            if command != "":
                file_metadata_count += 1
                prompt = ""
                width = ""
                height = ""
                steps = ""
                scale = ""
                upscale = ""

                if (command[0] == '"') or ("--prompt " in command):
                    if "--prompt " in command:
                        # old metadata format
                        prompt = command.split("--prompt \"", 1)[1]
                        prompt = prompt.split("\"", 1)[0]
                    else:
                        # new metadata format
                        prompt = command[1:].split("\"", 1)[0]

                    width = find_between(command, "--W ", " --")
                    height = find_between(command, "--H ", " --")
                    steps = find_between(command, "--ddim_steps ", " --")
                    scale = find_between(command, "--scale ", " --")
                    upscaled = find_between(upscale_text, " (upscaled ", ")")
                    initimg = find_between(command, "--init-img ", " --")
                    initstr = find_between(command, "--strength ", " --")

                    # width/height params not in metadata,
                    # infer from actual fize size and upscale factor
                    if width == "":
                        upfactor = 1
                        if upscaled != "":
                            upfactor = upscaled.split("x via", 1)[0]

                        width = float(im_width) / float(upfactor)
                        height = float(im_height) / float(upfactor)

                        if width % 64 != 0:
                            width = closest_number(width, 64)
                        if height % 64 != 0:
                            height = closest_number(height, 64)

                        width = int(width)
                        height = int(height)

                    upscale_use = "yes"
                    if upscaled == "":
                        upscaled = "no"
                        upscale_use = "no"

                    upscale_amt = "2"
                    upscale_face = "no"
                    if upscale_use == "yes":
                        upscale_amt = upscaled.split("x via", 1)[0]
                        if 'GFPGAN' in upscaled:
                            upscale_face = "yes"

                    settings = "width: " + str(width) + " | " \
                        + "height: " + str(height) + " | " \
                        + "steps: " + steps + " | " \
                        + "scale: " + scale + " | " \
                        + "upscaled: " + upscaled

                    cwd = ""
                    if initimg != "":
                        initfn = initimg.replace('\"', '').replace('/', '\\').replace('..\\', '')
                        cwd = os.getcwd().replace('\\utils', '')
                        cwd += '\\' + initfn
                        if '\\' in initfn:
                            initfn = initfn.rsplit('\\', 1)[1]

                    html.add_image_section(dir, f, 192, prompt, settings, cwd, initstr)
                    prompts.add_prompt_section(prompt, width, height, steps, scale, initimg, initstr, upscale_use, upscale_amt, upscale_face)

                else:
                    print('   Unexpected metadata format in ' + f + ', skipping...')



    print('Found ' + str(file_count) + ' images in ' + dir)
    print("Successfully read metadata from " + str(file_metadata_count) + " images.")
    print("Created gallery.html and gallery_prompts.txt in " + os.getcwd() + "\n")
    html.cleanup()
    prompts.cleanup()


# entry point
if __name__ == '__main__':
    if len(sys.argv) > 1:
        gallery_dir = sys.argv[1]
        if not os.path.exists(gallery_dir):
            print("\nThe specified path '" + gallery_dir + "' doesn't exist!")
            print("Please specify a valid directory containing images.")
            exit()
        else:
            make_gallery(gallery_dir)

    else:
        print("\nUsage: python metadata_gallery.py [directory containing images]")
        print("Example: python metadata_gallery.py \"c:\images\"")
        exit()