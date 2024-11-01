import argparse
import cv2
import os
from basicsr.archs.rrdbnet_arch import RRDBNet
from basicsr.utils.download_util import load_file_from_url
from super_res.Real_ESRGAN.realesrgan import RealESRGANer
from super_res.Real_ESRGAN.realesrgan.archs.srvgg_arch import SRVGGNetCompact
from tqdm import tqdm


# 如果需要用到 GFPGAN，请确保已安装并导入相应的模块
# from gfpgan import GFPGANer  # 注意：需要安装GFPGAN库


class RealESRGANProcessor:
    def __init__(self, model_name='realesr-general-x4v3', model_path=None, denoise_strength=0.5, outscale=4,
                 tile=0, tile_pad=10, pre_pad=0, face_enhance=False, fp32=False, alpha_upsampler='realesrgan',
                 ext='auto', gpu_id=None):
        self.model_name = model_name.split('.')[0]
        self.model_path = model_path
        self.denoise_strength = denoise_strength
        self.outscale = outscale
        self.tile = tile
        self.tile_pad = tile_pad
        self.pre_pad = pre_pad
        self.face_enhance = face_enhance
        self.fp32 = fp32
        self.alpha_upsampler = alpha_upsampler
        self.ext = ext
        self.gpu_id = gpu_id

        self.model, self.netscale, self.file_url = self._load_model()
        self.upsampler = self._init_upsampler()

        if self.face_enhance:
            # 注意：需要确保GFPGAN库已安装并可用
            # self.face_enhancer = self._init_face_enhancer()
            pass  # 暂时禁用，因为需要额外的安装步骤

    def _load_model(self):
        if self.model_name == 'RealESRGAN_x4plus':
            model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=4)
            netscale = 4
            file_url = ['https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth']
        elif self.model_name == 'RealESRNet_x4plus':
            model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=4)
            netscale = 4
            file_url = ['https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.1/RealESRNet_x4plus.pth']
        elif self.model_name == 'RealESRGAN_x4plus_anime_6B':
            model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=6, num_grow_ch=32, scale=4)
            netscale = 4
            file_url = [
                'https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.2.4/RealESRGAN_x4plus_anime_6B.pth']
        elif self.model_name == 'RealESRGAN_x2plus':
            model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=2)
            netscale = 2
            file_url = ['https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.1/RealESRGAN_x2plus.pth']
        elif self.model_name == 'realesr-animevideov3':
            model = SRVGGNetCompact(num_in_ch=3, num_out_ch=3, num_feat=64, num_conv=16, upscale=4, act_type='prelu')
            netscale = 4
            file_url = ['https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-animevideov3.pth']
        elif self.model_name == 'realesr-general-x4v3':
            model = SRVGGNetCompact(num_in_ch=3, num_out_ch=3, num_feat=64, num_conv=32, upscale=4, act_type='prelu')
            netscale = 4
            file_url = [
                'https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-general-wdn-x4v3.pth',
                'https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-general-x4v3.pth'
            ]
        else:
            raise ValueError(f"Unknown model name: {self.model_name}")

        if self.model_path is None:
            ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
            model_dir = os.path.join(ROOT_DIR, 'weights')
            os.makedirs(model_dir, exist_ok=True)
            self.model_path = os.path.join(model_dir, self.model_name + '.pth')
            if not os.path.isfile(self.model_path):
                self.model_path = load_file_from_url(
                    url=file_url[0], model_dir=model_dir, progress=True, file_name=None)
                if self.model_name == 'realesr-general-x4v3' and self.denoise_strength != 1:
                    wdn_model_path = self.model_path.replace('realesr-general-x4v3', 'realesr-general-wdn-x4v3')
                    self.model_path = [self.model_path, load_file_from_url(
                        url=file_url[1], model_dir=model_dir, progress=True, file_name=None) if os.path.basename(
                        file_url[1]) else wdn_model_path]
        else:
            self.model_path = [self.model_path] if isinstance(self.model_path, str) else self.model_path

        dni_weight = [self.denoise_strength,
                      1 - self.denoise_strength] if self.model_name == 'realesr-general-x4v3' and self.denoise_strength != 1 else None

        return model, netscale, file_url

    def _init_upsampler(self):
        return RealESRGANer(
            scale=self.netscale,
            model_path=self.model_path,
            dni_weight=[self.denoise_strength,
                        1 - self.denoise_strength] if self.model_name == 'realesr-general-x4v3' and self.denoise_strength != 1 else None,
            model=self.model,
            tile=self.tile,
            tile_pad=self.tile_pad,
            pre_pad=self.pre_pad,
            half=not self.fp32,
            gpu_id=self.gpu_id
        )

        # def _init_face_enhancer(self):

    #     return GFPGANer(
    #         model_path='https://github.com/TencentARC/GFPGAN/releases/download/v1.3.0/GFPGANv1.3.pth',
    #         upscale=self.outscale,
    #         arch='clean',
    #         channel_multiplier=2,
    #         bg_upsampler=self.upsampler
    #     )

    def enhance_image(self, input_image):
        output, _ = self.upsampler.enhance(input_image, outscale=self.outscale)
        return output

    # 使用示例


if __name__ == '__main__':


    # input_image = cv2.imread('image_01.jpg')
    # output_image = processer.enhance_image(input_image=input_image)
    # cv2.imwrite('image_01_out.jpg', output_image)

    images_path = r'E:\dek\Haptic artificial intelligence development\6_classification_pre-tasks\save'
    video_output_path = r'E:\dek\Haptic artificial intelligence development\6_classification_pre-tasks\vedio'

    # 合成帧为MP4
    frame_rate = 20  # 视频帧率，可以根据需要调整
    frame_size = (256, 256)  # 假设所有图像大小相同
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')  # 视频编码格式

    # super_resolution_image = Super_Resolution_image()
    processer = RealESRGANProcessor()

    for i, cls in enumerate(os.listdir(images_path)):
        cls_path = fr"{images_path}\{cls}"

        if os.path.isdir(cls_path):
            image_files = sorted([f for f in os.listdir(cls_path) if f.endswith('.jpg')])

            # 创建视频写入对象
            video_path = fr"{video_output_path}\{cls}_new.mp4"
            out = cv2.VideoWriter(video_path, fourcc, frame_rate, frame_size)

            for image_file in tqdm(image_files):
                img_path = fr"{cls_path}\{image_file}"
                # 使用OpenCV读取图像
                frame = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)  # 假设图像是灰度图
                '''别问为什么，不加这行会出现写入文件失败'''
                frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
                # 超分辨率处理
                frame = processer.enhance_image(frame)
                # print(frame.shape)
                # 检查图像是否成功加载
                if frame is not None:
                    # 写入视频文件
                    out.write(frame)

                    cv2.imshow('frame', frame)  # 显示帧
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        break

                else:
                    print(f"警告：无法加载图像 {img_path}")

            # 释放视频写入对象
            out.release()
            print(f"类别-{cls}的视频文件已创建")