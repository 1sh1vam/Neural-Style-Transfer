import os
import numpy as np
import tensorflow as tf
from tensorflow.keras.models import Model
from tensorflow.keras.preprocessing.image import load_img, img_to_array
from tensorflow.keras.applications.vgg19 import preprocess_input
import matplotlib.pyplot as plt
import cv2

### Loading VGG19 model.
from tensorflow.keras.applications.vgg19 import VGG19
model = VGG19( 
    weights = 'imagenet', 
    include_top = False
    )
model.trainable = False # Setting layers of VGG19 to non-trainable
model.summary()

class CONFIG:
    IMAGE_WIDTH = 430
    IMAGE_HEIGHT = 398
    COLOR_CHANNELS = 3
    NOISE_RATIO = 0.6
    MEANS = np.array([123.68, 116.779, 103.939]).reshape((1,1,1,3)) 
    VGG_MODEL = model # Pick the VGG 19-layer model by from the paper "Very Deep Convolutional Networks for Large-Scale Image Recognition".
    STYLE_IMAGE = '/content/drive/My Drive/Colab Notebooks/NST/style.jpg' # Style image to use.
    CONTENT_IMAGE = '/content/drive/My Drive/Colab Notebooks/NST/lotus-1.jpg' # Content image to use.
    OUTPUT_DIR = '/content/drive/My Drive/Colab Notebooks/NST/'

### Resizing style image to shape of content image
style_image = cv2.imread(CONFIG.STYLE_IMAGE)
style_image = cv2.resize(style_image, (650, 437))
style_image = cv2.cvtColor(style_image, cv2.COLOR_BGR2RGB)
plt.imshow(style_image)
plt.imsave('/content/drive/My Drive/Colab Notebooks/NST/style.jpg', style_image)

def load_and_process_image(image_path):
  """
  This function takes an image and processes it to a format which can be 
  fed to VGG19 model.

  Args:
      image_path: path of image which is to be processed.

  Returns:
      image: processed image.
  """
  image = load_img(image_path)
  image = img_to_array(image)
  image = preprocess_input(image)
  image = np.expand_dims(image, axis=0)
  return image

img = load_and_process_image(CONFIG.CONTENT_IMAGE)
plt.imshow(img[0])

img = load_and_process_image(CONFIG.STYLE_IMAGE)
plt.imshow(img[0])

def deprocess_image(x):
  """
  This fucnction is used to deprocess processed image.

  Args:
      x: x is an image.
    
  Returns:
      x: deprocessed image.
  """
  ### Adding back VGG19 biases 
  x[:,:,0] += 103.939
  x[:,:,1] += 116.779
  x[:,:,2] += 123.68
  x = x[:,:,::-1] # Inverting BGR channels to RGB

  x = np.clip(x, 0, 255).astype('uint8')
  return x

def display_image(image):
  """
  This function will reshape image and call deprocess_image function 
  and then prints image.

  Args:
      image: processed image
  Returns:
      None
  """
  if len(image.shape) == 4:
    image = np.squeeze(image, axis = 0)

  img = deprocess_image(image)

  plt.xticks([])
  plt.yticks([])
  plt.imshow(img)
  plt.show()

display_image(load_and_process_image(CONFIG.CONTENT_IMAGE))

display_image(load_and_process_image(CONFIG.STYLE_IMAGE))

### layer of VGG19 model which will represent content image features
content_layer = 'block5_conv2'

content_model = Model(
    
    inputs = model.input,
    outputs = model.get_layer(content_layer).output
)

### layers of VGG19 model that we will use to stylize content image
style_layers = ['block1_conv1',
                'block2_conv1',
                'block3_conv1',
                'block4_conv1',
                'block5_conv1']
style_coeff = [0.5, 0.6, 0.8, 0.8, 0.5]

style_models = [
                Model(inputs = model.input,
                      outputs = model.get_layer(layer).output) 
                for layer in style_layers]

