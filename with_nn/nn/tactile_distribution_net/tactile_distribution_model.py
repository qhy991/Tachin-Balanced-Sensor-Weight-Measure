import tensorflow as tf
import os
import json
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
tf.compat.v1.logging.set_verbosity(tf.compat.v1.logging.ERROR)

MASK_THRESHOLD = 1.

EPS = tf.keras.backend.epsilon()


def clip_0(t: tf.Tensor):
    return tf.keras.backend.clip(t, EPS, None)


def clip_0_1(t: tf.Tensor):
    return tf.keras.backend.clip(t, EPS, 1 - EPS)


class DistributionToMaterialType(tf.keras.Model):

    def __init__(self, save_folder, num_class,
                 base_filter_count=64, residual_unit_repetition=2, dropout=0.2,
                 base_learn_rate=0.001, learn_rate_decay=0.1):
        super().__init__()
        self.num_class = num_class
        self.save_folder = save_folder
        self.base_filter_count = base_filter_count
        self.residual_unit_repetition = residual_unit_repetition
        self.dropout = dropout
        self.base_learn_rate = base_learn_rate
        self.learn_rate_decay = learn_rate_decay
        #
        self.size_down_rate = 4
        #
        self.mapping = MappingModel(base_filter_count=base_filter_count,
                                    residual_unit_repetition=residual_unit_repetition,
                                    dropout=dropout)
        self.out_class = tf.keras.layers.Dense(num_class)
        self.smax = tf.keras.layers.Softmax()
        self.pooling_mask = tf.keras.layers.AveragePooling2D(pool_size=self.size_down_rate)
        # 标定

    def get_mask(self, x):
        mask = clip_0(-tf.keras.backend.exp(-self.pooling_mask(x) / MASK_THRESHOLD) + 1.)

        return mask

    def call(self, x, training=None, mask=None):
        x = tf.expand_dims(x, -1)
        mask = self.get_mask(x)
        x = self.mapping(x)
        x = self.out_class(x)
        x = self.smax(tf.reduce_sum(x * mask, axis=[1, 2]))
        return x

    def log_call(self, x):
        x = tf.expand_dims(x, -1)
        mask = self.get_mask(x)
        x = self.mapping(x)
        # mapped.shape = (None, SIZE // 4, SIZE // 4, 128)
        x = self.out_class(x)
        x = tf.reduce_sum(x * mask, axis=[1, 2])
        return x

    def group_call(self, x, suppression=1.):
        x = tf.expand_dims(x, -1)
        mask = self.get_mask(x)
        x = self.mapping(x)
        x = self.out_class(x)
        x = self.smax(tf.reduce_sum(x * mask * suppression, axis=[1, 2]))
        return x

    def map_call(self, x):
        x = tf.expand_dims(x, -1)
        mask = self.get_mask(x)
        x = self.mapping(x)
        x = self.out_class(x)
        x = self.smax(x * mask)
        return x

    def log_map_call(self, x):
        x = tf.expand_dims(x, -1)
        mask = self.get_mask(x)
        x = self.mapping(x)
        x = self.out_class(x)
        x = x * mask
        return x

    def compile(self):
        super().compile(loss='categorical_crossentropy',
                        optimizer=tf.keras.optimizers.legacy.Adam(learning_rate=self.base_learn_rate,
                                                                  decay=self.learn_rate_decay),
                        metrics=[self.val_accuracy])

    def save(self):
        if self.save_folder:
            super().save_weights(filepath=os.path.join(self.save_folder, 'model'), save_format='tf')
            json.dump({'num_class': self.num_class,
                      'base_filter_count': self.base_filter_count,
                       'residual_unit_repetition': self.residual_unit_repetition,
                       'dropout': self.dropout,
                       'base_learn_rate': self.base_learn_rate,
                       'learn_rate_decay': self.learn_rate_decay},
                      open(os.path.join(self.save_folder, 'parameters.json'), 'wt'))

    @staticmethod
    def load(save_folder, name='model'):
        parameters = json.load(open(os.path.join(save_folder, 'parameters.json'), 'rt'))
        model = DistributionToMaterialType(save_folder=save_folder, **parameters)
        model.load_weights(filepath=os.path.join(save_folder, name))
        return model

    def val_accuracy(self, y_true, y_pred):
        return tf.reduce_sum(y_true * y_pred, axis=-1)


class MappingModel(tf.keras.Model):

    # 这个模型只解决到图映射

    def __init__(self, base_filter_count=64, residual_unit_repetition=2, dropout=0.2):
        super().__init__()
        self.conv_bottom = tf.keras.layers.Conv2D(filters=base_filter_count,
                                                  kernel_size=3,
                                                  padding='same',
                                                  use_bias=False)
        self.norm_bottom = tf.keras.layers.BatchNormalization()
        self.pooling_bottom = tf.keras.layers.MaxPooling2D(pool_size=3, strides=2, padding='same')
        self.resnet_units_0 = []
        self.resnet_units_0.append(ResidualUnit(filters=base_filter_count))
        for _ in range(1, residual_unit_repetition):
            self.resnet_units_0.append(ResidualUnit(filters=base_filter_count))
        self.drop0 = tf.keras.layers.Dropout(dropout)
        self.resnet_units_1 = []
        self.resnet_units_1.append(ResidualUnit(filters=base_filter_count * 2, stride=2))
        for _ in range(1, residual_unit_repetition):
            self.resnet_units_1.append(ResidualUnit(filters=base_filter_count * 2))

    def call(self, x, training=None, mask=None):
        x = self.conv_bottom(x)
        x = self.norm_bottom(x)
        x = tf.nn.relu(x)
        x = self.pooling_bottom(x)
        for r in self.resnet_units_0:
            x = r(x)
        x = self.drop0(x)
        for r in self.resnet_units_1:
            x = r(x)
        return x


class ResidualUnit(tf.keras.Model):
    def __init__(self, filters: int, stride: int = 1):
        super().__init__()
        self.conv0 = SpecificCNN(filters=filters, kernel_half_size=1, stride=stride)
        self.norm0 = tf.keras.layers.BatchNormalization()
        self.conv1 = SpecificCNN(filters=filters, kernel_half_size=1)
        self.norm1 = tf.keras.layers.BatchNormalization()
        if stride == 1:
            self.downsample = None
        else:
            self.downsample = DownSample(filters, stride)

    def call(self, x, training=None, mask=None):
        residual = x
        x = self.conv0(x)
        x = self.norm0(x)
        x = tf.nn.relu(x)
        x = self.conv1(x)
        x = self.norm1(x)
        if self.downsample is not None:
            residual = self.downsample(residual)
        x += residual
        x = tf.nn.relu(x)
        return x


class SpecificCNN(tf.keras.layers.Conv2D):

    def __init__(self, filters: int, kernel_half_size: int, stride: int = 1, padding='same'):
        super().__init__(filters=filters,
                         kernel_size=1 + kernel_half_size * 2,
                         strides=(stride, stride),
                         padding=padding)


class DownSample(tf.keras.Model):

    def __init__(self, filters, stride):
        super().__init__()
        self.conv = tf.keras.layers.Conv2D(filters,
                                           kernel_size=2,  # 我调一下？
                                           strides=stride,
                                           use_bias=False)
        self.norm = tf.keras.layers.BatchNormalization()

    def call(self, x, training=None, mask=None):
        x = self.conv(x)
        x = self.norm(x)
        return x

