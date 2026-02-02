import cv2
import numpy as np
import os
from datetime import datetime

class VideoKeyframeExtractor:
    def __init__(self, threshold=3000000, min_interval=10):
        """
        初始化视频关键帧提取器
        :param threshold: 帧差异阈值，超过此值则视为关键帧
        :param min_interval: 关键帧之间的最小间隔（帧数）
        """
        self.threshold = threshold
        self.min_interval = min_interval
        self.prev_frame = None
        self.last_keyframe_idx = -min_interval
        self.keyframes = []
        
    def process_video(self, video_path, output_dir="keyframes"):
        """
        处理视频并提取关键帧
        :param video_path: 视频文件路径
        :param output_dir: 关键帧保存目录
        :return: 提取的关键帧列表
        """
        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)
        
        # 打开视频文件
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            print(f"无法打开视频文件: {video_path}")
            return []
            
        frame_count = 0
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break  # 视频处理完毕
                
            # 转换为灰度图以减少计算量
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # 第一帧默认为关键帧
            if self.prev_frame is None:
                self._save_keyframe(frame, frame_count, output_dir)
                self.prev_frame = gray
                frame_count += 1
                continue
                
            # 计算当前帧与前一帧的差异
            frame_diff = cv2.absdiff(gray, self.prev_frame)
            diff_value = np.sum(frame_diff)
            
            # 检查是否满足关键帧条件
            if diff_value > self.threshold and (frame_count - self.last_keyframe_idx) > self.min_interval:
                self._save_keyframe(frame, frame_count, output_dir)
                self.prev_frame = gray  # 更新前一帧为当前关键帧
                self.last_keyframe_idx = frame_count
                
            frame_count += 1
            
        cap.release()
        print(f"视频处理完成，共提取 {len(self.keyframes)} 个关键帧")
        return self.keyframes
        
    def _save_keyframe(self, frame, frame_idx, output_dir):
        """保存关键帧到文件"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"keyframe_{timestamp}_frame_{frame_idx}.jpg"
        filepath = os.path.join(output_dir, filename)
        
        cv2.imwrite(filepath, frame)
        self.keyframes.append({
            "frame_index": frame_idx,
            "file_path": filepath,
            "timestamp": timestamp
        })
        
        print(f"保存关键帧: {filepath} (帧索引: {frame_idx})")

if __name__ == "__main__":
    # 示例用法
    video_path = "input_video.mp4"  # 替换为你的视频文件路径
    output_directory = "extracted_keyframes"
    
    # 初始化提取器，可根据需要调整阈值和最小间隔
    extractor = VideoKeyframeExtractor(threshold=5000000, min_interval=15)
    
    # 处理视频
    keyframes = extractor.process_video(video_path, output_directory)
    
    # 打印提取结果
    if keyframes:
        print("\n提取的关键帧信息:")
        for idx, kf in enumerate(keyframes):
            print(f"{idx+1}. 帧索引: {kf['frame_index']}, 文件: {kf['file_path']}")