def content_cost(content_image, generated_image):
  """
  This function will calculate cost between content and generated images.

  Args:
      content_image: content image.
      generated_image: generated image which will be optimized.

  Returns:
      content_cost: cost between content and generated image.

  """
  a_C = content_model(content_image)
  a_G = content_model(generated_image)
  content_cost = 0.05 * tf.reduce_mean(tf.square(a_C - a_G))
  return content_cost

def gram_matrix(A):
  """
  gram matrix is used to calculate correlation between features of different
  channels

  Args:
      A: it takes an image as input

  Returns:
      GM: gram matrix containning correlation between different pixels

  """
  GM = tf.matmul(A, tf.transpose(A))
  return GM

def style_cost(style_image, generated_image):
  """
  This function will calculate cost between style and generated images.

  Args:
      style_image: style image.
      generated_image: generated image which will be optimized.

  Returns:
      total_style_cost: cost between features of style and generated image.

  """
  total_style_cost = 0

  for i, style_model in enumerate(style_models):
    a_S = style_model(style_image)
    a_G = style_model(generated_image)
    m, n_H, n_W, n_C = a_G.get_shape().as_list()
    a_S_unrolled = tf.transpose(tf.reshape(a_S, shape=[n_H * n_W, n_C]), perm = [1, 0])
    a_G_unrolled = tf.transpose(tf.reshape(a_G, shape=[n_H * n_W, n_C]), perm = [1, 0])

    GMS = gram_matrix(a_S_unrolled)
    GMG = gram_matrix(a_G_unrolled)

    current_style_cost = 1/4*1/np.square(n_C)*1/np.square(n_H*n_W) * tf.reduce_mean(tf.square(GMS - GMG))

    total_style_cost += style_coeff[i] * current_style_cost

  return total_style_cost

def train(content_image, style_image, alpha = 10, beta =40, Iterations = 2000, lr = 5.0):
  """
  This function will train the model on generated_image

  Args:
      content_image: image  which is to be stylized
      style_image: image which is used to stylize
      alpha: content weight
      beta: style weight
      Iteration: number of iteration
      lr: learning rate

  Returns:
      generate_images: list of stylized images on different iterations
      costs: list of cost at each iteration
  """
  
  content_image_preprocessed = load_and_process_image(CONFIG.CONTENT_IMAGE)
  style_image_preprocessed = load_and_process_image(CONFIG.STYLE_IMAGE)
  generated_image = tf.Variable(content_image_preprocessed, dtype = tf.float32)

  generated_images = []
  costs = []
  optimizer = tf.optimizers.Adam(learning_rate = lr)

  for i in range(Iterations):

    with tf.GradientTape() as tape:
      J_content = content_cost(content_image_preprocessed, generated_image)
      J_style = style_cost(style_image_preprocessed, generated_image)

      J_total = alpha * J_content + beta * J_style

    grads = tape.gradient(J_total, generated_image)
    optimizer.apply_gradients([(grads, generated_image)])

    costs.append(J_total.numpy())

    if i%200 == 0:
      display_image(generated_image.numpy())
      generated_images.append(generated_image.numpy())
      print('Iteration: {}/{}, Total_cost: {}, Style_cost: {}, Content_cost: {}'.format(i+1, Iterations, J_total, J_style, J_content))
  return generated_images, costs

generated_images, costs = train(CONFIG.CONTENT_IMAGE, CONFIG.STYLE_IMAGE, alpha = 1e-5, beta = 1e-2, lr = 10)

plt.plot(range(2000), costs)
plt.xlabel('Iterations')
plt.ylabel('Cost')
plt.show()

generated_images_lotus, costs2 = train(CONFIG.CONTENT_IMAGE, CONFIG.STYLE_IMAGE, alpha = 1e-4, beta = 1e-2, lr = 8.0)

for i in range(len(generated_images_lotus)):
  image = Image.fromarray(deprocess_image(generated_images_lotus[i][0]))
  plt.imshow(image)
  plt.xticks([])
  plt.yticks([])
  plt.tight_layout()
  plt.savefig('/content/drive/My Drive/Colab Notebooks/NST/lotus art/lotus'+str(i)+'.jpg')

plt.plot(range(2000), costs2)
plt.xlabel('Iterstions')
plt.ylabel('Cost')
plt.show()