import numpy as np
import serial
import threading
import cv2
from collections import deque

# ===================== 配置参数 =====================
PORT = '/dev/cu.usbserial-140'  # macOS通常是 /dev/cu.usbserial-xxx
BAUD = 2000000
ROW_COUNT = 16
COLUMN_COUNT = 16
THRESHOLD = 5  # 基础噪声阈值
NOISE_SCALE = 60  # 归一化比例因子

# 窗口设置
HEATMAP_SCALE = 30  # 放大倍数
MAX_PLOT_POINTS = 100

# ===================== 全局变量 =====================
# 存储当前正在构建的 16x16 矩阵
raw_matrix = np.zeros((ROW_COUNT, COLUMN_COUNT))
# 存储处理后用于显示的数据
contact_data_norm = np.zeros((ROW_COUNT, COLUMN_COUNT))
# 标定用
calibration_buffer = []
calibrated_median = np.zeros((ROW_COUNT, COLUMN_COUNT))
is_calibrated = False


def readThread(serDev):
    global raw_matrix, contact_data_norm, is_calibrated, calibrated_median, calibration_buffer

    serDev.flushInput()
    line_count = 0

    while True:
        if serDev.in_waiting > 0:
            try:
                # 读取一行，例如 "R0:12,13,44..."
                raw_line = serDev.readline().decode('utf-8').strip()
                if not raw_line or ":" not in raw_line:
                    continue

                # 1. 解析行号和数据
                parts = raw_line.split(":")
                row_idx = int(parts[0].replace("R", ""))  # 提取数字行号
                vals = [int(v) for v in parts[1].split(",")]  # 提取16个数据

                if len(vals) == COLUMN_COUNT:
                    raw_matrix[row_idx] = vals

                    # 2. 如果收到最后一行 (R15)，说明一帧扫描完成
                    if row_idx == ROW_COUNT - 1:
                        process_frame()
            except Exception as e:
                print(f"数据解析错误: {e}")
                continue


def process_frame():
    global is_calibrated, calibrated_median, calibration_buffer, contact_data_norm

    current_frame = raw_matrix.copy()

    # 3. 自动标定逻辑 (前30帧取中值)
    if not is_calibrated:
        calibration_buffer.append(current_frame)
        if len(calibration_buffer) >= 30:
            calibrated_median = np.median(np.array(calibration_buffer), axis=0)
            is_calibrated = True
            print(">>> 标定成功！传感器已就绪")
    else:
        # 4. 去除基准噪声并归一化
        # 原始值 - 背景中值 - 阈值
        processed = current_frame - calibrated_median - THRESHOLD
        processed = np.clip(processed, 0, 255)  # 限制在正数范围

        # 归一化逻辑
        max_val = np.max(processed)
        if max_val < THRESHOLD:
            contact_data_norm = processed / NOISE_SCALE
        else:
            contact_data_norm = processed / max_val


if __name__ == '__main__':
    try:
        serDev = serial.Serial(PORT, BAUD, timeout=1)
        print(f"成功连接到端口: {PORT}")
    except:
        print(f"无法打开端口 {PORT}，请检查设备连接或权限。")
        exit()

    serialThread = threading.Thread(target=readThread, args=(serDev,))
    serialThread.daemon = True
    serialThread.start()

    cv2.namedWindow("ESP-NOW Matrix Heatmap", cv2.WINDOW_NORMAL)

    while True:
        if is_calibrated:
            # 将 0-1 的浮点矩阵转为 0-255 的图像
            heatmap_img = (contact_data_norm * 255).astype(np.uint8)

            # 放大 (INTER_NEAREST 保持颗粒感)
            display_img = cv2.resize(heatmap_img,
                                     (COLUMN_COUNT * HEATMAP_SCALE, ROW_COUNT * HEATMAP_SCALE),
                                     interpolation=cv2.INTER_NEAREST)

            # 应用伪彩色 (JET色图：红热蓝冷)
            color_map = cv2.applyColorMap(display_img, cv2.COLORMAP_JET)

            # 添加文字提示
            cv2.putText(color_map, "Press 'Q' to Exit", (10, 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

            cv2.imshow("ESP-NOW Matrix Heatmap", color_map)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    serDev.close()
    cv2.destroyAllWindows()
