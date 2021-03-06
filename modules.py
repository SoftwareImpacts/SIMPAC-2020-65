# -*- coding: utf-8 -*-
#/usr/bin/python2
'''
By kyubyong park. kbpark.linguist@gmail.com. 
https://www.github.com/kyubyong/dc_tts

Modified...
'''

from __future__ import print_function, division

import tensorflow as tf
from logging import info

def embed(inputs, vocab_size, num_units, zero_pad=True, scope="embedding", reuse=None):
    '''Embeds a given tensor. 
    
    Args:
      inputs: A `Tensor` with type `int32` or `int64` containing the ids
         to be looked up in `lookup table`.
      vocab_size: An int. Vocabulary size.
      num_units: An int. Number of embedding hidden units.
      zero_pad: A boolean. If True, all the values of the fist row (id 0)
        should be constant zeros.
      scope: Optional scope for `variable_scope`.  
      reuse: Boolean, whether to reuse the weights of a previous layer
        by the same name.
        
    Returns:
      A `Tensor` with one more rank than inputs's. The last dimensionality
        should be `num_units`.
    '''
    with tf.variable_scope(scope, reuse=reuse):
        lookup_table = tf.get_variable('lookup_table', 
                                       dtype=tf.float32, 
                                       shape=[vocab_size, num_units],
                                       initializer=tf.truncated_normal_initializer(mean=0.0, stddev=0.1))
        if zero_pad:
            lookup_table = tf.concat((tf.zeros(shape=[1, num_units]), 
                                      lookup_table[1:, :]), 0)

        outputs = tf.nn.embedding_lookup(lookup_table, inputs)

    return outputs


def normalize(inputs,
              scope="normalize",
              reuse=None,
              normtype='layer'):
    '''Applies layer normalization that normalizes along the last axis.

    Args:
      inputs: A tensor with 2 or more dimensions, where the first dimension has
        `batch_size`. The normalization is over the last dimension.
      scope: Optional scope for `variable_scope`.
      reuse: Boolean, whether to reuse the weights of a previous layer
        by the same name.

    Returns:
      A tensor with the same shape and data dtype as `inputs`.
    '''
    assert normtype in [None, 'layer', 'batch']
    if normtype == 'layer':
      outputs = tf.contrib.layers.layer_norm(inputs,
                                             begin_norm_axis=-1,
                                             scope=scope,
                                             reuse=reuse)
    elif normtype == 'batch':
      outputs = tf.contrib.layers.batch_norm(inputs,
                                             scope=scope,
                                             reuse=reuse)
    else:
      outputs = inputs
    return outputs


def learn_channel_contributions(input_tensor, codes, ncodes=1, reuse=None):
    # codes (B, ?) Always 1D??
    info('learn_channel_contributions; codes: %s'%(codes.shape))
    nchannels = input_tensor.get_shape().as_list()[-1]
    lcc_gate = embed(codes, vocab_size=ncodes, num_units=nchannels, \
                  scope="lcc_embed", reuse=reuse) ## init weight mean 0.0 
    lcc_gate = tf.nn.sigmoid(lcc_gate, "lcc_gate") ##    -> 0.5 after sigmoid
    ## lcc_gate (B, filters)
    #print(lcc_gate.shape)  # (32, ?, 512)
    input_tensor = lcc_gate * input_tensor  ## Broadcast on time dimension
    return input_tensor


def conv1d(inputs,
           filters=None,
           size=1,
           rate=1,
           padding="SAME",
           dropout_rate=0,
           use_bias=True,
           activation_fn=None,
           training=True,
           scope="conv1d",
           reuse=None,
           normtype='layer',
           lcc=0, codes=None):
    '''
    Args:
      inputs: A 3-D tensor with shape of [batch, time, depth].
      filters: An int. Number of outputs (=activation maps)
      size: An int. Filter size.
      rate: An int. Dilation rate.
      padding: Either `same` or `valid` or `causal` (case-insensitive).
      dropout_rate: A float of [0, 1].
      use_bias: A boolean.
      activation_fn: A string.
      training: A boolean. If True, dropout is applied.
      scope: Optional scope for `variable_scope`.
      reuse: Boolean, whether to reuse the weights of a previous layer
        by the same name.

    Returns:
      A masked tensor of the same shape and dtypes as `inputs`.
    '''
    with tf.variable_scope(scope):
        if padding.lower() == "causal":
            # pre-padding for causality
            pad_len = (size - 1) * rate  # padding size
            inputs = tf.pad(inputs, [[0, 0], [pad_len, 0], [0, 0]])
            padding = "valid"

        if filters is None:
            filters = inputs.get_shape().as_list()[-1]

        params = {"inputs": inputs, "filters": filters, "kernel_size": size,
                  "dilation_rate": rate, "padding": padding, "use_bias": use_bias,
                  "kernel_initializer": tf.contrib.layers.variance_scaling_initializer(), "reuse": reuse}

        tensor = tf.layers.conv1d(**params)
        tensor = normalize(tensor, normtype=normtype, reuse=reuse)
        if activation_fn is not None:
            tensor = activation_fn(tensor)

        tensor = tf.layers.dropout(tensor, rate=dropout_rate, training=training)

        if lcc: 
          tensor = learn_channel_contributions(tensor, codes, ncodes=lcc, reuse=reuse)

    return tensor

