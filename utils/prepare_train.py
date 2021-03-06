#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2016 Shunta Saito

import argparse
import imp
import os
import shutil
import time

import numpy as np

import chainer
import chainer.links as L
from chainer import optimizers


def create_args():
    parser = argparse.ArgumentParser()

    # Training settings
    parser.add_argument(
        '--model_file', type=str, default='lib/models/faster_rcnn.py',
        help='The model filename (.py)')
    parser.add_argument(
        '--model_name', type=str, default='FasterRCNN',
        help='The model class name')
    parser.add_argument(
        '--trunk_model', type=str, default='VGG16',
        choices=['VGG16', 'ResNet50', 'ResNet101', 'ResNet152', 'None'])

    # Model parameters
    parser.add_argument('--rpn_in_ch', type=int, default=512)
    parser.add_argument('--rpn_out_ch', type=int, default=512)
    parser.add_argument('--n_anchors', type=int, default=9)
    parser.add_argument('--feat_stride', type=int, default=16)
    parser.add_argument('--anchor_scales', type=str, default='8,16,32')
    parser.add_argument('--num_classes', type=int, default=21)
    parser.add_argument('--loss_delta', type=float, default=3.0)
    parser.add_argument('--loss_lambda', type=float, default=1.0)

    parser.add_argument(
        '--epoch', type=int, default=100,
        help='When the trianing will finish')
    parser.add_argument(
        '--gpus', type=str, default='0',
        help='GPU Ids to be used')
    parser.add_argument(
        '--batchsize', type=int, default=1,
        help='minibatch size')
    parser.add_argument(
        '--snapshot_iter', type=int, default=1000,
        help='The current learnt parameters in the model is saved every'
             'this iteration')
    parser.add_argument(
        '--valid_freq', type=int, default=1,
        help='Perform test every this iteration (0 means no test)')
    parser.add_argument(
        '--valid_batchsize', type=int, default=1,
        help='The mini-batch size during validation loop')
    parser.add_argument(
        '--show_log_iter', type=int, default=10,
        help='Show loss value per this iterations')

    # Settings
    parser.add_argument(
        '--shift_jitter', type=int, default=None,
        help='Shift jitter amount for data augmentation (typically 50)')
    parser.add_argument(
        '--scale_jitter', type=float, default=None,
        help='Scale jitter amount for data augmentation '
             '(typically +- 2 ** 0.25)')
    parser.add_argument(
        '--scale', type=float, default=0.5,
        help='Scale for the input images and label images')
    parser.add_argument(
        '--n_classes', type=int, default=20,
        help='The number of classes that the model predicts')

    # Optimization settings
    parser.add_argument(
        '--opt', type=str, default='Adam',
        choices=['MomentumSGD', 'Adam', 'AdaGrad', 'RMSprop'],
        help='Optimization method')
    parser.add_argument('--weight_decay', type=float, default=0.0005)
    parser.add_argument('--adam_alpha', type=float, default=0.001)
    parser.add_argument('--adam_beta1', type=float, default=0.9)
    parser.add_argument('--adam_beta2', type=float, default=0.999)
    parser.add_argument('--adam_eps', type=float, default=1e-8)
    parser.add_argument('--lr', type=float, default=0.01)
    parser.add_argument(
        '--lr_decay_freq', type=int, default=10,
        help='The learning rate will be decreased every this epoch')
    parser.add_argument(
        '--lr_decay_ratio', type=float, default=0.1,
        help='When the learning rate is decreased, this number will be'
             'multiplied')
    parser.add_argument('--seed', type=int, default=1701)
    args = parser.parse_args()
    xp = chainer.cuda.cupy if chainer.cuda.available else np
    xp.random.seed(args.seed)
    args.anchor_scales = [int(v) for v in args.anchor_scales.split(',') if v]
    args.trunk_model = None if args.trunk_model == 'None' \
        else '{}Layers'.format(args.trunk_model)
    return args


def create_result_dir(model_name):
    result_dir = 'results/{}_{}'.format(
        model_name, time.strftime('%Y-%m-%d_%H-%M-%S'))
    if os.path.exists(result_dir):
        result_dir += '_{}'.format(time.clock())
    if not os.path.exists(result_dir):
        os.makedirs(result_dir)
    return result_dir


def get_model(
        model_file, model_name, gpu, rpn_in_ch, rpn_out_ch, n_anchors,
        feat_stride, anchor_scales, num_classes, spatial_scale, rpn_sigma,
        sigma, trunk_model, train=False,
        result_dir=None):
    model = imp.load_source(model_name, model_file)
    model = getattr(model, model_name)
    if trunk_model is not None:
        trunk = getattr(L, trunk_model)

    # Initialize
    model = model(
        gpu=gpu, trunk=trunk, rpn_in_ch=rpn_in_ch, rpn_out_ch=rpn_out_ch,
        n_anchors=n_anchors, feat_stride=feat_stride,
        anchor_scales=anchor_scales, num_classes=num_classes,
        spatial_scale=spatial_scale, rpn_sigma=rpn_sigma, sigma=sigma)

    # Copy files
    if result_dir is not None:
        base_fn = os.path.basename(model_file)
        dst = '{}/{}'.format(result_dir, base_fn)
        if not os.path.exists(dst):
            shutil.copy(model_file, dst)

    return model


def get_optimizer(model, opt, lr=None, adam_alpha=None, adam_beta1=None,
                  adam_beta2=None, adam_eps=None, weight_decay=None):
    if opt == 'MomentumSGD':
        optimizer = optimizers.MomentumSGD(lr=lr, momentum=0.9)
    elif opt == 'Adam':
        optimizer = optimizers.Adam(
            alpha=adam_alpha, beta1=adam_beta1,
            beta2=adam_beta2, eps=adam_eps)
    elif opt == 'AdaGrad':
        optimizer = optimizers.AdaGrad(lr=lr)
    elif opt == 'RMSprop':
        optimizer = optimizers.RMSprop(lr=lr)
    else:
        raise Exception('No optimizer is selected')

    # The first model as the master model
    optimizer.setup(model)
    if opt == 'MomentumSGD':
        optimizer.add_hook(
            chainer.optimizer.WeightDecay(weight_decay))

    return optimizer
