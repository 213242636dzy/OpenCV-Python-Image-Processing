import cv2
import numpy as np
import matplotlib.pyplot as plt

class VideoStabilizer:
    def __init__(self, smoothing_window=30):
        """
        初始化视频稳像器
        :param smoothing_window: 平滑窗口大小，控制稳像效果，值越大画面越平稳但可能有延迟感
        """
        self.smoothing_window = smoothing_window
        self.prev_gray = None
        self.transforms = []  # 存储帧间变换
        self.original_frames = []  # 存储原始帧
        self.stabilized_frames = []  # 存储稳定后的帧
        
    def capture_video(self, input_path=None):
        """
        捕获视频，可以是摄像头输入或视频文件
        :param input_path: 视频文件路径，None则使用摄像头
        :return: 视频捕获对象
        """
        if input_path:
            cap = cv2.VideoCapture(input_path)
        else:
            cap = cv2.VideoCapture(0)  # 使用默认摄像头
            
        if not cap.isOpened():
            raise Exception("无法打开视频源")
            
        return cap
    
    def get_transform(self, frame):
        """
        计算当前帧与前一帧的变换矩阵
        :param frame: 当前帧
        :return: 变换矩阵
        """
        # 转换为灰度图
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # 如果是第一帧，初始化前一帧的灰度图
        if self.prev_gray is None:
            self.prev_gray = gray
            return np.eye(3, dtype=np.float32)
        
        # 使用ORB特征检测器和描述符
        orb = cv2.ORB_create(500)
        prev_keypoints, prev_descriptors = orb.detectAndCompute(self.prev_gray, None)
        curr_keypoints, curr_descriptors = orb.detectAndCompute(gray, None)
        
        # 匹配特征点
        matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
        matches = matcher.match(prev_descriptors, curr_descriptors)
        
        # 按匹配距离排序并取前N个最佳匹配
        matches = sorted(matches, key=lambda x: x.distance)[:100]
        
        # 提取匹配点的坐标
        prev_points = np.float32([prev_keypoints[m.queryIdx].pt for m in matches]).reshape(-1, 1, 2)
        curr_points = np.float32([curr_keypoints[m.trainIdx].pt for m in matches]).reshape(-1, 1, 2)
        
        # 计算变换矩阵 (平移 + 旋转 + 缩放)
        transform, _ = cv2.findTransformECC(prev_gray, gray, None, cv2.MOTION_AFFINE)
        
        # 将变换矩阵扩展为3x3以支持矩阵乘法
        full_transform = np.eye(3, dtype=np.float32)
        full_transform[:2, :3] = transform
        
        # 更新前一帧的灰度图
        self.prev_gray = gray
        
        return full_transform
    
    def smooth_transforms(self):
        """平滑变换矩阵，减少抖动"""
        # 计算累积变换
        cumulative_transform = np.eye(3, dtype=np.float32)
        cumulative_transforms = [cumulative_transform]
        
        for transform in self.transforms:
            cumulative_transform = cumulative_transform @ transform
            cumulative_transforms.append(cumulative_transform)
        
        # 提取平移和旋转角度
        tx = [t[0, 2] for t in cumulative_transforms]
        ty = [t[1, 2] for t in cumulative_transforms]
        rx = [np.arctan2(t[1, 0], t[0, 0]) for t in cumulative_transforms]
        
        # 使用滑动窗口平均法平滑变换
        smoothed_tx = self.moving_average(tx)
        smoothed_ty = self.moving_average(ty)
        smoothed_rx = self.moving_average(rx)
        
        # 计算平滑后的变换矩阵
        smoothed_transforms = []
        for i in range(1, len(cumulative_transforms)):
            # 计算平滑变换与原始变换的差值
            diff_tx = smoothed_tx[i] - tx[i]
            diff_ty = smoothed_ty[i] - ty[i]
            diff_rx = smoothed_rx[i] - rx[i]
            
            # 创建旋转矩阵
            rot = np.array([
                [np.cos(diff_rx), -np.sin(diff_rx), diff_tx],
                [np.sin(diff_rx), np.cos(diff_rx), diff_ty],
                [0, 0, 1]
            ], dtype=np.float32)
            
            # 计算最终的平滑变换矩阵
            smoothed_transform = rot @ np.linalg.inv(cumulative_transforms[i])
            smoothed_transforms.append(smoothed_transform)
        
        return smoothed_transforms
    
    def moving_average(self, values):
        """滑动窗口平均滤波"""
        smoothed = []
        window = min(self.smoothing_window, len(values))
        
        for i in range(len(values)):
            start = max(0, i - window + 1)
            smoothed_val = np.mean(values[start:i+1])
            smoothed.append(smoothed_val)
            
        return smoothed
    
    def stabilize_frame(self, frame, transform):
        """应用变换矩阵稳定单帧"""
        h, w = frame.shape[:2]
        # 应用变换
        stabilized = cv2.warpAffine(frame, transform[:2, :3], (w, h), 
                                   flags=cv2.INTER_LINEAR + cv2.WARP_INVERSE_MAP)
        return stabilized
    
    def process_video(self, input_path=None, output_path="stabilized_video.mp4"):
        """
        处理视频并输出稳定后的视频
        :param input_path: 输入视频路径，None则使用摄像头
        :param output_path: 输出视频路径
        """
        cap = self.capture_video(input_path)
        
        # 获取视频属性
        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        # 定义视频编码器和创建VideoWriter对象
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
        
        print("正在处理视频...")
        
        # 读取第一帧
        ret, prev_frame = cap.read()
        if not ret:
            raise Exception("无法读取视频帧")
            
        self.original_frames.append(prev_frame)
        self.prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
        
        # 读取并处理后续帧
        while True:
            ret, frame = cap.read()
            if not ret:
                break
                
            self.original_frames.append(frame)
            
            # 计算当前帧与前一帧的变换
            transform = self.get_transform(frame)
            self.transforms.append(transform)
            
            # 显示处理进度
            if len(self.transforms) % 10 == 0:
                print(f"已处理 {len(self.transforms)} 帧")
        
        print("正在平滑处理...")
        
        # 平滑变换
        smoothed_transforms = self.smooth_transforms()
        
        print("正在生成稳定视频...")
        
        # 应用平滑变换到每一帧
        for i, transform in enumerate(smoothed_transforms):
            stabilized = self.stabilize_frame(self.original_frames[i], transform)
            self.stabilized_frames.append(stabilized)
            out.write(stabilized)
            
            # 显示稳定前后的对比
            combined = np.hstack((self.original_frames[i], stabilized))
            cv2.imshow('Original vs Stabilized', cv2.resize(combined, (int(width*1.5), int(height*0.75))))
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        
        # 释放资源
        cap.release()
        out.release()
        cv2.destroyAllWindows()
        
        print(f"稳定后的视频已保存至 {output_path}")
        
        # 绘制变换曲线
        self.plot_transforms()
    
    def plot_transforms(self):
        """绘制变换参数曲线，展示稳像效果"""
        if not self.transforms:
            return
            
        # 计算累积变换
        cumulative_transform = np.eye(3, dtype=np.float32)
        tx, ty, rx = [], [], []
        
        tx.append(0)
        ty.append(0)
        rx.append(0)
        
        for transform in self.transforms:
            cumulative_transform = cumulative_transform @ transform
            tx.append(cumulative_transform[0, 2])
            ty.append(cumulative_transform[1, 2])
            rx.append(np.arctan2(cumulative_transform[1, 0], cumulative_transform[0, 0]))
        
        # 计算平滑后的变换
        smoothed_tx = self.moving_average(tx)
        smoothed_ty = self.moving_average(ty)
        smoothed_rx = self.moving_average(rx)
        
        # 绘制曲线
        plt.figure(figsize=(15, 10))
        
        plt.subplot(311)
        plt.plot(tx, label='原始X方向平移')
        plt.plot(smoothed_tx, label='平滑后X方向平移')
        plt.title('X方向平移')
        plt.legend()
        
        plt.subplot(312)
        plt.plot(ty, label='原始Y方向平移')
        plt.plot(smoothed_ty, label='平滑后Y方向平移')
        plt.title('Y方向平移')
        plt.legend()
        
        plt.subplot(313)
        plt.plot(rx, label='原始旋转角度')
        plt.plot(smoothed_rx, label='平滑后旋转角度')
        plt.title('旋转角度')
        plt.legend()
        
        plt.tight_layout()
        plt.show()

if __name__ == "__main__":
    # 创建稳像器实例，调整平滑窗口大小控制效果
    stabilizer = VideoStabilizer(smoothing_window=30)
    
    # 处理视频，可以是视频文件路径或None(使用摄像头)
    # stabilizer.process_video(input_path="shaky_video.mp4", output_path="stabilized_output.mp4")
    stabilizer.process_video(input_path=None, output_path="stabilized_from_camera.mp4")
