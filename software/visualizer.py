'''
Date: 27 Apr 2026
Author: Zhiheng Yang
This code is created for debugging and visualization only, not relevant to model training
'''
import cv2
import time
import serial
import struct
import numpy as np
from collections import deque

# serial config
PORT = '/dev/cu.usbserial-1401'
BAUD = 2000000

# binary config
HEADER = b'st'
buffer = b''
FORMAT = '<2sf512B'                                  # 2 (char number of head) + 1 (float angle) + 512 (2 * 256 pixel data from knee and foot)
FORMAT_LEN = struct.calcsize(FORMAT)                 # this confines one frame's length

# heatmap config
PIXEL_SIZE = 30                                      # define the side length of a single pixel in the heatmap
HEAT_THRESHOLD = 5
NOISE_SCALE = 10
NUM = 16                                             # define the side length of our square heatmap
pixel = []

# line chart config
WINDOW_LEN = 150                                     # the actual length of the window
WINDOW_WIDTH = 150                                   # the number of points within window
WINDOW_HEIGHT = 50                                   # the actual height of the window
WINDOW = deque([0.0] * WINDOW_WIDTH, maxlen=WINDOW_WIDTH)
ANGLE_THRESHOLD = 1
angle = 0.0

# flagging config
FLAG = False
FLAG_NUM = 30                                        # we'll use first 30 frame as base for calibration
FLAG_COUNT = 0
base_angle = 0.0                                     # create a float to store flag angle
base_pixel = np.zeros(512)                           # create a 512 zeros array to store flag pixel
base_angle_set = []
base_pixel_set = []

def processSerial(ser):
    global base_angle_set, base_pixel_set, base_angle, base_pixel, buffer, angle, pixel, FLAG, FLAG_NUM, FLAG_COUNT

    while ser.in_waiting > 0:                        # if there are any data that are waiting for received
        buffer += ser.read(ser.in_waiting)
        while len(buffer) >= FORMAT_LEN:             # try process buffer when possible
            header_idx = buffer.find(HEADER)
            if header_idx == -1:                     # no header, indicating a null data
                buffer = b''                         # throw these trash data
                break                                # shift to next loop to collect more data

            if header_idx > 0:                       # header isn't at the first position
                buffer = buffer[header_idx:]         # we only want data that start with header
                if len(buffer) < FORMAT_LEN:         # indicating incomplete data
                    break                            # shift to next loop to collect more data

            # now, out buffer begin with header with at least one complete frame
            frame = buffer[:FORMAT_LEN]              # cut one frame's data
            unpacked = struct.unpack(FORMAT, frame)  # we unpack this frame's data from binary format
            buffer = buffer[FORMAT_LEN:]             # shift to next frame
            if FLAG_COUNT < 30:
                base_angle_set.append(unpacked[1])
                base_pixel_set.append(unpacked[2:])
                FLAG_COUNT += 1
                print(f'Calibration: {FLAG_COUNT}/{FLAG_NUM}', end='\r')
                return                               # brutally jump out of the function

            print('Calibration complete')
            FLAG = True                              # if code can execute up to this point, then we can be confident that flagging is complete
            base_angle = np.median(base_angle_set)
            base_pixel = np.median(np.array(base_pixel_set), axis=0)

            angle = unpacked[1] - base_angle         # cuz frame[0] is the header
            angle = np.clip(angle, 0, 180)

            # the following data are 512 pixels' pressure, and we don't need to separate knee and foot
            pixel = np.array(unpacked[2:]) - base_pixel
            pixel = np.clip(pixel, 0, 255)

            if np.max(pixel) < HEAT_THRESHOLD:
                pixel *= NOISE_SCALE                 # amplifying peaceful event for visual-friendly purpose

            WINDOW.append(angle)                     # add this frame's angle to deque


def line_chart_plotter():
    point_coordinates = []                           # this list store values of every angle within the window
    canvas = np.zeros(shape=(WINDOW_HEIGHT, WINDOW_LEN, 3), dtype=np.uint8)  # height, width, RGB

    if len(WINDOW) < 2:
        return canvas                                # return directly since we cannot plot a single dot or empty
    for i, val in enumerate(WINDOW):                 # grab both index and angle inside the window
        cv2.putText(canvas,
                    f'Knee angle: {val:.2f} degrees',
                    (20, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (255, 255, 255),           # set background as black
                    2)
        x = i * (WINDOW_LEN / WINDOW_WIDTH)          # distribute every dot uniformly
        y = WINDOW_HEIGHT * (1 - val / 180.0)        # cuz the y-coordinate at top is 0, so we need to flip it
        point_coordinates.append((x, y))             # add tuple containing x, y

    for i in range(len(point_coordinates) - 1):
        # connect every adjacent dots by using yellow lines with thick 2
        cv2.line(canvas, point_coordinates[i], point_coordinates[i+1], (0, 255, 255), 2)

    time.sleep(0.01)                                 # give CPU a short break, increasing robustness
    cv2.imshow('Knee angle line chart (live)', canvas)


def heatmap_painter():
    # transform num list to 16 * 16 grid by 0~255 int, corresponding with RGB scale
    knee_matrix = np.array(pixel[:256]).astype(np.uint8).reshape(16, 16)
    foot_matrix = np.array(pixel[256:]).astype(np.uint8).reshape(16, 16)
    knee_heatmap = cv2.resize(knee_matrix,
        (NUM * PIXEL_SIZE, NUM * PIXEL_SIZE),  # define the heatmap's side length under the pixel dimension
        interpolation=cv2.INTER_NEAREST)             # Fill center color to all the grid to make pure color grids
    foot_heatmap = cv2.resize(foot_matrix,
        (NUM * PIXEL_SIZE, NUM * PIXEL_SIZE),
        interpolation=cv2.INTER_NEAREST)

    knee_colormap = cv2.applyColorMap(knee_heatmap, cv2.COLORMAP_JET)
    foot_colormap = cv2.applyColorMap(foot_heatmap, cv2.COLORMAP_JET)

    time.sleep(0.01)
    cv2.imshow('Knee Heatmap (pixelated)', knee_colormap)
    cv2.imshow('Feet Heatmap (pixelated)', foot_colormap)


if __name__ == '__main__':
    serial_data = serial.Serial(PORT, BAUD, timeout=0.1)
    try:
        while True:
            processSerial(serial_data)
            if FLAG:                                 # the following will proceed only when flag is complete
                line_chart_plotter()
                heatmap_painter()

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    except Exception as e:
        print(f'Trace back (most recent call last): {e}')
    finally:                                         # execute 100% regardless whether previous error exist or not
        serial_data.close()
        cv2.destroyAllWindows()
