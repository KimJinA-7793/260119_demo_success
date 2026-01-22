import time
import cv2
import os
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from std_msgs.msg import Float32MultiArray
from cv_bridge import CvBridge

# 당신이 준 coords_flat (len=20, N=4)
COORDS_FLAT = [
    0, 50.05782977134092, -9.195203233329103, 12.764014014052961, 90.0,
    1, 57.129640204305964,  7.902029444306972,  9.246551378991981, 98.1301040649414,
    2, 60.608172970207264, -16.755234726076147,  6.094565919785651, 81.86988067626953,
    3, 65.41322804722721,  -5.643819675964139, 20.015627048587902, 0.0
]

# 사진 파일 경로를 당신 PC 경로로 바꾸세요!
IMAGE_PATH = os.path.expanduser("~/0113/test_images/sample_01.jpg")


class OneShotPub(Node):
    def __init__(self):
        super().__init__("one_shot_pub")
        self.bridge = CvBridge()
        self.pub_coords = self.create_publisher(Float32MultiArray, "/perception/waste_coordinates", 10)
        self.pub_img = self.create_publisher(Image, "/perception/waste_image_raw", 10)

    def run(self):
        # 1) coords 먼저 publish (Judge 게이트 통과를 위해 순서가 중요)
        if len(COORDS_FLAT) % 5 != 0:
            raise ValueError(f"coords length must be 5N. got len={len(COORDS_FLAT)}")

        msg_c = Float32MultiArray()
        msg_c.data = [float(v) for v in COORDS_FLAT]  # tmp_id(int) 포함 전부 float로 강제

        self.pub_coords.publish(msg_c)
        self.get_logger().info(f"published coords len={len(COORDS_FLAT)} (N={len(COORDS_FLAT)//5})")

        # 2) 20ms 후 image publish (coords가 먼저 들어가도록)
        time.sleep(0.02)

        bgr = cv2.imread(IMAGE_PATH, cv2.IMREAD_COLOR)
        if bgr is None:
            raise RuntimeError(f"cv2.imread failed: {IMAGE_PATH}")

        msg_i = self.bridge.cv2_to_imgmsg(bgr, encoding="bgr8")
        self.pub_img.publish(msg_i)
        self.get_logger().info(f"published image shape={bgr.shape}, encoding=bgr8")


def main():
    rclpy.init()
    node = OneShotPub()

    # 구독자 매칭 시간(처음 메시지 유실 방지): 1초 미만
    for _ in range(10):
        rclpy.spin_once(node, timeout_sec=0.1)

    node.run()

    # 메시지 flush: 0.5초
    t0 = time.time()
    while time.time() - t0 < 0.5:
        rclpy.spin_once(node, timeout_sec=0.1)

    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()