def hc(inputs,
       filters=None,
       size=1,
       rate=1,
       padding="SAME",
       dropout_rate=0,
       use_bias=True,
       activation_fn=None,
       training=True,
       scope="hc",
       reuse=None,
       normtype='layer', lcc=0, codes=None):
    '''
    Args:
      inputs: A 3-D tensor with shape of [batch, time, depth].
      filters: An int. Number of outputs (=activation maps)
      size: An int. Filter size.
      rate: An int. Dilation rate.
      padding: Either `same` or `valid` or `causal` (case-insensitive).
      use_bias: A boolean.
      activation_fn: A string.
      training: A boolean. If True, dropout is applied.
      scope: Optional scope for `variable_scope`.
      reuse: Boolean, whether to reuse the weights of a previous layer
        by the same name.

    Returns:
      A masked tensor of the same shape and dtypes as `inputs`.
    '''
    _inputs = inputs
    with tf.variable_scope(scope):
        if padding.lower() == "causal":
            # pre-padding for causality
            pad_len = (size - 1) * rate  # padding size
            inputs = tf.pad(inputs, [[0, 0], [pad_len, 0], [0, 0]])
            padding = "valid"

        if filters is None:
            filters = inputs.get_shape().as_list()[-1]


        params = {"inputs": inputs, "filters": 2*filters, "kernel_size": size,
                  "dilation_rate": rate, "padding": padding, "use_bias": use_bias,
                  "kernel_initializer": tf.contrib.layers.variance_scaling_initializer(), "reuse": reuse}

        tensor = tf.layers.conv1d(**params)
        H1, H2 = tf.split(tensor, 2, axis=-1)
        H1 = normalize(H1, scope="H1", normtype=normtype, reuse=reuse)
        H2 = normalize(H2, scope="H2", normtype=normtype, reuse=reuse)
        H1 = tf.nn.sigmoid(H1, "gate")
        H2 = activation_fn(H2, "info") if activation_fn is not None else H2

        if lcc:  ## LCC applied on transformation connections only
          H2 = learn_channel_contributions(H2, codes, ncodes=lcc, reuse=reuse)

        tensor = H1*H2 + (1.-H1)*_inputs

        tensor = tf.layers.dropout(tensor, rate=dropout_rate, training=training)

    return tensor

def conv1d_transpose(inputs,
                     filters=None,
                     size=3,
                     stride=2,
                     padding='same',
                     dropout_rate=0,
                     use_bias=True,
                     activation=None,
                     training=True,
                     scope="conv1d_transpose",
                     reuse=None,
                     normtype='layer'):
    '''
        Args:
          inputs: A 3-D tensor with shape of [batch, time, depth].
          filters: An int. Number of outputs (=activation maps)
          size: An int. Filter size.
          rate: An int. Dilation rate.
          padding: Either `same` or `valid` or `causal` (case-insensitive).
          dropout_rate: A float of [0, 1].
          use_bias: A boolean.
          activation_fn: A string.
          training: A boolean. If True, dropout is applied.
          scope: Optional scope for `variable_scope`.
          reuse: Boolean, whether to reuse the weights of a previous layer
            by the same name.

        Returns:
          A tensor of the shape with [batch, time*2, depth].
        '''
    with tf.variable_scope(scope, reuse=reuse):
        if filters is None:
            filters = inputs.get_shape().as_list()[-1]
        inputs = tf.expand_dims(inputs, 1)
        tensor = tf.layers.conv2d_transpose(inputs,
                                   filters=filters,
                                   kernel_size=(1, size),
                                   strides=(1, stride),
                                   padding=padding,
                                   activation=None,
                                   kernel_initializer=tf.contrib.layers.variance_scaling_initializer(),
                                   use_bias=use_bias)
        tensor = tf.squeeze(tensor, 1)
        tensor = normalize(tensor, normtype=normtype, reuse=reuse)
        if activation is not None:
            tensor = activation(tensor)

        tensor = tf.layers.dropout(tensor, rate=dropout_rate, training=training)

    return tensor





