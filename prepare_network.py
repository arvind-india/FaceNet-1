import tensorflow as tf
from tensorflow.contrib.layers import flatten
from tqdm import tqdm
from tensorflow.python.platform import gfile
from tensorflow.python.tools import freeze_graph
import numpy as np
class Network:
    def __init__(self):
        self.sess = tf.InteractiveSession()
        self.input_tensor = None
        self.output_tensor = None
        self.output = None
        self.cross_entropy = None
        self.loss_operation = None
        self.optimizer = None
        self.model = None
        self.correct_prediction = None
        self.accuracy_operation = None
        self.output_tensor_one_hot = None
        self.learning_rate = 0.001
        self.training_epochs = 100
        self.batch_size = 24
        self.train = None
        self.test = None
        self.network = None
        self.class_number = None
        self.classes = None
        # self.saver = tf.train.Saver()

    def prepare(self,configuration):
        self.learning_rate = configuration.learning_rate
        self.training_epochs = configuration.training_steps
        self.batch_size = configuration.batch_size
        self.train = configuration.data.train_data
        self.test = configuration.data.test_data
        self.network = configuration.network
        self.class_number = configuration.data.classes_count
        self.classes = configuration.data.classes

    def conv_layer(self, prev_layer, layer):
        W = tf.Variable(tf.random_normal(layer['weights'], dtype=tf.float32), dtype=tf.float32)
        B = tf.Variable(tf.random_normal([layer['weights'][-1]], dtype=tf.float32), dtype=tf.float32)
        convolution = tf.nn.conv2d(prev_layer, W, strides=layer['strides'], padding=layer['padding'],
                                   name=layer['name']) + B
        return convolution

    def maxpool_layer(self, prev_layer, layer):
        max_pooling = tf.nn.max_pool(prev_layer, ksize=layer['filters'], strides=layer['strides'],
                                     padding=layer['padding'], name=layer['name'])
        return max_pooling

    def relu_layer(self, prev_layer, layer):
        if layer['flatten']:
            return flatten(tf.nn.relu(prev_layer, name=layer['name']))
        else:
            return tf.nn.relu(prev_layer, name=layer['name'])

    def sigmoid_layer(self, prev_layer, layer):
        return tf.nn.sigmoid(prev_layer, name=layer['name'])

    def output_detection_layer(self, prev_layer, layer):
        prediction = np.argmax(prev_layer)
        # label_str = self.classes[prediction]
        return tf.Variable(prediction, name=layer['name'])


    def dense_layer(self, prev_layer, layer):
        fw = tf.Variable(tf.random_normal(layer['weights'], dtype=tf.float32), dtype=tf.float32)
        fb = tf.Variable(tf.random_normal([layer['weights'][-1]], dtype=tf.float32), dtype=tf.float32)
        fc = tf.add(tf.matmul(prev_layer, fw), fb,name=layer['name'])
        return fc

    def build_model(self):
        classes_number = len(self.class_number)
        neural_network_dict = self.network
        layers_op = []
        self.input_tensor = tf.placeholder(tf.float32,
                                           [None, neural_network_dict[0]['width'], neural_network_dict[0]['height'], 1],
                                           name='input_tensor')
        self.output_tensor = tf.placeholder(tf.int32, (None), name='output_tensor')
        self.output_tensor_one_hot = tf.one_hot(self.output_tensor, classes_number)

        layers_op.append(self.input_tensor)

        for layer in neural_network_dict:
            if layer['type'] == 'conv':
                layers_op.append(self.conv_layer(layers_op[-1], layer))
            elif layer['type'] == 'maxpool':
                layers_op.append(self.maxpool_layer(layers_op[-1], layer))
            elif layer['type'] == 'relu':
                layers_op.append(self.relu_layer(layers_op[-1], layer))
            elif layer['type'] == 'fc':
                layers_op.append(self.dense_layer(layers_op[-1], layer))
            elif layer['type'] == 'sigmoid':
                layers_op.append(self.sigmoid_layer(layers_op[-1], layer))
            elif layer['type'] == 'prediction':
                layers_op.append(self.output_detection_layer(layers_op[-1], layer))

        self.output = layers_op[-2]
        self.cross_entropy = tf.nn.softmax_cross_entropy_with_logits(logits=self.output, labels=self.output_tensor_one_hot)
        self.loss_operation = tf.reduce_mean(self.cross_entropy,name="loss")
        self.optimizer = tf.train.AdamOptimizer(learning_rate=self.learning_rate,name="optimizer")
        self.model = self.optimizer.minimize(self.loss_operation)
        self.correct_prediction = tf.equal(tf.argmax(self.output, 1), tf.argmax(self.output_tensor_one_hot, 1))
        self.accuracy_operation = tf.reduce_mean(tf.cast(self.correct_prediction, tf.float32))

    def train_model(self):
        images = self.train['images']
        labels = self.train['labels_n']

        saver = tf.train.Saver()
        with self.sess.as_default():
            self.sess.run(tf.global_variables_initializer())

            for i in range(self.training_epochs):
                epoch_loss = 0
                start = 0
                end = 0
                for j in tqdm(range(0, len(images), self.batch_size)):
                    end = start + self.batch_size
                    batch_images = images[start:end]
                    # batch_labels = images[start:end]
                    batch_labels = labels[start:end]
                    start = start + self.batch_size

                    _, loss = self.sess.run([self.model, self.loss_operation],
                                       feed_dict={self.input_tensor: batch_images,
                                                  self.output_tensor: batch_labels})

                    epoch_loss += loss

                print("Epoch Loss for epoch : ", str(i), " is ", epoch_loss)
                self.test_model()
                if epoch_loss == 0.0:
                    break

            # graph = tf.get_default_graph()
            checkpoint_prefix = './model/model.ckpt'
            saver.save(self.sess, checkpoint_prefix) #,global_step=50
            # tf.train.write_graph(graph, './model/', 'train.pb')
            tf.train.write_graph(self.sess.graph.as_graph_def(), './model/', 'train.pb')

            input_graph_path = './model/train.pb'
            input_saver_def_path = ""
            input_binary = False
            input_checkpoint_path = checkpoint_prefix
            output_graph_path = './model/train_model.pb'
            clear_devices = False
            output_node_names = "output_tensor,input_tensor,output,prediction,conv1,maxpool1,relu1,conv2,maxpool2,flatten_relu2,fc1,relu3,loss"
            restore_op_name = "save/restore_all"
            filename_tensor_name = "save/Const:0"
            initializer_nodes = ""
            freeze_graph.freeze_graph(input_graph_path,
                                      input_saver_def_path,
                                      input_binary,
                                      input_checkpoint_path,
                                      output_node_names,
                                      restore_op_name,
                                      filename_tensor_name,
                                      output_graph_path,
                                      clear_devices,
                                      initializer_nodes)


    def test_model(self):
        images = self.test['images']
        labels = self.test['labels_n']

        with self.sess.as_default():
            print('Accuracy is ', self.accuracy_operation.eval({self.input_tensor: images, self.output_tensor: labels}))

    def load_pre_train_model(self,model_file):
        with gfile.FastGFile(model_file, "rb") as f:
            graph_def = tf.GraphDef()
            byte = f.read()
            graph_def.ParseFromString(byte)

        tf.import_graph_def(graph_def, name='')
