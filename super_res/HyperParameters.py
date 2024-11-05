'''
超参数和调用模块
'''
# 文件Real_ESRGAN_master.inference_realesrgan_class 由源代码修改而成，添加了类结构，提升调用效率
from super_res.Real_ESRGAN.inference_realesrgan_class import *
import cv2
import time
from tqdm import tqdm
'''
通过类实例对象RealESRGANProcessor()调用，输入输出皆为numpy数组
'''

if __name__ == '__main__':
    # 示例使用-单图
    # 为了保证多次调用的速率，请实例化类后 保持此后的多次调用都使用实例方法processer.enhance_image进行超分
    processer = RealESRGANProcessor()


    input_image = cv2.imread('image_01.jpg')

    # 第一次调用会内部初始化，耗时略长
    output_image_first = processer.enhance_image(input_image=input_image)

    # 之后的调用时间约在7~10ms/张
    for i in range(10):
        time1 = time.time()
        output_image = processer.enhance_image(input_image=input_image)
        time2 = time.time()
        print(f'耗时{time2-time1}s')

    # 输出的numpy数组形状为(256, 256, 3) (3通道)
    # print(output_image.shape)

    cv2.imwrite('image_01_out.jpg', output_image)




















