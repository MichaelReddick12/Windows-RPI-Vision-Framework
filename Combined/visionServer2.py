import cv2
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from threading import Thread
import imutils
import sys
import socket
import numpy as np
import time
from operator import itemgetter
import math

# construct the argument parse and parse the arguments
# v4l2-ctl --set-ctrl brightness=25
#cmd commands:
#source ~/.profile
#workon cv
#python '/home/pi/Documents/PythonProjects/pyImage.py' or wherever u have pyImage saved

def contourArea(contours):
    area = []
    for i in range(0,len(contours)):
       area.append([cv2.contourArea(contours[i]),i])

    area.sort(key=itemgetter(1))

    return area[len(area) - 1]

def widthDistanceCalc(x):
    return -0.0003 * math.pow(x, 3) + 0.0881 * x * x - 10.336 * x + 553.9

def tanDistance(x):
    return ((0.333) * 480) / 2 * x * np.tan(14.86 * np.pi/180)

class CamHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        print(self.path)
        if self.path.endswith('/stream.mjpg'):
            self.send_response(20)
            self.send_header('Content-type', 'multipart/x-mixed-replace; boundary=--jpgboundary')
            self.end_headers()
            while True:
                try:

                    if(frame != None):
                        pass
                    r, buf = cv2.imencode(".jpg", frame)
                    self.wfile.write("--jpgboundary\r\n".encode())
                    self.end_headers()
                    self.wfile.write(bytearray(buf))
                except KeyboardInterrupt:
                    break
            return

        if self.path.endswith('.html') or self.path == "/":
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write('<html><head></head><body>')
            self.wfile.write('<img src="http://localhost:5810/stream.mjpg" height="480px" width="640px"/>')
            self.wfile.write('</body></html>')
            return

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle requests in a separate thread."""


class WebcamVideoStream:
    def __init__(self, src=0):

        self.stream = cv2.VideoCapture(src)

        (self.grabbed, self.frame) = self.stream.read()

        self.stopped = False

    def start(self):

        Thread(target=self.update, args=()).start()
        return self

    def update(self):
        while True:

            if self.stopped:
                self.stream.release()
                return

            (self.grabbed, self.frame) = self.stream.read()

    def read(self):
        return self.frame

    def stop(self):
        self.stopped = True


def realmain():
    global frame

    font = cv2.FONT_HERSHEY_SIMPLEX

    lower_green = (55, 140, 110)
    upper_green = (90, 256, 256)

    UDP_PORT = 5800
    UDP_RECEIVE_PORT = 5801

    BUFFER_SIZE = 1024
    UDP_IP = '10.54.65.79'
    UDP_COMP_IP = '10.54.65.88'

    sendsock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    receivesock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    receivesock.bind((UDP_COMP_IP, UDP_RECEIVE_PORT))

    ip = ''

    try:
        cap = WebcamVideoStream(src=0).start()
        capGear = WebcamVideoStream(src=1).start()

        server = ThreadedHTTPServer((ip, 9090), CamHandler)
        print("starting server ")
        target = Thread(target=server.serve_forever,args=())

        i = 0
        while True:

            img = cap.read()
            t = imutils.resize(img, width=640,height=480)

            img2 = cv2.GaussianBlur(t, (5, 5), 0)
            hsv = cv2.cvtColor(img2, cv2.COLOR_BGR2HSV)
            # construct a mask for the color "green", then perform
            # a series of dilations and erosions to remove any small
            # blobs left in the mask
            mask = cv2.inRange(hsv, lower_green, upper_green)
            edged = cv2.Canny(mask, 35, 125)

            # find contours in the mask and initialize the current
            # (x, y) center of the ball
            im2, cnts, hierarchy = cv2.findContours(edged.copy(), cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)

            if(len(cnts) >=1):
                area, place = contourArea(cnts)

                if(area >= 100):
                    maxc = cnts[place]


                    rect = cv2.minAreaRect(maxc)
                    box = cv2.boxPoints(rect)
                    box = np.int0(box)
                    cv2.drawContours(t, [box], 0, (0, 0, 255), 2)

                    M = cv2.moments(maxc)
                    cx = int(M['m10'] / M['m00'])  # Center of MASS Coordinates
                    cy = int(M['m01'] / M['m00'])
                    rect = cv2.minAreaRect(maxc)
                    height = rect[1][0]
                    width = rect[1][1]

                    widthreal = max(width,height)
                    heightreal = min(width, height)
                    distance = widthDistanceCalc(widthreal)
                    otherdistance = tanDistance(heightreal)

                    cv2.putText(t, '%s in. ' % (round(distance,2)), (10, 400), font, 0.5, (0, 0, 255), 1)

                    sendsock.sendto(('Y ' + str(cx) + ' ' + str(cy) + ' ' + "{0:.2f}".format(heightreal) + ' ' + "{0:.2f}".format(widthreal)).encode(),(UDP_IP, UDP_PORT))
            else:
                sendsock.sendto('N'.encode(), (UDP_IP, UDP_PORT))

            if(receivesock.recvfrom(BUFFER_SIZE).decode() == '1'):
                frame = t
            elif(receivesock.recvfrom(BUFFER_SIZE).decode() == '2'):
                frame = imutils.resize(capGear.read(),width=640,height=480)
            else:
                frame = imutils.resize(capGear.read(),width=640,height=480)

            if (i == 0):
                target.start()
            i += 1

    except KeyboardInterrupt:
        cap.stop()
        capGear.stop()
        target.join()
        sys.exit()

if __name__ == '__main__':
    realmain()